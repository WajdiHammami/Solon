"""Compare Solon's outlet-level lean with AllSides / Ad Fontes ratings.

    python -m evaluation.report          # -> results/external_agreement.{md,json}

Per outlet, Solon's lean is the mean over its *political* articles (non-
political ones have no lean). Outlets with fewer than
``MIN_POLITICAL_PER_OUTLET`` political articles are excluded and listed.
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone

from backend.workflows import prompts
from evaluation import config, stats
from evaluation.files import Outlet, load_outlets, read_jsonl

LEAN_NAMES = {-2: "Left", -1: "Lean Left", 0: "Center", 1: "Lean Right", 2: "Right"}


def allsides_score(outlet: Outlet) -> float | None:
    """The AllSides rating as a number: the Bias Meter score if one was
    entered, otherwise the category on the -2..2 scale. Used for rank
    correlation, where only the order matters."""
    rating = outlet.allsides_rating.strip()
    if not rating:
        return None
    if rating.lower() in config.ALLSIDES_SCALE:
        return float(config.ALLSIDES_SCALE[rating.lower()])
    try:
        return float(rating)
    except ValueError:
        return None


def allsides_class(outlet: Outlet) -> int | None:
    """The AllSides category on Solon's -2..2 lean scale."""
    rating = outlet.allsides_rating.strip().lower()
    if rating in config.ALLSIDES_SCALE:
        return config.ALLSIDES_SCALE[rating]
    score = allsides_score(outlet)
    return None if score is None else score_to_class(score)


def score_to_class(score: float) -> int:
    """AllSides Bias Meter score -> category, using AllSides' published bands."""
    if score <= -3.0:
        return -2
    if score <= -1.0:
        return -1
    if score < 1.0:
        return 0
    if score < 3.0:
        return 1
    return 2


def outlet_leans(runs: list[dict], min_articles: int) -> dict[str, dict]:
    """Per-outlet aggregate of one article-level condition."""
    by_outlet: dict[str, dict] = {}
    for r in runs:
        if "error" in r:
            continue
        entry = by_outlet.setdefault(r["outlet"], {"analyzed": 0, "leans": []})
        entry["analyzed"] += 1
        if r.get("political") and r.get("lean") is not None:
            entry["leans"].append(r["lean"])
    for i, (outlet, entry) in enumerate(sorted(by_outlet.items())):
        leans = entry["leans"]
        entry["n_political"] = len(leans)
        entry["included"] = len(leans) >= min_articles
        entry["mean"] = stats.mean(leans)
        entry["ci"] = stats.bootstrap_ci(stats.mean, leans, config.BOOTSTRAP_SAMPLES, config.SEED + i)
    return by_outlet


def _correlation(pairs: list[tuple[float, float]]) -> dict:
    rho = stats.spearman([a for a, _ in pairs], [b for _, b in pairs])
    ci = stats.bootstrap_ci(
        lambda sample: stats.spearman([a for a, _ in sample], [b for _, b in sample]),
        pairs, config.BOOTSTRAP_SAMPLES, config.SEED,
    )
    return {"spearman": rho, "ci": ci, "n": len(pairs)}


def compare(predicted: dict[str, float], outlets: list[Outlet]) -> dict:
    """Agreement of per-outlet predictions with both rating sources."""
    rated = [o for o in outlets if o.domain in predicted and allsides_score(o) is not None]
    allsides = [(predicted[o.domain], allsides_score(o)) for o in rated]
    adfontes = [(predicted[o.domain], o.adfontes_bias) for o in outlets
                if o.domain in predicted and o.adfontes_bias is not None]
    classes = [stats.to_class(predicted[o.domain]) for o in rated]
    actual = [allsides_class(o) for o in rated]
    return {
        "allsides": {**_correlation(allsides), **stats.agreement(classes, actual),
                     "confusion": stats.confusion(classes, actual)},
        "adfontes": _correlation(adfontes),
    }


