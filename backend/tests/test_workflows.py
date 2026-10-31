"""Tests for the analysis tasks and the article/batch workflows.

The LLM is a scripted in-memory :class:`LLMClient`; nothing hits the network.
"""

import json

import pytest

from backend.cache.memory import InMemoryAnalysisCache
from backend.llm.base import LLMClient
from backend.llm.errors import LLMAuthenticationError, LLMInvalidOutputError, LLMRateLimitError
from backend.llm.models import GenerationResponse, LLMConfig
from backend.models import ArticleAnalysis, BiasAssessment
from backend.workflows import prompts, tasks
from backend.workflows.article_workflow import ArticleWorkflow
from backend.workflows.batch_workflow import BatchWorkflow

BIAS_JSON = json.dumps({"label": "Political", "explanation": "Charged language."})


@pytest.fixture
def anyio_backend():
    return "asyncio"


class ScriptedLLM(LLMClient):
    """Answers by task (recognised from the system prompt) and records calls.

    ``fail`` maps ``(task, article title)`` to an error to raise instead;
    use ``"*"`` as the title to fail that task for every article.
    """

    def __init__(self, bias_reply=BIAS_JSON, fail=None):
        self.bias_reply = bias_reply
        self.fail = fail or {}
        self.requests = []

    @property
    def config(self):
        return LLMConfig(model="scripted")

    def task_calls(self, task):
        return [r for r in self.requests if self._task(r) == task]

    @staticmethod
    def _task(request):
        system = request.messages[0].content
        if system == prompts.BIAS_SYSTEM:
            return "detect_bias"
        if system == prompts.SYNTHESIZE_SYSTEM:
            return "synthesize"
        return "summarize"

    @staticmethod
    def _title(request):
        body = request.messages[1].content
        return body.split("Title: ")[1].split("\n")[0] if "Title: " in body else ""

    def invoke(self, request):
        self.requests.append(request)
        task, title = self._task(request), self._title(request)
        error = self.fail.get((task, title)) or self.fail.get((task, "*"))
        if error:
            raise error
        if task == "detect_bias":
            content = self.bias_reply
        elif task == "synthesize":
            content = "synthesis text"
        else:
            content = f"summary of {title}"
        return GenerationResponse(content=content, model="scripted")

    async def ainvoke(self, request):
        return self.invoke(request)

    def stream(self, request):
        yield self.invoke(request).content

    async def astream(self, request):
        yield self.invoke(request).content


@pytest.fixture
def llm():
    return ScriptedLLM()


@pytest.fixture
def cache():
    return InMemoryAnalysisCache()


pytestmark = pytest.mark.anyio


class TestTasks:
    async def test_detect_bias_parses_json(self, llm, make_article):
        bias = await tasks.detect_bias(llm, make_article())
        assert bias == BiasAssessment(label="Political", explanation="Charged language.")
        assert llm.requests[0].json_output is True

    async def test_detect_bias_rejects_malformed_output(self, make_article):
        llm = ScriptedLLM(bias_reply="Bias Detected: [Political]")
        with pytest.raises(LLMInvalidOutputError):
            await tasks.detect_bias(llm, make_article())

    async def test_synthesize_includes_every_summary(self, llm, make_article):
        a, b = make_article(1), make_article(2)
        await tasks.synthesize(llm, [(a, "sum A"), (b, "sum B")])
        body = llm.requests[0].messages[1].content
        assert "sum A" in body and "sum B" in body
        assert "Source 1" in body and "Source 2" in body


