"""Run bias detection over the frozen dataset under three conditions.

    python -m evaluation.run_bias                       # all conditions
    python -m evaluation.run_bias --conditions blinded --limit 20

- ``blinded``:    production ``tasks.detect_bias`` (no source, no URL, outlet
                  name stripped) - what Solon ships.
- ``unblinded``:  the same rubric, but the model also sees source, URL and the
                  raw text - measures how much the outlet's identity sways it.
- ``reputation``: the outlet's name and website only, no article - measures
                  what the model already "knows" about the outlet.

Results append to ``data/runs/<condition>.jsonl`` keyed by URL (or outlet for
``reputation``); re-running skips finished items and retries failed ones.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from backend.llm.base import LLMClient
from backend.llm.errors import LLMError, LLMInvalidOutputError
from backend.llm.models import GenerationRequest, Message, Role
from backend.llm.recording import UsageRecordingLLM
from backend.models import Article, BiasAssessment
from backend.workflows import prompts, tasks
from backend.workflows.blinding import blind, blind_title, outlet_aliases
from evaluation import config
from evaluation.files import Outlet, append_jsonl, load_outlets, read_jsonl

CONDITIONS = ("blinded", "unblinded", "reputation")

UNBLINDED_ARTICLE = """Title: {title}
Source: {source}
URL: {url}
Content: {content}"""

REPUTATION_SYSTEM = """You are a media analyst. You are given only the name and
website of a news outlet, not any article. Rate the typical political lean of
its news coverage on the US left-right spectrum.

Respond with a single JSON object of this shape:
{"lean": <-2, -1, 0, 1, or 2>, "explanation": "<at most 2 sentences>"}
-2 Left, -1 Lean Left, 0 Center, 1 Lean Right, 2 Right."""


class ReputationRating(BaseModel):
    lean: int = Field(ge=-2, le=2)
    explanation: str | None = None


def _article(record: dict) -> Article:
    return Article(
        id=0,
        title=record["title"],
        url=record["url"],
        source_name=record["source_name"],
        published_at=record["published_at"],
        content=record["content"],
    )


def leaks_outlet(record: dict) -> bool:
    """Does the blinded prompt still name the outlet (by our list's name/domain)?"""
    title = blind_title(record["title"], record["source_name"], record["url"])
    content = blind(record["content"][: tasks.MAX_CONTENT_CHARS], record["source_name"], record["url"])
    text = f"{title}\n{content}".lower()
    aliases = outlet_aliases(record["outlet_name"], f"https://{record['outlet']}")
    return any(alias.lower() in text for alias in aliases)


async def _with_retries(call, delays=None):
    """Run ``call()``; on a retryable LLM error wait and try again."""
    delays = config.RETRY_DELAYS if delays is None else delays
    for delay in (*delays, None):
        try:
            return await call()
        except LLMError as e:
            if not e.retryable or delay is None:
                raise
            await asyncio.sleep(delay)


async def _ask_json(llm: LLMClient, system: str, user: str, model_cls):
    response = await llm.ainvoke(
        GenerationRequest(
            messages=[Message(role=Role.SYSTEM, content=system), Message(role=Role.USER, content=user)],
            json_output=True,
        )
    )
    try:
        return model_cls.model_validate_json(response.content)
    except ValidationError as e:
        raise LLMInvalidOutputError(f"malformed JSON: {response.content[:200]!r}") from e


async def _bias_record(llm: LLMClient, record: dict, condition: str) -> dict:
    base = {"url": record["url"], "outlet": record["outlet"], "topic": record["topic"]}
    try:
        if condition == "blinded":
            bias = await _with_retries(lambda: tasks.detect_bias(llm, _article(record)))
            base["leak"] = leaks_outlet(record)
        else:
            user = UNBLINDED_ARTICLE.format(
                title=record["title"],
                source=record["source_name"],
                url=record["url"],
                content=record["content"][: tasks.MAX_CONTENT_CHARS],
            )
            bias = await _with_retries(lambda: _ask_json(llm, prompts.BIAS_SYSTEM, user, BiasAssessment))
    except LLMError as e:
        return {**base, "error": f"{type(e).__name__}: {e}"}
    return {**base, "label": bias.label, "political": bias.political, "lean": bias.lean}


async def _reputation_record(llm: LLMClient, outlet: Outlet) -> dict:
    base = {"outlet": outlet.domain}
    try:
        rating = await _with_retries(lambda: _ask_json(
            llm, REPUTATION_SYSTEM, f"Outlet: {outlet.name}\nWebsite: {outlet.domain}", ReputationRating
        ))
    except LLMError as e:
        return {**base, "error": f"{type(e).__name__}: {e}"}
    return {**base, "lean": rating.lean}


def _pending(items: list, key: str, done_path: Path) -> list:
    finished = {r[key] for r in read_jsonl(done_path) if "error" not in r}
    return [item for item in items if (item[key] if isinstance(item, dict) else getattr(item, key)) not in finished]


async def run_condition(
    llm: LLMClient,
    condition: str,
    dataset: list[dict],
    outlets: list[Outlet],
    runs_dir: Path,
    concurrency: int = config.LLM_CONCURRENCY,
    limit: int | None = None,
) -> dict:
    """Process the pending items of one condition; returns a small summary."""
    out_path = runs_dir / f"{condition}.jsonl"
    if condition == "reputation":
        dataset_outlets = {r["outlet"] for r in dataset}
        items = _pending([o for o in outlets if o.domain in dataset_outlets], "domain", out_path)
    else:
        items = _pending([r for r in dataset if r["usable"]], "url", out_path)
    if limit is not None:
        items = items[:limit]

    semaphore = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    errors = 0

    async def process(item):
        nonlocal errors
        async with semaphore:
            if condition == "reputation":
                result = await _reputation_record(llm, item)
            else:
                result = await _bias_record(llm, item, condition)
        result.update(model=llm.config.model, prompt_version=prompts.BIAS_VERSION,
                      at=datetime.now(timezone.utc).isoformat())
        errors += "error" in result
        async with lock:  # one writer at a time keeps lines intact
            append_jsonl(out_path, [result])

    await asyncio.gather(*(process(item) for item in items))
    return {"condition": condition, "processed": len(items), "errors": errors}


async def _main(conditions: list[str], limit: int | None) -> int:
    from backend.config import get_settings
    from backend.llm.factory import create_llm

    dataset = read_jsonl(config.DATASET)
    if not dataset:
        print("No dataset yet: run `python -m evaluation.collect` first.")
        return 1
    outlets = load_outlets(config.OUTLETS_CSV)
    llm = UsageRecordingLLM(create_llm(get_settings()))
    for condition in conditions:
        summary = await run_condition(llm, condition, dataset, outlets, config.RUNS_DIR, limit=limit)
        usage = llm.reset()
        summary.update(model=llm.config.model, calls=usage.calls,
                       input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
        meta_path = config.RUNS_DIR / f"{condition}.meta.jsonl"
        append_jsonl(meta_path, [{**summary, "at": datetime.now(timezone.utc).isoformat()}])
        print(json.dumps(summary))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--limit", type=int, help="max items per condition in this run")
    args = parser.parse_args(argv)
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = set(conditions) - set(CONDITIONS)
    if unknown:
        parser.error(f"unknown condition(s): {', '.join(sorted(unknown))}")
    return asyncio.run(_main(conditions, args.limit))


if __name__ == "__main__":
    sys.exit(main())
