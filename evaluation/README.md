# Evaluation: external agreement of Solon's bias lean

**Question.** When Solon reads an outlet's political articles *without being
told who published them*, does its average left–right lean per outlet agree
with established media-bias ratings (AllSides, Ad Fontes Media)?

Results: [`results/external_agreement.md`](results/external_agreement.md)

## Method

1. **Outlets.** 13 US outlets spanning the spectrum ([`outlets.csv`](outlets.csv)),
   with ratings **taken from the rating sites' own pages** (URL and access date
   recorded per outlet). A probe on 2026-11-12 narrowed 30 candidates:
   - no NewsAPI results: MSNBC, The New York Times, ABC News, Politico, Reuters,
     Axios, The Wall Street Journal, The Washington Times, National Review,
     The Daily Wire, Newsmax;
   - full text not retrievable (the site refuses automated requests, e.g. HTTP
     403; we do not circumvent this): The Atlantic, The Washington Post, CNN, Associated Press, The Hill, USA Today.
2. **Articles.** For each outlet, the same 6 politically contested topics
   (immigration, economy, elections, climate, guns, healthcare;
   [`config.py`](config.py)), up to 5 articles per outlet × topic via NewsAPI
   restricted to the outlet's domain. Full text is scraped; articles under 600
   characters (paywalls, failed scrapes) are marked unusable. The dataset is
   frozen in `data/dataset.jsonl` so every later step is reproducible offline.
3. **Scoring.** Solon's production bias task returns, per article, `political`
   (is it about politics/policy?) and `lean` (−2 Left … +2 Right, AllSides'
   five categories). The task is **blinded**: the model sees only title and
   text, with the outlet's name and domain stripped, so it must judge the
   article rather than the outlet's reputation.
4. **Aggregation.** An outlet's lean is the mean over its political articles,
   with a bootstrap 95% CI. Outlets with fewer than 5 political articles are
   excluded and listed.
5. **Metrics.** Spearman ρ between outlet lean and AllSides (mapped to −2…+2)
   and Ad Fontes (numeric bias score), each with a bootstrap 95% CI over
   outlets; exact and within-one-class agreement with AllSides; confusion matrix.
   AllSides ratings may be entered as categories or Bias Meter scores (−6…+6,
   mapped to categories with AllSides' published bands). As a ceiling, the
   report also gives how well AllSides and Ad Fontes agree with each other.

### Controls

| Condition | What the model sees | Why |
|---|---|---|
| **Blinded** (headline) | title + text, outlet identity removed | what Solon ships |
| Unblinded | title + text + source name + URL | how much knowing the outlet sways the score |
| Reputation only | outlet name + website, no article | what the model already "knows"; if blinded ≈ reputation, it may be recognizing the outlet anyway |
| Always "Center" / random | – | floors any real result must beat |

The report also gives the **leak rate**: the share of blinded prompts that still
contain the outlet's name or domain (e.g. syndicated copies hosted elsewhere).

## Running it

From the repository root, with `backend/.env` configured (NewsAPI + LLM keys):

```bash
# 0. Check which outlets NewsAPI actually covers (1 request per outlet).
backend/.venv/bin/python -m evaluation.collect --probe

# 1. Collect the dataset. NewsAPI's free plan allows 100 requests/day and each
#    outlet x topic costs one; the run stops cleanly at the quota and the next
#    run continues where it left off (~2 days for the full set).
backend/.venv/bin/python -m evaluation.collect

# 2. Score every usable article (blinded, unblinded) and every outlet
#    (reputation). Resumable; failed items are retried on the next run.
backend/.venv/bin/python -m evaluation.run_bias

# 3. Build the report (ratings come from outlets.csv).
backend/.venv/bin/python -m evaluation.report
```

`allsides_rating` is either a category (`Left`, `Lean Left`, `Center`,
`Lean Right`, `Right`) or the AllSides Bias Meter score (−6…+6; the current
file uses scores). `adfontes_bias` is the numeric overall bias score from
adfontesmedia.com (negative = left). Every value needs the date accessed and
the URL of the page it was read from (`*_accessed`, `*_url`); a test enforces
this. Token usage per condition is logged in `data/runs/*.meta.jsonl`.

All rows of one run must come from a single model and prompt version; the
report warns otherwise. To start over, delete `data/runs/` (keeps the dataset).

`data/` is gitignored because it holds full article text; only aggregated
results are committed.

## Limitations

- **Reference ratings are judgments, not ground truth.** AllSides and Ad Fontes
  use editorial/panel methods and rate outlets as a whole; disagreement is not
  automatically Solon's error.
- **US-centric scale.** "Left/right" here is the US spectrum.
- **Sample size.** 13 outlets. Coverage gaps removed most center-rated outlets
  (AP, The Hill, USA Today), so the middle of the scale is thinly represented and ≤30 articles each; CIs are reported for that
  reason. Topic choice and NewsAPI's indexing shape the sample.
- **Paywalls** reduce usable articles for some outlets (see the coverage table).
- **Residual leakage.** Blinding strips names and domains, but a model can still
  recognize an outlet from style or recurring bylines; the reputation-only
  baseline and leak rate bound this.
- **One model, one prompt version** per run; both are recorded in the results.
