from typing import TypedDict, Annotated
import operator
from backend.models import Article

class PipelineState(TypedDict):
    articles: list[Article]
    summaries: Annotated[list, operator.add]
    synthesis: str | None
    tags: Annotated[dict[int, tuple[str, str]], operator.or_]

class SummarizeState(TypedDict):
    article: Article

class BiasDetectionState(TypedDict):
    article: Article
    bias: str | None
    explanation: str | None