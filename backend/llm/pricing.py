from backend.llm.recording import UsageTotals
from backend.models import LLMUsage


def estimate_cost(totals: UsageTotals, prices: tuple[float, float] | None) -> float | None:
    """Cost of ``totals`` at (input, output) prices per 1M tokens, or None."""
    if prices is None:
        return None
    input_price, output_price = prices
    return (totals.input_tokens * input_price + totals.output_tokens * output_price) / 1_000_000


def usage_summary(
    totals: UsageTotals,
    prices: tuple[float, float] | None,
    currency: str,
    model: str | None,
) -> LLMUsage:
    cost = estimate_cost(totals, prices)
    return LLMUsage(
        calls=totals.calls,
        input_tokens=totals.input_tokens,
        output_tokens=totals.output_tokens,
        cost=cost,
        currency=currency if cost is not None else None,
        model=model,
    )