class TestArticleWorkflow:
    async def test_computes_both_when_nothing_known(self, llm, make_article):
        result = await ArticleWorkflow(llm).run(make_article(1))
        assert result.analysis.summary == "summary of Title 1"
        assert result.analysis.bias.label == "Political"
        assert result.failures == []
        assert len(llm.task_calls("summarize")) == 1
        assert len(llm.task_calls("detect_bias")) == 1

    async def test_skips_summary_already_on_article(self, llm, make_article):
        article = make_article(1, summary="existing summary")
        result = await ArticleWorkflow(llm).run(article)
        assert result.analysis.summary == "existing summary"
        assert llm.task_calls("summarize") == []
        assert len(llm.task_calls("detect_bias")) == 1

    async def test_skips_bias_already_on_article(self, llm, make_article):
        result = await ArticleWorkflow(llm).run(make_article(1, tag="Neutral"))
        assert result.analysis.bias.label == "Neutral"
        assert llm.task_calls("detect_bias") == []
        assert len(llm.task_calls("summarize")) == 1

    async def test_no_llm_calls_when_article_complete(self, llm, make_article):
        article = make_article(1, summary="s", tag="Neutral")
        result = await ArticleWorkflow(llm).run(article)
        assert result.analysis.summary == "s"
        assert llm.requests == []

    async def test_uses_preresolved_known_without_cache_lookup(self, llm, make_article):
        class ExplodingCache(InMemoryAnalysisCache):
            async def get(self, url):
                raise AssertionError("cache should not be read")

        known = ArticleAnalysis(summary="given", bias=BiasAssessment(label="None"))
        result = await ArticleWorkflow(llm, ExplodingCache()).run(
            make_article(1), known=known
        )
        assert result.analysis == known
        assert llm.requests == []

    async def test_reads_from_cache(self, llm, cache, make_article):
        article = make_article(1)
        await cache.put(
            article.url,
            ArticleAnalysis(summary="cached", bias=BiasAssessment(label="Economic")),
        )
        result = await ArticleWorkflow(llm, cache).run(article)
        assert result.analysis.summary == "cached"
        assert result.analysis.bias.label == "Economic"
        assert llm.requests == []

    async def test_fills_only_what_cache_lacks(self, llm, cache, make_article):
        article = make_article(1)
        await cache.put(article.url, ArticleAnalysis(summary="cached"))
        result = await ArticleWorkflow(llm, cache).run(article)
        assert result.analysis.summary == "cached"
        assert result.analysis.bias.label == "Political"
        assert llm.task_calls("summarize") == []

    async def test_writes_results_to_cache(self, llm, cache, make_article):
        article = make_article(1)
        await ArticleWorkflow(llm, cache).run(article)
        cached = await cache.get(article.url)
        assert cached.summary == "summary of Title 1"
        assert cached.bias.label == "Political"

    async def test_second_run_is_served_from_cache(self, llm, cache, make_article):
        workflow = ArticleWorkflow(llm, cache)
        await workflow.run(make_article(1))
        calls_after_first = len(llm.requests)
        # Same URL, fresh id: a re-fetch of the same article.
        await workflow.run(make_article(7, url="https://example.com/1"))
        assert len(llm.requests) == calls_after_first

    async def test_failed_task_is_reported_and_other_task_kept(self, cache, make_article):
        llm = ScriptedLLM(fail={("detect_bias", "*"): LLMRateLimitError("slow down")})
        article = make_article(1)
        result = await ArticleWorkflow(llm, cache).run(article)
        assert result.analysis.summary == "summary of Title 1"
        assert result.analysis.bias is None
        [failure] = result.failures
        assert failure.task == "detect_bias"
        assert failure.article_id == 1
        assert failure.retryable is True
        assert "LLMRateLimitError" in failure.error
        # The successful summary is cached, so a retry only redoes the bias.
        assert (await cache.get(article.url)).summary == "summary of Title 1"

    async def test_nothing_cached_when_every_task_fails(self, cache, make_article):
        error = LLMAuthenticationError("bad key")
        llm = ScriptedLLM(fail={("summarize", "*"): error, ("detect_bias", "*"): error})
        article = make_article(1)
        result = await ArticleWorkflow(llm, cache).run(article)
        assert {f.task for f in result.failures} == {"summarize", "detect_bias"}
        assert await cache.get(article.url) is None

    async def test_non_llm_errors_propagate(self, make_article):
        llm = ScriptedLLM(fail={("summarize", "*"): ValueError("bug")})
        with pytest.raises(ValueError):
            await ArticleWorkflow(llm).run(make_article(1))


