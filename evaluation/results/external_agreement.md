# External agreement: Solon lean vs AllSides / Ad Fontes

Generated 2026-11-12 17:33 UTC · bias prompt `1fb9ffe6dea6` · model(s) gpt-4.1-mini · ≥5 political articles per outlet

## Headline (blinded, as shipped)

| Metric | vs AllSides | vs Ad Fontes |
|---|---|---|
| Spearman ρ (95% CI) | +0.92 [+0.67, +1.00] | +0.94 [+0.69, +1.00] |
| Outlets | 12 | 12 |
| Exact class agreement | 33% | – |
| Within one class | 92% | – |

Reference ceiling: AllSides and Ad Fontes agree with each other at ρ = +0.94 [+0.76, +1.00] over 13 outlets.

## Baselines (vs AllSides)

| Predictor | Spearman ρ | Exact | Within one |
|---|---|---|---|
| **Solon, blinded** | +0.92 | 33% | 92% |
| Solon, unblinded (sees source + URL) | +0.94 | 42% | 100% |
| Reputation only (outlet name, no article) | +0.90 | 50% | 100% |
| Always "Center" | – | 8% | 50% |
| Random class (expected) | – | 20% | 50% |

Blinding effect: mean |unblinded − blinded| = 0.28 lean points over 12 outlets. Blinded vs reputation-only ρ = +0.85. Blinded prompts still naming the outlet: 8%.

## Confusion matrix (blinded, rows = AllSides, columns = Solon)

| | Left | Lean Left | Center | Lean Right | Right |
|---|---|---|---|---|---|
| Left | 1 | 3 | 0 | 0 | 0 |
| Lean Left | 0 | 1 | 2 | 0 | 0 |
| Center | 0 | 0 | 1 | 0 | 0 |
| Lean Right | 0 | 0 | 1 | 1 | 0 |
| Right | 0 | 0 | 1 | 1 | 0 |

## Per outlet

| Outlet | Usable / collected | Political | Solon blinded (95% CI) | Unblinded | Reputation | AllSides | Ad Fontes |
|---|---|---|---|---|---|---|---|
| HuffPost | 26 / 29 | 26 | -0.62 [-0.96, -0.23] | -0.88 | -2.00 | -4.3 (Left) | -10.8 |
| Vox | 25 / 25 | 23 | -0.91 [-1.00, -0.78] | -0.92 | -1.00 | -3.5 (Left) | -10.1 |
| Mother Jones | 24 / 24 | 24 | -0.83 [-1.00, -0.58] | -1.12 | -2.00 | -4 (Left) | -15.1 |
| Slate | 15 / 17 | 13 | -1.54 [-1.77, -1.31] | -1.43 | -1.00 | -4.5 (Left) | -12.8 |
| NBC News | 26 / 27 | 26 | -0.46 [-0.73, -0.15] | -0.62 | -1.00 | -1.48 (Lean Left) | -4.8 |
| CBS News | 27 / 30 | 25 | -0.16 [-0.44, +0.12] | -0.42 | +0.00 | -1.69 (Lean Left) | -2.6 |
| NPR | 29 / 30 | 29 | -0.62 [-0.83, -0.41] | -0.57 | -1.00 | -1.88 (Lean Left) | -4.4 |
| Reason | 30 / 30 | 30 | -0.13 [-0.57, +0.33] | +0.03 | +1.00 | 0.1 (Center) | +4.2 |
| New York Post | 30 / 30 | 27 | +0.33 [-0.07, +0.74] | +0.61 | +2.00 | 3.13 (Right) | +9.6 |
| Washington Examiner | 5 / 6 | 5 | +0.40 [+0.00, +0.80] | +0.80 | +2.00 | 2.3 (Lean Right) | +11.2 |
| Fox News *(excluded)* | 0 / 30 | 0 | – – | – | +2.00 | 3.85 (Right) | +11.4 |
| Daily Caller | 30 / 30 | 30 | +0.53 [+0.10, +0.97] | +1.17 | +2.00 | 2.67 (Lean Right) | +12.8 |
| Breitbart | 30 / 30 | 29 | +0.66 [+0.17, +1.10] | +1.34 | +2.00 | 6 (Right) | +13.6 |

Lean scale: −2 Left · −1 Lean Left · 0 Center · +1 Lean Right · +2 Right. Ratings were entered by hand from allsides.com and adfontesmedia.com (see `outlets.csv` for access dates). Errors per condition: blinded 1, unblinded 1, reputation 0.
