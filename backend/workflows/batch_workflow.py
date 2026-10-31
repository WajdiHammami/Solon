"""Analyze many articles and synthesize a cross-source view.

Graph::

    START -> plan -> analyze_article (one per selected article, in parallel)
                  -> synthesize -> END

``plan`` resolves what is already known about each article (request fields,
then cache), estimates the tokens the remaining work needs, and drops the
lowest-priority articles if the estimate exceeds the budget. Each
``analyze_article`` runs the :class:`ArticleWorkflow`, so known results are
reused. Failures are collected rather than aborting the batch, and results
are keyed by ``Article.id``, never by position.
"""

import asyncio
import logging
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from backend.llm.base import LLMClient
from backend.llm.errors import LLMError
from backend.models import Article, ArticleAnalysis, BatchAnalysis, TaskFailure
from backend.workflows import tasks
from backend.workflows.article_workflow import ArticleWorkflow
from backend.workflows.budget import Prioritizer, keep_order, plan_batch

logger = logging.getLogger(__name__)


class BatchState(TypedDict, total=False):
    articles: list[Article]
    known: dict[int, ArticleAnalysis]
    selected: list[Article]
    skipped: list[int]
    estimated_tokens: int
    analyses: Annotated[dict[int, ArticleAnalysis], operator.or_]
    failed: Annotated[list[TaskFailure], operator.add]
    # (task, "cache" | "computed") for every summary/bias produced.
    provenance: Annotated[list[tuple[str, str]], operator.add]
    synthesis: str | None
    sources: list[int]


class AnalyzeArticleState(TypedDict):
    article: Article
    known: ArticleAnalysis


class BatchWorkflow:
    """
    :param max_tokens: estimated-token budget per batch; ``None`` disables it.
    :param max_concurrency: max articles analyzed at once (each article makes
        up to two LLM calls in parallel); ``None`` means unlimited.
    :param prioritize: orders articles most-important first, deciding which
        are dropped when over budget.
    """

    def __init__(
        self,
        llm: LLMClient,
        article_workflow: ArticleWorkflow,
        max_tokens: int | None = None,
        max_concurrency: int | None = None,
        prioritize: Prioritizer = keep_order,
    ):
        self._llm = llm
        self._article_workflow = article_workflow
        self._max_tokens = max_tokens
        self._max_concurrency = max_concurrency
        self._prioritize = prioritize
        self.graph = self._build_graph()

    async def run(self, articles: list[Article]) -> BatchAnalysis:
        config = {}
        if self._max_concurrency is not None:
            config["max_concurrency"] = self._max_concurrency
        state = await self.graph.ainvoke(
            {"articles": articles, "analyses": {}, "failed": [], "provenance": []},
            config=config,
        )
        return BatchAnalysis(
            analyses=state["analyses"],
            synthesis=state.get("synthesis"),
            sources=state.get("sources", []),
            failed=state["failed"],
            skipped=state.get("skipped", []),
            estimated_tokens=state.get("estimated_tokens", 0),
        )

    def _build_graph(self) -> CompiledStateGraph:
        graph = StateGraph(BatchState)
        graph.add_node("plan", self._plan)
        graph.add_node("analyze_article", self._analyze_article)
        graph.add_node("synthesize", self._synthesize)

        graph.add_edge(START, "plan")
        graph.add_conditional_edges("plan", self._fan_out, ["analyze_article", END])
        graph.add_edge("analyze_article", "synthesize")
        graph.add_edge("synthesize", END)
        return graph.compile()

    async def _plan(self, state: BatchState) -> BatchState:
        articles = state["articles"]
        resolved = await asyncio.gather(
            *(self._article_workflow.resolve_known(a) for a in articles)
        )
        known = {a.id: k for a, k in zip(articles, resolved)}
        plan = plan_batch(
            articles,
            known,
            self._max_tokens,
            self._prioritize,
            fetch_below=self._article_workflow.fetches_content_below,
        )
        logger.info(
            "Batch plan: %d articles, %d selected, %d skipped, ~%d tokens (budget %s)",
            len(articles),
            len(plan.selected),
            len(plan.skipped),
            plan.estimated_tokens,
            self._max_tokens,
        )
        return {
            "known": known,
            "selected": plan.selected,
            "skipped": [a.id for a in plan.skipped],
            "estimated_tokens": plan.estimated_tokens,
        }

    @staticmethod
    def _fan_out(state: BatchState) -> list[Send] | str:
        if not state["selected"]:
            return END
        return [
            Send(
                "analyze_article",
                AnalyzeArticleState(article=a, known=state["known"][a.id]),
            )
            for a in state["selected"]
        ]

    async def _analyze_article(self, state: AnalyzeArticleState) -> BatchState:
        article = state["article"]
        result = await self._article_workflow.run(article, known=state["known"])
        return {
            "analyses": {article.id: result.analysis},
            "failed": result.failures,
            "provenance": [(t, "cache") for t in result.from_cache]
            + [(t, "computed") for t in result.computed],
        }

    async def _synthesize(self, state: BatchState) -> BatchState:
        summarized = [
            (article, state["analyses"][article.id].summary)
            for article in state["selected"]
            if state["analyses"][article.id].summary
        ]
        sources = [article.id for article, _ in summarized]
        self._log_provenance(state)
        if not summarized:
            return {"synthesis": None, "sources": []}
        try:
            synthesis = await tasks.synthesize(self._llm, summarized)
        except LLMError as e:
            logger.warning("Synthesis failed: %s: %s", type(e).__name__, e)
            return {
                "synthesis": None,
                "sources": sources,
                "failed": [
                    TaskFailure(
                        task="synthesize",
                        error=f"{type(e).__name__}: {e}",
                        retryable=e.retryable,
                    )
                ],
            }
        logger.info(
            "Batch done: synthesis from %d sources, %d failed tasks",
            len(sources),
            len(state["failed"]),
        )
        return {"synthesis": synthesis, "sources": sources}

    @staticmethod
    def _log_provenance(state: BatchState) -> None:
        provenance = state.get("provenance", [])

        def count(task: str, origin: str) -> int:
            return provenance.count((task, origin))

        logger.info(
            "Batch analysis: %d articles — summaries %d new, %d from database; "
            "bias %d new, %d from database",
            len(state["selected"]),
            count("summarize", "computed"),
            count("summarize", "cache"),
            count("detect_bias", "computed"),
            count("detect_bias", "cache"),
        )
