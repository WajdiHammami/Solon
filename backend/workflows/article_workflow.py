"""Analyze one article: summary and bias, skipping whatever is already known.

Graph::

    START -> load -> (summarize ∥ detect_bias, only the missing ones) -> save -> END
                  \\-> END   (nothing missing)

``load`` looks the article up in the server-side cache; only the missing
pieces are computed, and newly computed results are written back to the
cache. Analysis fields sent by the client (``Article.summary`` /
``Article.tag``) are never trusted: a client could otherwise skip work or
plant results that would then be cached for everyone. A failing task is
recorded as a :class:`TaskFailure` instead of aborting the workflow, so the
other task's result is still returned and cached.
"""

import logging
import operator
from collections.abc import Awaitable, Callable
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
    from_cache: list[str]  # tasks whose result was already known at load
    failures: Annotated[list[TaskFailure], operator.add]


#: Fetches an article's full text by URL; returns "" when it can't.
ContentLoader = Callable[[str], Awaitable[str]]


class ArticleWorkflow:
    """
    :param content_loader: when set, articles that still need LLM work and
        have less than ``min_content_chars`` of text are scraped first.
    """

    def __init__(
        self,
        llm: LLMClient,
        cache: AnalysisCache | None = None,
        content_loader: ContentLoader | None = None,
        min_content_chars: int = 600,
    ):
        self._llm = llm
        self._cache = cache
        self._content_loader = content_loader
        self._min_content_chars = min_content_chars
        self.graph = self._build_graph()

    @property
    def fetches_content_below(self) -> int:
        """Content length under which articles are scraped (0 = never)."""
        return self._min_content_chars if self._content_loader else 0

    async def run(
        self, article: Article, known: ArticleAnalysis | None = None
    ) -> ArticleResult:
        """Analyze ``article``; pass ``known`` if it was already resolved."""
        state = await self.graph.ainvoke(
            {"article": article, "known": known, "failures": []}
        )
        from_cache = state.get("from_cache", [])
        produced = {"summarize": state.get("summary"), "detect_bias": state.get("bias")}
        computed = [
            task for task, value in produced.items()
            if value is not None and task not in from_cache
        ]
        logger.debug(
            "Article %s: from cache %s, computed %s, failed %s",
            article.url,
            from_cache or "-",
            computed or "-",
            [f.task for f in state["failures"]] or "-",
        )
        return ArticleResult(
            analysis=ArticleAnalysis(
                summary=state.get("summary"), bias=state.get("bias")
            ),
            failures=state["failures"],
            from_cache=from_cache,
            computed=computed,
        )

    async def resolve_known(self, article: Article) -> ArticleAnalysis:
        """What the server already knows about ``article`` (cache only).

        The article's own ``summary``/``tag`` are deliberately ignored; see
        the module docstring.
        """
        cached = await self._cache.get(article.url) if self._cache else None
        return cached or ArticleAnalysis()

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
        if not known.is_complete:
            article = await self._ensure_content(article)
        from_cache = [
            task
            for task, value in (("summarize", known.summary), ("detect_bias", known.bias))
            if value is not None
        ]
        return {
            "article": article,
            "summary": known.summary,
            "bias": known.bias,
            "from_cache": from_cache,
        }

    async def _ensure_content(self, article: Article) -> Article:
        """Scrape full text for an article with too little content to analyze.

        Keeps the existing (snippet) content when scraping yields nothing.
        """
        if len(article.content or "") >= self.fetches_content_below:
            return article
        scraped = await self._content_loader(article.url)
        if not scraped:
            logger.info("No content scraped for %s; using snippet", article.url)
            return article
        logger.debug("Scraped %d chars for %s", len(scraped), article.url)
        return article.model_copy(update={"content": scraped})

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
