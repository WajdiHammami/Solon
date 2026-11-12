"""Settings for the external-agreement evaluation. Run everything from the repo root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTLETS_CSV = ROOT / "outlets.csv"
DATA_DIR = ROOT / "data"  # gitignored: contains article text
DATASET = DATA_DIR / "dataset.jsonl"
COLLECT_STATE = DATA_DIR / "collect_state.json"
RUNS_DIR = DATA_DIR / "runs"
RESULTS_DIR = ROOT / "results"

# The same politically contested topics for every outlet, so differences come
# from framing rather than topic choice. NewsAPI boolean query syntax.
TOPICS: dict[str, str] = {
    "immigration": "immigration OR border OR deportation",
    "economy": "inflation OR tariffs OR economy",
    "elections": "election OR campaign OR voters",
    "climate": '"climate change" OR emissions OR "clean energy"',
    "guns": '"gun control" OR "Second Amendment" OR firearms',
    "healthcare": 'healthcare OR Medicaid OR "health insurance"',
}

ARTICLES_PER_QUERY = 5  # per outlet x topic, so up to 30 per outlet
SCRAPE_WORKERS = 8
MIN_CONTENT_CHARS = 600  # same threshold the app uses before analysis

LLM_CONCURRENCY = 4
# Waits (seconds) before retrying a retryable LLM error (rate limit, timeout).
# Free tiers have low tokens-per-minute limits, so back off generously.
RETRY_DELAYS = (20, 60, 120)
MIN_POLITICAL_PER_OUTLET = 5  # fewer -> outlet excluded from the statistics

# AllSides ratings may be entered as a category name or as the numeric Bias
# Meter score (-6 .. +6). Categories map onto Solon's lean scale; scores map
# to categories with AllSides' published bands (allsides.com/about/
# media-bias-rating-methods): Left -6.00..-3.00, Lean Left -2.99..-1.00,
# Center -0.99..+0.99, Lean Right +1.00..+2.99, Right +3.00..+6.00.
ALLSIDES_SCORE_RANGE = (-6.0, 6.0)
ALLSIDES_SCALE: dict[str, int] = {
    "left": -2,
    "lean left": -1,
    "center": 0,
    "lean right": 1,
    "right": 2,
}

BOOTSTRAP_SAMPLES = 2000
SEED = 7