def build_report(
    outlets: list[Outlet],
    dataset: list[dict],
    runs: dict[str, list[dict]],
    min_articles: int = config.MIN_POLITICAL_PER_OUTLET,
) -> dict:
    blinded = outlet_leans(runs.get("blinded", []), min_articles)
    unblinded = outlet_leans(runs.get("unblinded", []), min_articles)
    reputation = {r["outlet"]: r["lean"] for r in runs.get("reputation", []) if "error" not in r}

    included = {d: e["mean"] for d, e in blinded.items() if e["included"]}
    rated = [o for o in outlets if allsides_class(o) is not None and o.domain in included]
    actual = [allsides_class(o) for o in rated]

    results: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompts.BIAS_VERSION,
        # Only models that produced results; failed attempts don't count.
        "models": sorted({r["model"] for rs in runs.values() for r in rs
                          if r.get("model") and "error" not in r}),
        "min_political_per_outlet": min_articles,
        "outlets_included": sorted(included),
        "outlets_excluded": sorted(d for d, e in blinded.items() if not e["included"]),
        "blinded": compare(included, outlets),
        "baselines": {
            "always_center": stats.agreement([0] * len(actual), actual),
            "random": stats.random_baseline(actual),
            "reputation_only": compare({d: v for d, v in reputation.items() if d in included}, outlets),
        },
    }

    # How much the two reference raters agree with each other: a realistic
    # ceiling for Solon (computed over all outlets rated by both).
    both = [(allsides_score(o), o.adfontes_bias) for o in outlets
            if allsides_score(o) is not None and o.adfontes_bias is not None]
    results["reference_agreement"] = _correlation(both)

    unblinded_included = {d: e["mean"] for d, e in unblinded.items() if e["included"]}
    shared = sorted(set(included) & set(unblinded_included))
    results["unblinded"] = compare(unblinded_included, outlets)
    results["blinding_effect"] = {
        "outlets": len(shared),
        "mean_abs_shift": stats.mean([abs(unblinded_included[d] - included[d]) for d in shared]),
    }
    results["blinded_vs_reputation_spearman"] = stats.spearman(
        [included[d] for d in included if d in reputation],
        [reputation[d] for d in included if d in reputation],
    )

    blinded_runs = [r for r in runs.get("blinded", []) if "error" not in r]
    results["leak_rate"] = (stats.mean([bool(r.get("leak")) for r in blinded_runs])
                            if blinded_runs else math.nan)
    results["errors"] = {c: sum("error" in r for r in rs) for c, rs in runs.items()}

    collected: dict[str, dict] = {}
    for r in dataset:
        entry = collected.setdefault(r["outlet"], {"articles": 0, "usable": 0})
        entry["articles"] += 1
        entry["usable"] += r["usable"]
    results["outlets"] = [
        {
            "domain": o.domain,
            "name": o.name,
            "articles": collected.get(o.domain, {}).get("articles", 0),
            "usable": collected.get(o.domain, {}).get("usable", 0),
            "political": blinded.get(o.domain, {}).get("n_political", 0),
            "blinded_mean": blinded.get(o.domain, {}).get("mean", math.nan),
            "blinded_ci": blinded.get(o.domain, {}).get("ci", (math.nan, math.nan)),
            "unblinded_mean": unblinded.get(o.domain, {}).get("mean", math.nan),
            "reputation": reputation.get(o.domain),
            "allsides": _allsides_display(o),
            "adfontes": o.adfontes_bias,
            "included": o.domain in included,
        }
        for o in outlets
    ]
    return results


def _allsides_display(outlet: Outlet) -> str | None:
    rating = outlet.allsides_rating.strip()
    if not rating:
        return None
    if rating.lower() in config.ALLSIDES_SCALE:
        return rating
    cls = allsides_class(outlet)
    return f"{rating} ({LEAN_NAMES[cls]})" if cls is not None else rating


