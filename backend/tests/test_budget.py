"""Tests for token estimation and budget-based selection."""

from backend.models import ArticleAnalysis, BiasAssessment
from backend.workflows import budget
from backend.workflows.budget import estimate_article_tokens, plan_batch

NOTHING = ArticleAnalysis()
EVERYTHING = ArticleAnalysis(summary="s", bias=BiasAssessment(label="None"))


def test_estimate_text_tokens():
    assert budget.estimate_text_tokens(None) == 0
    assert budget.estimate_text_tokens("abcd") == 1
    assert budget.estimate_text_tokens("abcde") == 2


def test_known_analysis_costs_nothing(make_article):
    assert estimate_article_tokens(make_article(content="x" * 1000), EVERYTHING) == 0


def test_cost_scales_with_missing_tasks(make_article):
    article = make_article(content="x" * 4000)
    both = estimate_article_tokens(article, NOTHING)
    only_bias = estimate_article_tokens(article, ArticleAnalysis(summary="s"))
    only_summary = estimate_article_tokens(
        article, ArticleAnalysis(bias=BiasAssessment(label="None"))
    )
    assert both == only_bias + only_summary
    assert only_summary > only_bias  # summaries are budgeted more output


def test_no_budget_selects_everything(make_article):
    articles = [make_article(i, content="x" * 10_000) for i in range(10)]
    plan = plan_batch(articles, {a.id: NOTHING for a in articles}, max_tokens=None)
    assert plan.selected == articles
    assert plan.skipped == []


def test_once_exhausted_cheaper_later_articles_do_not_jump_the_queue(make_article):
    articles = [
        make_article(0, content="x" * 4000),
        make_article(1, content="x" * 40_000),  # does not fit
        make_article(2, content="x" * 40),  # would fit, but lower priority
    ]
    plan = plan_batch(articles, {a.id: NOTHING for a in articles}, max_tokens=7000)  # 0 and 2 would both fit
    assert [a.id for a in plan.selected] == [0]
    assert [a.id for a in plan.skipped] == [1, 2]


def test_content_to_be_scraped_is_budgeted_at_the_cap(make_article):
    snippet = make_article(content="short")
    assert budget.estimate_content_tokens(snippet) == 2
    assert (
        budget.estimate_content_tokens(snippet, fetch_below=600)
        == budget.MAX_CONTENT_CHARS // budget.CHARS_PER_TOKEN
    )


def test_content_estimate_never_exceeds_the_cap(make_article):
    huge = make_article(content="x" * 100_000)
    assert (
        budget.estimate_content_tokens(huge)
        == budget.MAX_CONTENT_CHARS // budget.CHARS_PER_TOKEN
    )
