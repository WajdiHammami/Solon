"""Tests for the token-usage recording LLM wrapper."""

import pytest

from backend.llm.models import GenerationRequest, GenerationResponse, Message, Role, Usage
from backend.llm.recording import UsageRecordingLLM
from backend.tests.conftest import ScriptedLLM

pytestmark = pytest.mark.anyio


class UsageLLM(ScriptedLLM):
    def invoke(self, request):
        response = super().invoke(request)
        usage = None if "no-usage" in request.messages[-1].content else Usage(input_tokens=10, output_tokens=3)
        return GenerationResponse(content=response.content, model="m", usage=usage)


def _request(text="Title: x\nhello"):
    return GenerationRequest(messages=[Message(role=Role.SYSTEM, content="sys"), Message(role=Role.USER, content=text)])


async def test_sums_usage_across_sync_and_async_calls():
    llm = UsageRecordingLLM(UsageLLM())
    llm.invoke(_request())
    await llm.ainvoke(_request())
    assert (llm.totals.calls, llm.totals.input_tokens, llm.totals.output_tokens) == (2, 20, 6)
    assert llm.totals.total_tokens == 26


async def test_counts_calls_without_usage():
    llm = UsageRecordingLLM(UsageLLM())
    await llm.ainvoke(_request("Title: x\nno-usage"))
    assert llm.totals.calls == 1 and llm.totals.calls_without_usage == 1
    assert llm.totals.total_tokens == 0


async def test_reset_returns_totals_and_restarts():
    llm = UsageRecordingLLM(UsageLLM())
    await llm.ainvoke(_request())
    first = llm.reset()
    assert first.calls == 1 and llm.totals.calls == 0


async def test_streams_pass_through_and_config_is_inner():
    inner = UsageLLM()
    llm = UsageRecordingLLM(inner)
    assert list(llm.stream(_request())) == ["summary of x"]
    assert [t async for t in llm.astream(_request())] == ["summary of x"]
    assert llm.config is not None and llm.totals.calls == 0


# --- per-request metering ----------------------------------------------------------

import asyncio

from backend.config import Settings
from backend.llm.pricing import estimate_cost, usage_summary
from backend.llm.recording import MeteredLLM, UsageTotals, track_usage


async def test_metered_counts_only_inside_track_usage():
    llm = MeteredLLM(UsageLLM())
    await llm.ainvoke(_request())  # outside: not counted anywhere
    with track_usage() as totals:
        await llm.ainvoke(_request())
        llm.invoke(_request())
    assert (totals.calls, totals.input_tokens, totals.output_tokens) == (2, 20, 6)


async def test_concurrent_requests_get_separate_tallies():
    llm = MeteredLLM(UsageLLM())

    async def request(n_calls):
        with track_usage() as totals:
            await asyncio.gather(*(llm.ainvoke(_request()) for _ in range(n_calls)))
            await asyncio.sleep(0)
            return totals.calls

    assert await asyncio.gather(request(1), request(3)) == [1, 3]


async def test_calls_in_spawned_tasks_are_counted():
    llm = MeteredLLM(UsageLLM())
    with track_usage() as totals:
        await asyncio.create_task(llm.ainvoke(_request()))  # tasks inherit the context
    assert totals.calls == 1


def test_cost_estimate():
    totals = UsageTotals(calls=1, input_tokens=2_000_000, output_tokens=500_000)
    assert estimate_cost(totals, (0.40, 1.60)) == pytest.approx(0.8 + 0.8)
    assert estimate_cost(totals, None) is None


def test_usage_summary_without_prices_has_no_cost_or_currency():
    summary = usage_summary(UsageTotals(calls=2, input_tokens=10, output_tokens=5), None, "USD", "m")
    assert (summary.calls, summary.cost, summary.currency, summary.model) == (2, None, None, "m")


def test_prices_follow_active_provider():
    s = Settings(_env_file=None, llm_provider="azure", azure_price_input_per_1m=0.4,
                 azure_price_output_per_1m=1.6, groq_price_input_per_1m=0.15,
                 groq_price_output_per_1m=0.6)
    assert s.llm_prices() == (0.4, 1.6)
    assert s.model_copy(update={"llm_provider": "groq"}).llm_prices() == (0.15, 0.6)
    assert Settings(_env_file=None, azure_price_input_per_1m=0.4).llm_prices() is None  # incomplete