def _json_safe(value):
    """NaN -> null (valid JSON), tuples -> lists."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _f(value, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    return f"{value:+.{digits}f}" if isinstance(value, float) else str(value)


def _abs(value) -> str:
    return "–" if value is None or math.isnan(value) else f"{value:.2f}"


def _pct(value) -> str:
    return "–" if value is None or math.isnan(value) else f"{value:.0%}"


def _ci(ci) -> str:
    lo, hi = ci
    return "–" if math.isnan(lo) else f"[{lo:+.2f}, {hi:+.2f}]"


def render_markdown(r: dict) -> str:
    b = r["blinded"]
    lines = [
        "# External agreement: Solon lean vs AllSides / Ad Fontes",
        "",
        f"Generated {r['generated_at'][:16].replace('T', ' ')} UTC · bias prompt `{r['prompt_version']}` · "
        f"model(s) {', '.join(r['models']) or '–'} · ≥{r['min_political_per_outlet']} political articles per outlet",
        "",
        *(["> **Warning:** results come from more than one model; rerun with a single "
            "model for a valid comparison.", ""] if len(r["models"]) > 1 else []),
        "## Headline (blinded, as shipped)",
        "",
        "| Metric | vs AllSides | vs Ad Fontes |",
        "|---|---|---|",
        f"| Spearman ρ (95% CI) | {_f(b['allsides']['spearman'])} {_ci(b['allsides']['ci'])} | "
        f"{_f(b['adfontes']['spearman'])} {_ci(b['adfontes']['ci'])} |",
        f"| Outlets | {b['allsides']['n']} | {b['adfontes']['n']} |",
        f"| Exact class agreement | {_pct(b['allsides']['exact'])} | – |",
        f"| Within one class | {_pct(b['allsides']['within_one'])} | – |",
        "",
        f"Reference ceiling: AllSides and Ad Fontes agree with each other at ρ = "
        f"{_f(r['reference_agreement']['spearman'])} {_ci(r['reference_agreement']['ci'])} "
        f"over {r['reference_agreement']['n']} outlets.",
        "",
        "## Baselines (vs AllSides)",
        "",
        "| Predictor | Spearman ρ | Exact | Within one |",
        "|---|---|---|---|",
        f"| **Solon, blinded** | {_f(b['allsides']['spearman'])} | {_pct(b['allsides']['exact'])} | {_pct(b['allsides']['within_one'])} |",
        f"| Solon, unblinded (sees source + URL) | {_f(r['unblinded']['allsides']['spearman'])} | "
        f"{_pct(r['unblinded']['allsides']['exact'])} | {_pct(r['unblinded']['allsides']['within_one'])} |",
        f"| Reputation only (outlet name, no article) | {_f(r['baselines']['reputation_only']['allsides']['spearman'])} | "
        f"{_pct(r['baselines']['reputation_only']['allsides']['exact'])} | "
        f"{_pct(r['baselines']['reputation_only']['allsides']['within_one'])} |",
        f"| Always \"Center\" | – | {_pct(r['baselines']['always_center']['exact'])} | "
        f"{_pct(r['baselines']['always_center']['within_one'])} |",
        f"| Random class (expected) | – | {_pct(r['baselines']['random']['exact'])} | "
        f"{_pct(r['baselines']['random']['within_one'])} |",
        "",
        f"Blinding effect: mean |unblinded − blinded| = {_abs(r['blinding_effect']['mean_abs_shift'])} "
        f"lean points over {r['blinding_effect']['outlets']} outlets. "
        f"Blinded vs reputation-only ρ = {_f(r['blinded_vs_reputation_spearman'])}. "
        f"Blinded prompts still naming the outlet: {_pct(r['leak_rate'])}.",
        "",
        "## Confusion matrix (blinded, rows = AllSides, columns = Solon)",
        "",
        "| | " + " | ".join(LEAN_NAMES.values()) + " |",
        "|---|" + "---|" * 5,
    ]
    for i, row in enumerate(b["allsides"]["confusion"]):
        lines.append(f"| {LEAN_NAMES[i - 2]} | " + " | ".join(str(c) for c in row) + " |")
    lines += [
        "",
        "## Per outlet",
        "",
        "| Outlet | Usable / collected | Political | Solon blinded (95% CI) | Unblinded | Reputation | AllSides | Ad Fontes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for o in r["outlets"]:
        mark = "" if o["included"] else " *(excluded)*"
        lines.append(
            f"| {o['name']}{mark} | {o['usable']} / {o['articles']} | {o['political']} | "
            f"{_f(o['blinded_mean'])} {_ci(o['blinded_ci'])} | {_f(o['unblinded_mean'])} | "
            f"{_f(None if o['reputation'] is None else float(o['reputation']))} | {o['allsides'] or '–'} | "
            f"{_f(o['adfontes'], 1)} |"
        )
    lines += [
        "",
        "Lean scale: −2 Left · −1 Lean Left · 0 Center · +1 Lean Right · +2 Right. "
        "Ratings were entered by hand from allsides.com and adfontesmedia.com (see `outlets.csv` for access dates). "
        "Errors per condition: " + ", ".join(f"{c} {n}" for c, n in r["errors"].items()) + ".",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-articles", type=int, default=config.MIN_POLITICAL_PER_OUTLET)
    args = parser.parse_args(argv)

    outlets = load_outlets(config.OUTLETS_CSV)
    if not any(o.allsides_rating or o.adfontes_bias is not None for o in outlets):
        print("Note: no ratings in evaluation/outlets.csv yet - correlations will be empty.")
    runs = {c: read_jsonl(config.RUNS_DIR / f"{c}.jsonl") for c in ("blinded", "unblinded", "reputation")}
    results = build_report(outlets, read_jsonl(config.DATASET), runs, args.min_articles)

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.RESULTS_DIR / "external_agreement.json").write_text(json.dumps(_json_safe(results), indent=2, default=str))
    markdown = render_markdown(results)
    (config.RESULTS_DIR / "external_agreement.md").write_text(markdown)
    print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
