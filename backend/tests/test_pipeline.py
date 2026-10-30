"""Tests for the LangGraph summarization pipeline.

The pipeline takes the LLM as a constructor argument, so a :class:`FakeLLM`
(see ``conftest.py``) is injected and no real model is ever called.
"""

from backend.summarization.pipeline import SummarizationPipeline


class TestBatchSummarization:
    def test_produces_summaries_tags_and_synthesis(self, fake_llm, make_article):
        pipeline = SummarizationPipeline(llm=fake_llm)
        articles = [make_article(1, content="c1"), make_article(2, content="c2")]

        result = pipeline.run_batch_summarization(articles)

        assert len(result["summaries"]) == 2
        assert result["synthesis"]
        # one bias tag per article, keyed by article id
        assert set(result["tags"].keys()) == {1, 2}
        tag, explanation = result["tags"][1]
        assert tag == "Political"
        assert explanation


class TestSingularSummarization:
    def test_sets_summary_and_tag_when_bias_enabled(self, fake_llm, make_article):
        pipeline = SummarizationPipeline(llm=fake_llm)
        article = make_article(5, content="body")

        result = pipeline.run_singular_summarization(
            article, config={"enable_bias": True}
        )

        summarized = result["article"]
        assert summarized.summary  # the previously-dropped summary is now returned
        assert summarized.tag == "Political"

    def test_skips_bias_when_disabled(self, fake_llm, make_article):
        pipeline = SummarizationPipeline(llm=fake_llm)
        article = make_article(6, content="body")

        result = pipeline.run_singular_summarization(
            article, config={"enable_bias": False}
        )

        summarized = result["article"]
        assert summarized.summary
        assert summarized.tag is None  # bias node never ran


class TestBiasParsing:
    def test_parses_tag_and_explanation_from_brackets(self, make_llm, make_article):
        llm = make_llm(
            lambda m: "Bias Detected: [Sensationalist] Uses alarmist wording."
        )
        pipeline = SummarizationPipeline(llm=llm)
        result = pipeline.run_batch_summarization([make_article(1, content="c")])
        tag, explanation = result["tags"][1]
        assert tag == "Sensationalist"
        assert "alarmist" in explanation

    def test_handles_no_bias_response(self, make_llm, make_article):
        llm = make_llm(lambda m: "No Bias Detected.")
        pipeline = SummarizationPipeline(llm=llm)
        result = pipeline.run_batch_summarization([make_article(1, content="c")])
        tag, explanation = result["tags"][1]
        assert tag == "No Bias"
        assert explanation == "No bias detected."
