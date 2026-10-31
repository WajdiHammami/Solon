"""Up-front token estimation and budget-based article selection.

Estimates are deliberately rough (characters / 4) and pessimistic about
output length, since reasoning models spend hidden tokens before answering.
They exist to bound a batch's cost, not to bill it.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.models import Article, ArticleAnalysis

CHARS_PER_TOKEN = 4
PROMPT_OVERHEAD_TOKENS = 200  # system prompt + instructions per call
SUMMARY_OUTPUT_TOKENS = 500
BIAS_OUTPUT_TOKENS = 300
SYNTHESIS_OUTPUT_TOKENS = 1500
SYNTHESIS_PER_ARTICLE_TOKENS = 200  # title + source + summary, as fed to synthesis

#: Orders articles from highest to lowest priority.
Prioritizer = Callable[[list[Article]], list[Article]]


def keep_order(articles: list[Article]) -> list[Article]:
    """Default priority: earlier in the list is more important."""
    return list(articles)


def estimate_text_tokens(text: str | None) -> int:
    return math.ceil(len(text or "") / CHARS_PER_TOKEN)


def estimate_article_tokens(article: Article, known: ArticleAnalysis) -> int:
    """Tokens needed to compute whatever ``known`` is still missing."""
    input_tokens = (
        PROMPT_OVERHEAD_TOKENS
        + estimate_text_tokens(article.title)
        + estimate_text_tokens(article.content)
    )
    total = 0
    if known.summary is None:
        total += input_tokens + SUMMARY_OUTPUT_TOKENS
    if known.bias is None:
        total += input_tokens + BIAS_OUTPUT_TOKENS
    return total


def synthesis_base_tokens() -> int:
    return PROMPT_OVERHEAD_TOKENS + SYNTHESIS_OUTPUT_TOKENS


@dataclass
class BudgetPlan:
    selected: list[Article] = field(default_factory=list)
    skipped: list[Article] = field(default_factory=list)
    estimated_tokens: int = 0


def plan_batch(
    articles: list[Article],
    known: dict[int, ArticleAnalysis],
    max_tokens: int | None,
    prioritize: Prioritizer = keep_order,
) -> BudgetPlan:
    """Select articles in priority order until ``max_tokens`` would be exceeded.

    Once an article doesn't fit, every lower-priority article that still
    needs LLM work is skipped too, so a cheap low-priority article never
    displaces an expensive high-priority one. Articles whose analysis is
    already known cost only their share of the synthesis and are kept as
    long as that fits.
    """
    plan = BudgetPlan(estimated_tokens=synthesis_base_tokens())
    exhausted = False
    for article in prioritize(articles):
        analysis_cost = estimate_article_tokens(article, known[article.id])
        cost = analysis_cost + SYNTHESIS_PER_ARTICLE_TOKENS
        fits = max_tokens is None or plan.estimated_tokens + cost <= max_tokens
        if fits and (analysis_cost == 0 or not exhausted):
            plan.selected.append(article)
            plan.estimated_tokens += cost
        else:
            exhausted = True
            plan.skipped.append(article)
    if not plan.selected:
        plan.estimated_tokens = 0
    return plan
