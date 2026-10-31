"""Analyze one article: summary and bias, skipping whatever is already known.

Graph::

    START -> load -> (summarize ∥ detect_bias, only the missing ones) -> save -> END
                  \\-> END   (nothing missing)

``load`` merges what the request already carries (``Article.summary`` /
``Article.tag``) with the cache; only the missing pieces are computed, and
newly computed results are written back to the cache. A failing task is
recorded as a :class:`TaskFailure` instead of aborting the workflow, so the
other task's result is still returned and cached.
"""

import logging
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.cache.base import AnalysisCache
from backend.llm.base import LLMClient
from backend.llm.errors import LLMError
from backend.models import (
    Article,
    ArticleAnalysis,
    ArticleResult,
    BiasAssessment,
    TaskFailure,
)
from backend.workflows import tasks

logger = logging.getLogger(__name__)


class ArticleState(TypedDict, total=False):
    article: Article
    known: ArticleAnalysis | None  # pre-resolved by the caller; skips the lookup
    summary: str | None
    bias: BiasAssessment | None
    failures: Annotated[list[TaskFailure], operator.add]


class ArticleWorkflow:
    def __init__(self, llm: LLMClient, cache: AnalysisCache | None = None):
        self._llm = llm
        self._cache = cache
        self.graph = self._build_graph()

    async def run(
        self, article: Article, known: ArticleAnalysis | None = None
    ) -> ArticleResult:
        """Analyze ``article``; pass ``known`` if it was already resolved."""
        state = await self.graph.ainvoke(
            {"article": article, "known": known, "failures": []}
        )
        return ArticleResult(
            analysis=ArticleAnalysis(
                summary=state.get("summary"), bias=state.get("bias")
            ),
            failures=state["failures"],
        )

    async def resolve_known(self, article: Article) -> ArticleAnalysis:
        """What is already known about ``article``: its own fields, then the cache."""
        known = ArticleAnalysis(
            summary=article.summary or None,
            bias=BiasAssessment(label=article.tag) if article.tag else None,
        )
        if not known.is_complete and self._cache:
            known = known.merged_with(await self._cache.get(article.url))
        return known

    def _build_graph(self) -> CompiledStateGraph:
        graph = StateGraph(ArticleState)
        graph.add_node("load", self._load)
        graph.add_node("summarize", self._summarize)
        graph.add_node("detect_bias", self._detect_bias)
        graph.add_node("save", self._save)

        graph.add_edge(START, "load")
        graph.add_conditional_edges(
            "load", self._route_missing, ["summarize", "detect_bias", END]
        )
        graph.add_edge("summarize", "save")
        graph.add_edge("detect_bias", "save")
        graph.add_edge("save", END)
        return graph.compile()

    async def _load(self, state: ArticleState) -> ArticleState:
        article = state["article"]
        known = state.get("known") or await self.resolve_known(article)
        logger.debug(
            "Article %s: summary %s, bias %s",
            article.url,
            "known" if known.summary is not None else "missing",
            "known" if known.bias is not None else "missing",
        )
        return {"summary": known.summary, "bias": known.bias}

    @staticmethod
    def _route_missing(state: ArticleState) -> list[str]:
        missing = []
        if state.get("summary") is None:
            missing.append("summarize")
        if state.get("bias") is None:
            missing.append("detect_bias")
        return missing or [END]

    async def _summarize(self, state: ArticleState) -> ArticleState:
        try:
            return {"summary": await tasks.summarize(self._llm, state["article"])}
        except LLMError as e:
            return {"failures": [self._failure("summarize", state["article"], e)]}

    async def _detect_bias(self, state: ArticleState) -> ArticleState:
        try:
            return {"bias": await tasks.detect_bias(self._llm, state["article"])}
        except LLMError as e:
            return {"failures": [self._failure("detect_bias", state["article"], e)]}

    async def _save(self, state: ArticleState) -> ArticleState:
        analysis = ArticleAnalysis(summary=state.get("summary"), bias=state.get("bias"))
        if self._cache and (analysis.summary is not None or analysis.bias is not None):
            await self._cache.put(state["article"].url, analysis)
        return {}

    @staticmethod
    def _failure(task: str, article: Article, error: LLMError) -> TaskFailure:
        logger.warning(
            "Task %s failed for %s: %s: %s",
            task,
            article.url,
            type(error).__name__,
            error,
        )
        return TaskFailure(
            task=task,
            error=f"{type(error).__name__}: {error}",
            retryable=error.retryable,
            article_id=article.id,
        )
