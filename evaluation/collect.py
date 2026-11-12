"""Build the frozen evaluation dataset from NewsAPI (resumable across days).

    python -m evaluation.collect --probe     # 1 request per outlet: coverage check
    python -m evaluation.collect             # outlets x topics -> data/dataset.jsonl

NewsAPI's free plan allows 100 requests a day. Each outlet x topic pair costs
one request; finished pairs are recorded in ``data/collect_state.json``, so
when the quota runs out the run stops cleanly and the next run continues.
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from backend.news_providers.base import NewsProviderError
from evaluation import config
from evaluation.files import Outlet, append_jsonl, load_outlets, read_jsonl


def _load_state(path: Path) -> set[str]:
    return set(json.loads(path.read_text())["done"]) if path.exists() else set()


def _save_state(path: Path, done: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"done": sorted(done)}, indent=1))


def collect(
    provider,
    outlets: list[Outlet],
    topics: dict[str, str],
    dataset_path: Path,
    state_path: Path,
    per_query: int = config.ARTICLES_PER_QUERY,
    max_requests: int | None = None,
    extract: Callable[[str], str] | None = None,
    workers: int = config.SCRAPE_WORKERS,
) -> dict:
    """Fetch every unfinished outlet x topic pair; returns a run summary.

    Stops early (``stopped_reason`` set) on a provider error such as the
    daily quota, or after ``max_requests``.
    """
    extract = extract or provider.extract_content
    done = _load_state(state_path)
    seen_urls = {r["url"] for r in read_jsonl(dataset_path)}
    summary = {"requests": 0, "new_articles": 0, "stopped_reason": None}

    for outlet in outlets:
        for topic, query in topics.items():
            key = f"{outlet.domain}|{topic}"
            if key in done:
                continue
            if max_requests is not None and summary["requests"] >= max_requests:
                summary["stopped_reason"] = f"request limit ({max_requests}) reached"
                return summary
            try:
                articles = provider.fetch_articles(query, page_size=per_query, domains=[outlet.domain])
            except NewsProviderError as e:
                summary["stopped_reason"] = str(e)
                return summary
            summary["requests"] += 1

            fresh = [a for a in articles if a.url not in seen_urls]
            with ThreadPoolExecutor(max_workers=workers) as pool:
                texts = list(pool.map(extract, [a.url for a in fresh]))
            now = datetime.now(timezone.utc).isoformat()
            records = []
            for article, text in zip(fresh, texts):
                content = text or ""
                records.append(
                    {
                        "url": article.url,
                        "outlet": outlet.domain,
                        "outlet_name": outlet.name,
                        "source_name": article.source_name,
                        "topic": topic,
                        "title": article.title,
                        "published_at": article.published_at.isoformat(),
                        "snippet": article.content,
                        "content": content,
                        "usable": len(content) >= config.MIN_CONTENT_CHARS,
                        "fetched_at": now,
                    }
                )
                seen_urls.add(article.url)
            append_jsonl(dataset_path, records)
            summary["new_articles"] += len(records)
            done.add(key)
            _save_state(state_path, done)
    return summary


def probe(
    provider, outlets: list[Outlet], query: str, extract: Callable[[str], str] | None = None
) -> list[dict]:
    """One small request per outlet: does NewsAPI cover it, and can we scrape it?

    Scraping is checked with a normal request; outlets that block it (e.g.
    HTTP 403) are reported, not worked around.
    """
    extract = extract or provider.extract_content
    results = []
    for outlet in outlets:
        try:
            found = provider.fetch_articles(query, page_size=3, domains=[outlet.domain])
        except NewsProviderError as e:
            results.append({"domain": outlet.domain, "error": str(e)})
            break  # quota or key problem: further requests would fail too
        usable = sum(len(extract(a.url) or "") >= config.MIN_CONTENT_CHARS for a in found)
        results.append({"domain": outlet.domain, "found": len(found), "scrapable": usable})
    return results


def coverage(dataset_path: Path) -> dict[str, Counter]:
    by_outlet: dict[str, Counter] = {}
    for record in read_jsonl(dataset_path):
        counts = by_outlet.setdefault(record["outlet"], Counter())
        counts["articles"] += 1
        counts["usable"] += record["usable"]
    return by_outlet


def main(argv: list[str] | None = None) -> int:
    from backend.config import get_settings
    from backend.news_providers.newsapi_provider import NewsAPIProvider

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--probe", action="store_true", help="check NewsAPI coverage per outlet")
    parser.add_argument("--outlets", help="comma-separated domains to restrict to")
    parser.add_argument("--topics", help="comma-separated topic names to restrict to")
    parser.add_argument("--max-requests", type=int, help="stop after this many NewsAPI requests")
    args = parser.parse_args(argv)

    outlets = load_outlets(config.OUTLETS_CSV)
    if args.outlets:
        wanted = {d.strip().lower() for d in args.outlets.split(",")}
        outlets = [o for o in outlets if o.domain in wanted]
    topics = config.TOPICS
    if args.topics:
        topics = {t: q for t, q in topics.items() if t in args.topics.split(",")}

    provider = NewsAPIProvider(api_key=get_settings().newsapi_key, language="en")

    if args.probe:
        print(f"{'outlet':28} found scrapable")
        for r in probe(provider, outlets, next(iter(config.TOPICS.values()))):
            if "error" in r:
                print(f"{r['domain']:28} error: {r['error']}")
            else:
                print(f"{r['domain']:28} {r['found']:5} {r['scrapable']:9}")
        return 0

    summary = collect(
        provider, outlets, topics, config.DATASET, config.COLLECT_STATE,
        max_requests=args.max_requests,
    )
    print(f"requests: {summary['requests']}, new articles: {summary['new_articles']}")
    if summary["stopped_reason"]:
        print(f"stopped early: {summary['stopped_reason']} (run again later to continue)")
    selected = {f"{o.domain}|{t}" for o in outlets for t in topics}
    print(f"pairs done: {len(selected & _load_state(config.COLLECT_STATE))}/{len(selected)}")
    print(f"\n{'outlet':28} articles usable")
    for domain, counts in sorted(coverage(config.DATASET).items()):
        print(f"{domain:28} {counts['articles']:8} {counts['usable']:6}")
    return 2 if summary["stopped_reason"] else 0


if __name__ == "__main__":
    sys.exit(main())
