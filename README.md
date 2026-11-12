# Solon

**A desktop news aggregation and analysis app** — Solon fetches articles from multiple news sources, summarizes them with an LLM, detects media bias, and generates a cross-source synthesis, all from a native desktop UI.

Built with a **C++/Qt6** desktop client and a **Python/FastAPI** backend driving **LangGraph** analysis workflows.

> 🚧 **Status: work in progress.** The core aggregation, summarization, bias-detection, and synthesis flow works end to end. The project is under active development — see the [roadmap](#roadmap) for what's next.

> The name is borrowed from Solon of Athens, the lawmaker known for his pursuit of balanced judgment.

---

## Why

Reading five articles about the same event leaves you with five partial pictures. Solon does the aggregation for you and surfaces what actually matters — where sources agree, where they diverge, and what bias each one carries — so you can form a judgment from the whole picture rather than one outlet's framing.

---

## Features

- **Topic search** — query news sources by topic, or leave the search empty for top headlines.
- **Article list** — tick the articles you want, sort by title, date, source or summarized-first; summarized articles show a colored bias badge.
- **Article detail view** — source, date, summary, bias label, explanation and lean for any article.
- **Batch summarization** — summarize the ticked articles at once; each gets a 3–5 sentence summary and a bias assessment.
- **Cross-source synthesis** — a unified analysis identifying consensus, divergence, and single-source claims across the selected articles.
- **Single-article summarization** — summarize one article on demand from the detail view.
- **Bias detection** — per-article label, explanation and left–right **lean** (−2 Left … +2 Right), run in parallel with summarization. The model is **blinded**: it sees only the article text, never which outlet published it.
- **Persistent cache** — summaries and bias are stored in SQLite and reused across restarts; editing a prompt automatically invalidates the results it produced.
- **Reader view** — scrape and display full article content in a styled window.
- **Cost visibility** — every LLM operation shows the tokens it used and its estimated price; the status bar keeps a session total.
- **Dark theme** — Catppuccin Mocha applied globally.

---

## Architecture

```
┌──────────────────────────────────┐          ┌──────────────────────────────────────┐
│         Qt6 Desktop Client        │          │            FastAPI Backend            │
│                                   │          │                                       │
│  MainWindow                       │          │  GET  /health                         │
│  ├── ArticleListModel (MVC)       │  HTTP    │  GET  /feed                           │
│  ├── ArticleDetailView            │◄───────► │  POST /analyze  · /analyze/article    │
│  └── SynthesisView                │  (JSON)  │  GET  /article/content                │
│                                   │          │                                       │
│  ApiClient (QNetworkAccessManager)│          │  BatchWorkflow (LangGraph)            │
│                                   │          │  ├── plan (cache + token budget)      │
│                                   │          │  ├── ArticleWorkflow per article      │
│                                   │          │  │   └── summarize ∥ detect_bias      │
│                                   │          │  └── synthesize                       │
│                                   │          │  LLMClient → Groq | Azure OpenAI      │
└──────────────────────────────────┘          └──────────────────────────────────────┘
```

**Client.** MVC throughout. `ApiClient` owns all HTTP communication and emits Qt signals when responses arrive. `ArticleListModel` adapts the article list for `QListView`. Views are decoupled from the network layer — they emit intent signals, and `MainWindow` wires those to `ApiClient`.

**Backend.** LangGraph workflows analyze each article (summary and bias detection in parallel) and synthesize the results into a single cross-source analysis. Work that is already known — from the request or the analysis cache — is never redone, a token budget drops the lowest-priority articles before any LLM call, and failures are reported per task instead of failing the batch. LLMs sit behind a provider-agnostic `LLMClient` interface (Groq or Azure OpenAI), and news sources behind a `NewsProvider` interface, so either can be swapped without touching the workflows. Configuration and secrets are loaded from the environment via `pydantic-settings`.

---

## Tech stack

| Layer | Technology |
|---|---|
| Desktop client | C++17 · Qt6 (Widgets, Network, Core) · CMake |
| Backend API | Python · FastAPI · Uvicorn |
| LLM orchestration | LangGraph |
| LLM | Groq (default `openai/gpt-oss-120b`) or Azure OpenAI, via the official SDKs |
| Storage | SQLite · SQLAlchemy (async) · Alembic migrations |
| Config & models | pydantic · pydantic-settings |
| News source | NewsAPI |
| Content extraction | newspaper3k |
| Tests | pytest (offline fakes for the LLM, NewsAPI and scraping) |

---

## Getting started

### Prerequisites

- **Backend:** Python 3.10+
- **Client:** a C++17 compiler, CMake 3.16+, and Qt6 (`Core`, `Network`, `Widgets` — e.g. `qt6-base-dev` on Debian/Ubuntu)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env     # then add your keys
cd ..
backend/.venv/bin/uvicorn backend.main:app --reload   # run from the repo root
```

Required keys in `.env`:

| Variable | Description |
|---|---|
| `NEWSAPI_KEY` | NewsAPI key — https://newsapi.org |
| `LLM_PROVIDER` | `groq` (default) or `azure` |
| `GROQ_API_KEY` | Groq API key — https://console.groq.com (for `groq`) |
| `AZURE_OPENAI_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT` | Azure OpenAI resource (for `azure`); endpoint is the base URL only |

Optional: per-provider prices per 1M tokens (`GROQ_PRICE_INPUT_PER_1M`, …) to show the estimated cost of each LLM operation.

See [`backend/README.md`](backend/README.md) for the full API reference and configuration options.

### Client

```bash
cd client
cmake -B build
cmake --build build
./build/Solon
```

---

## Testing

The backend ships with ~290 pytest tests. They use in-memory fakes — no network, no real LLM, no keys — and run in a few seconds. Storage tests run the same contract suite against the in-memory and SQLite implementations.

```bash
# from the repo root
backend/.venv/bin/python -m pytest backend -q                       # full suite
backend/.venv/bin/python -m pytest backend -q -m "not integration"  # offline only
```

The one integration test hits the live NewsAPI and skips automatically when `NEWSAPI_KEY` is not set.

---

## Evaluation

Does Solon's bias lean agree with established media-bias raters? For 12 US outlets (297 articles on the same six political topics), the **blinded** model's average lean per outlet was compared with [AllSides](https://www.allsides.com/media-bias/ratings) and [Ad Fontes Media](https://adfontesmedia.com/) ratings:

| | vs AllSides | vs Ad Fontes |
|---|---|---|
| **Spearman ρ, blinded (95% CI)** | **0.92** [0.67, 1.00] | **0.94** [0.69, 1.00] |
| The two raters vs each other (ceiling) | 0.94 [0.76, 1.00] | |
| Exact / within-one class agreement | 33% / 92% | – |

Solon ranks outlets about as consistently as the two raters agree with each other, while seeing only the article text. Its scores are compressed toward the center (hence modest exact-class agreement), and showing the model the source pushes them outward — the reason production is blinded. Controls include an unblinded condition, a reputation-only baseline, always-Center and random baselines, and a leak check.

Method, controls, limitations and how to reproduce: [`evaluation/README.md`](evaluation/README.md). Full results: [`evaluation/results/external_agreement.md`](evaluation/results/external_agreement.md). Run of 2026-11-12, Azure `gpt-4.1-mini`, ≈ $0.45 in tokens.

---

## Project structure

```
solon/
├── backend/
│   ├── main.py                     # FastAPI routes
│   ├── config.py                   # Settings (env / .env)
│   ├── models.py                   # Pydantic models
│   ├── profile.py                  # Profile loading/validation
│   ├── news_providers/             # News source adapters (NewsProvider interface)
│   ├── llm/                        # LLMClient interface + Groq / Azure clients
│   ├── workflows/                  # LangGraph workflows, tasks, prompts, budget
│   ├── cache/                      # AnalysisCache interface + in-memory store
│   ├── storage/                    # SQLite: Database, tables, SQL repositories
│   ├── migrations/                 # Alembic migrations
│   ├── profiles/                   # Source/topic profiles
│   └── tests/                      # pytest suite
├── evaluation/                     # External-agreement evaluation (collect, run, report)
└── client/
    ├── CMakeLists.txt
    └── src/
        ├── main.cpp
        ├── app/                    # Application entry point
        ├── network/               # ApiClient (HTTP layer)
        ├── models/                # Article, ArticleListModel, sort proxy
        └── ui/                    # MainWindow, views, delegate, settings dialog
```

---

## Roadmap

- Navigation sidebar (bookmarks, history, profiles)
- User profiles — preferred sources and topics
- Faithfulness evaluation of the synthesis (claim-level judge validated against human labels, NLI cross-check)
- Cost and latency evaluations (cache savings vs a naive baseline; parallel vs sequential)
- Show the lean score in the client
- Additional news providers beyond NewsAPI
- Filter articles by bias tag
- Export summaries and synthesis to Markdown or PDF

---

## Limitations

- **NewsAPI free tier** — 100 requests/day, no full article content, limited sources.
- **Content extraction is best-effort** — `newspaper3k` can fail on paywalled or heavily dynamic pages, and some sites refuse automated requests; Solon then falls back to the NewsAPI snippet.
- **US-centric lean** — the left–right scale follows the US political spectrum.
- **Single provider** — only NewsAPI is wired up today; the `NewsProvider` interface exists for future sources.
- **Local use** — the backend has no auth layer and is intended to run locally.

---

## License

Released under the [MIT License](LICENSE).

---

## Author

Built by **Wajdi** as a full-stack portfolio project spanning native desktop (C++/Qt6), API design (FastAPI), and LLM orchestration (LangGraph).

This is an actively evolving project rather than a finished product — new features are being added over time, and feedback is welcome.
