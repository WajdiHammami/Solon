from typing import TypedDict, Annotated
import operator
from backend.models import Article

class PipelineState(TypedDict):
    topic: str
    providers: list[str] | None
    articles: list[Article]
    summaries: Annotated[list, operator.add]
    synthesis: str | None

class SummarizeState(TypedDict):
    article: Article