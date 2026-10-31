from datetime import datetime, timezone

from sqlalchemy import select

from backend.cache.base import AnalysisCache
from backend.models import ArticleAnalysis, BiasAssessment
from backend.storage.database import Database
from backend.storage.tables import AnalysisRow
from backend.workflows import prompts


class SqlAnalysisCache(AnalysisCache):
    """Analyses persisted in SQL, invalidated per part by prompt version.

    A stored summary (or bias) is returned only while it was produced by the
    current prompt version; otherwise it reads as missing and the workflow
    recomputes just that part. ``model`` is recorded for reference.
    """

    def __init__(
        self,
        db: Database,
        model: str,
        summary_version: str = prompts.SUMMARY_VERSION,
        bias_version: str = prompts.BIAS_VERSION,
    ):
        self._db = db
        self._model = model
        self._summary_version = summary_version
        self._bias_version = bias_version

    async def get(self, url: str) -> ArticleAnalysis | None:
        async with self._db.session() as session:
            row = await session.get(AnalysisRow, url)
        return self._current(row) if row is not None else None

    async def get_many(self, urls: list[str]) -> dict[str, ArticleAnalysis]:
        if not urls:
            return {}
        async with self._db.session() as session:
            rows = await session.scalars(
                select(AnalysisRow).where(AnalysisRow.url.in_(set(urls)))
            )
            found = {row.url: self._current(row) for row in rows}
        return {url: analysis for url, analysis in found.items() if analysis is not None}

    def _current(self, row: AnalysisRow) -> ArticleAnalysis | None:
        """The parts of ``row`` produced by the current prompt versions."""
        summary = row.summary if row.summary_version == self._summary_version else None
        bias = (
            BiasAssessment(label=row.bias_label, explanation=row.bias_explanation)
            if row.bias_version == self._bias_version and row.bias_label is not None
            else None
        )
        if summary is None and bias is None:
            return None
        return ArticleAnalysis(summary=summary, bias=bias)

    async def put(self, url: str, analysis: ArticleAnalysis) -> None:
        now = datetime.now(timezone.utc)
        async with self._db.session() as session:
            row = await session.get(AnalysisRow, url)
            if row is None:
                row = AnalysisRow(url=url)
                session.add(row)
            # Only touch the parts this analysis has; keep the other part's
            # stored value (and its timestamp) when it is unchanged.
            if analysis.summary is not None and (
                row.summary != analysis.summary
                or row.summary_version != self._summary_version
            ):
                row.summary = analysis.summary
                row.summary_version = self._summary_version
                row.summary_model = self._model
                row.summary_at = now
            bias = analysis.bias
            if bias is not None and (
                row.bias_label != bias.label
                or row.bias_explanation != bias.explanation
                or row.bias_version != self._bias_version
            ):
                row.bias_label = bias.label
                row.bias_explanation = bias.explanation
                row.bias_version = self._bias_version
                row.bias_model = self._model
                row.bias_at = now
