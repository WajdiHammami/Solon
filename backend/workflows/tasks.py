"""Single-purpose LLM tasks. Each one is one capability with one prompt.

Workflows compose these; they hold no graph or caching logic themselves.
"""

from pydantic import ValidationError

from backend.llm.base import LLMClient
from backend.llm.errors import LLMInvalidOutputError
from backend.llm.models import GenerationRequest, Message, Role
from backend.models import Article, BiasAssessment
from backend.workflows import prompts


async def summarize(llm: LLMClient, article: Article) -> str:
    response = await llm.ainvoke(
        GenerationRequest(
            messages=[
                Message(role=Role.SYSTEM, content=prompts.ANALYST_SYSTEM),
                Message(
                    role=Role.USER,
                    content=prompts.SUMMARIZE.format(
                        title=article.title,
                        source=article.source_name,
                        content=article.content or "",
                    ),
                ),
            ]
        )
    )
    return response.content.strip()


async def detect_bias(llm: LLMClient, article: Article) -> BiasAssessment:
    response = await llm.ainvoke(
        GenerationRequest(
            messages=[
                Message(role=Role.SYSTEM, content=prompts.BIAS_SYSTEM),
                Message(
                    role=Role.USER,
                    content=prompts.BIAS_ARTICLE.format(
                        title=article.title,
                        source=article.source_name,
                        url=article.url,
                        content=article.content or "",
                    ),
                ),
            ],
            json_output=True,
        )
    )
    try:
        return BiasAssessment.model_validate_json(response.content)
    except ValidationError as e:
        raise LLMInvalidOutputError(
            f"Bias detection returned malformed JSON: {response.content!r}"
        ) from e


async def synthesize(llm: LLMClient, articles: list[tuple[Article, str]]) -> str:
    """Write a cross-source analysis from ``(article, summary)`` pairs."""
    body = "\n\n".join(
        prompts.SYNTHESIZE_ARTICLE.format(
            title=article.title,
            source=article.source_name,
            url=article.url,
            summary=summary,
        )
        for article, summary in articles
    )
    response = await llm.ainvoke(
        GenerationRequest(
            messages=[
                Message(role=Role.SYSTEM, content=prompts.SYNTHESIZE_SYSTEM),
                Message(role=Role.USER, content=body),
            ]
        )
    )
    return response.content.strip()
