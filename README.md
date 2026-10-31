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
- **Article detail view** — title, source, publication date, and bias tag for any article.
- **Batch summarization** — summarize every fetched article at once; each gets a 3–5 sentence summary and a bias tag.
- **Cross-source synthesis** — a unified analysis identifying consensus, divergence, and single-source claims across all articles.
- **Single-article summarization** — summarize one article on demand from the detail view.
- **Bias detection** — per-article LLM bias tagging, run in parallel with summarization.
- **Reader view** — scrape and display full article content in a styled window.
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
| Config & models | pydantic · pydantic-settings |
| News source | NewsAPI |
| Content extraction | newspaper3k |
| Tests | pytest |

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
uvicorn backend.main:app --reload   # run from the repo root
```

Required keys in `.env`:

| Variable | Description |
|---|---|
| `NEWSAPI_KEY` | NewsAPI key — https://newsapi.org |
| `GROQ_API_KEY` | Groq API key — https://console.groq.com |

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

The backend ships with a pytest suite (unit tests use in-memory fakes — no network, no real LLM, no keys):

```bash
cd backend
pytest                        # full suite
pytest -m "not integration"   # offline only
```

The one integration test hits the live NewsAPI and skips automatically when `NEWSAPI_KEY` is not set.

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
│   ├── cache/                      # Analysis cache (in-memory; DB later)
│   ├── profiles/                   # Source/topic profiles
│   └── tests/                      # pytest suite
└── client/
    ├── CMakeLists.txt
    └── src/
        ├── main.cpp
        ├── app/                    # Application entry point
        ├── network/               # ApiClient (HTTP layer)
        ├── models/                # Article, ArticleListModel
        └── ui/                    # MainWindow + views
```

---

## Roadmap

- Navigation sidebar (bookmarks, history, profiles)
- User profiles — preferred sources and topics
- Local persistence for articles, summaries, and syntheses
- Additional news providers beyond NewsAPI
- Filter articles by bias tag
- Export summaries and synthesis to Markdown or PDF

---

## Limitations

- **NewsAPI free tier** — 100 requests/day, no full article content, limited sources.
- **Content extraction is best-effort** — `newspaper3k` can fail on paywalled or heavily dynamic pages, leaving content empty.
- **No persistence yet** — state is in-memory; closing the app discards fetched articles and summaries.
- **Single provider** — only NewsAPI is wired up today; the `NewsProvider` interface exists for future sources.
- **Local use** — the backend has no auth layer and is intended to run locally.

---

## License

Released under the [MIT License](LICENSE).

---

## Author

Built by **Wajdi** as a full-stack portfolio project spanning native desktop (C++/Qt6), API design (FastAPI), and LLM orchestration (LangGraph).

This is an actively evolving project rather than a finished product — new features are being added over time, and feedback is welcome.