class TestBatchWorkflow:
    def _workflow(self, llm, cache=None, **kwargs):
        return BatchWorkflow(llm, ArticleWorkflow(llm, cache), **kwargs)

    async def test_analyses_keyed_by_article_id(self, llm, make_article):
        articles = [make_article(i) for i in (3, 1, 2)]
        result = await self._workflow(llm).run(articles)
        assert set(result.analyses) == {1, 2, 3}
        for i in (1, 2, 3):
            assert result.analyses[i].summary == f"summary of Title {i}"
        assert result.synthesis == "synthesis text"
        assert result.sources == [3, 1, 2]
        assert result.failed == []
        assert result.skipped == []
        assert result.estimated_tokens > 0

    async def test_reuses_known_work_per_article(self, llm, make_article):
        articles = [
            make_article(1, summary="known", tag="Neutral"),
            make_article(2),
        ]
        result = await self._workflow(llm).run(articles)
        assert result.analyses[1].summary == "known"
        assert len(llm.task_calls("summarize")) == 1
        assert len(llm.task_calls("detect_bias")) == 1
        synthesis_body = llm.task_calls("synthesize")[0].messages[1].content
        assert "known" in synthesis_body

    async def test_rerun_only_resynthesizes(self, llm, cache, make_article):
        workflow = self._workflow(llm, cache)
        articles = [make_article(1), make_article(2)]
        await workflow.run(articles)
        llm.requests.clear()
        await workflow.run(articles)
        assert [ScriptedLLM._task(r) for r in llm.requests] == ["synthesize"]

    async def test_empty_batch(self, llm):
        result = await self._workflow(llm).run([])
        assert result.analyses == {}
        assert result.synthesis is None
        assert result.sources == []
        assert llm.requests == []

    async def test_failed_summary_excludes_article_from_sources(self, make_article):
        llm = ScriptedLLM(fail={("summarize", "Title 2"): LLMRateLimitError("slow")})
        result = await self._workflow(llm).run([make_article(1), make_article(2)])
        assert result.sources == [1]
        assert result.synthesis == "synthesis text"
        [failure] = result.failed
        assert (failure.task, failure.article_id) == ("summarize", 2)
        # Bias for the failed-summary article still succeeded.
        assert result.analyses[2].bias.label == "Political"

    async def test_failed_bias_keeps_article_as_source(self, make_article):
        llm = ScriptedLLM(fail={("detect_bias", "Title 1"): LLMRateLimitError("slow")})
        result = await self._workflow(llm).run([make_article(1), make_article(2)])
        assert result.sources == [1, 2]
        assert [(f.task, f.article_id) for f in result.failed] == [("detect_bias", 1)]

    async def test_failed_synthesis_is_reported(self, make_article):
        llm = ScriptedLLM(fail={("synthesize", "*"): LLMRateLimitError("slow")})
        result = await self._workflow(llm).run([make_article(1), make_article(2)])
        assert result.synthesis is None
        assert result.sources == [1, 2]
        [failure] = result.failed
        assert failure.task == "synthesize"
        assert failure.article_id is None

    async def test_budget_drops_lowest_priority_articles(self, llm, make_article):
        articles = [make_article(i, content="x" * 4000) for i in range(5)]
        # Each article ~3.4k tokens + ~1.7k for synthesis: two fit in 9k.
        result = await self._workflow(llm, max_tokens=9000).run(articles)
        assert result.sources == [0, 1]
        assert result.skipped == [2, 3, 4]
        assert set(result.analyses) == {0, 1}
        assert len(llm.task_calls("summarize")) == 2
        assert result.estimated_tokens <= 9000

    async def test_budget_keeps_already_analyzed_articles(self, llm, make_article):
        articles = [make_article(i, content="x" * 4000) for i in range(3)]
        articles.append(make_article(3, summary="known", tag="None"))
        result = await self._workflow(llm, max_tokens=5500).run(articles)  # one fits
        assert 3 in result.sources  # free to include despite lowest priority
        assert result.skipped == [1, 2]

    async def test_custom_prioritizer(self, llm, make_article):
        articles = [make_article(i, content="x" * 4000) for i in range(3)]
        result = await self._workflow(
            llm, max_tokens=5500, prioritize=lambda a: list(reversed(a))
        ).run(articles)
        assert result.sources == [2]
        assert result.skipped == [1, 0]

    async def test_everything_over_budget(self, llm, make_article):
        result = await self._workflow(llm, max_tokens=10).run([make_article(1)])
        assert result.skipped == [1]
        assert result.synthesis is None
        assert result.estimated_tokens == 0
        assert llm.requests == []

    async def test_max_concurrency_is_respected(self, make_article):
        import asyncio

        in_flight = peak = 0

        class SlowLLM(ScriptedLLM):
            async def ainvoke(self, request):
                nonlocal in_flight, peak
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(0.01)
                in_flight -= 1
                return self.invoke(request)

        llm = SlowLLM()
        articles = [make_article(i) for i in range(6)]
        await self._workflow(llm, max_concurrency=2).run(articles)
        assert peak <= 4  # 2 articles at once, each with summary ∥ bias
