# Solon

A desktop news aggregation and analysis app. Solon fetches articles from multiple news sources, summarizes them using an LLM, detects media bias, and generates a cross-source synthesis — all from a native desktop UI.

---

## What is this?

Solon is built around one idea: instead of reading five articles about the same event and forming your own incomplete picture, let the machine do the aggregation and surface what actually matters — where sources agree, where they diverge, and what bias each one carries.

The name is borrowed from Solon of Athens, the lawmaker known for his pursuit of balanced judgment.

---

## Stack

| Layer | Technology |
|---|---|
| Desktop client | C++ / Qt6 (QtWidgets) |
| Backend API | Python / FastAPI |
| LLM | Llama 3.3 70B via Groq |
| Orchestration | LangGraph |
| News source | NewsAPI |
| Content extraction | newspaper3k |

---

## Architecture

```
┌─────────────────────────────────┐        ┌──────────────────────────────────┐
│         Qt6 Desktop Client      │        │         FastAPI Backend           │
│                                 │        │                                   │
│  MainWindow                     │        │  GET  /feed                       │
│  ├── ArticleListModel (MVC)     │◄──────►│  POST /summarize                  │
│  ├── ArticleDetailView          │        │  GET  /article/content            │
│  └── SynthesisView              │        │                                   │
│                                 │        │  SummarizationPipeline (LangGraph)│
│  ApiClient (QNetworkAccessManager)       │  ├── summarize_article (parallel) │
│                                 │        │  ├── bias_detection (parallel)    │
└─────────────────────────────────┘        │  └── synthesize                   │
                                           └──────────────────────────────────┘
```

The client follows an MVC pattern. `ApiClient` handles all HTTP communication and emits Qt signals when responses arrive. `ArticleListModel` wraps the article list for the `QListView`. Views are decoupled from the network layer — they emit signals expressing intent, `MainWindow` wires them to `ApiClient`.

The backend uses a LangGraph pipeline that fans out summarization and bias detection in parallel for each article, then synthesizes the results into a unified analysis.

---

## Features

### Done
- **Feed search** — query NewsAPI by topic, results displayed in a scrollable list
- **Article detail view** — click any article to see title, source, publication date, and bias tag
- **Batch summarization** — summarize all fetched articles at once; each article gets a 3-5 sentence summary and a bias tag
- **Synthesis view** — after batch summarization, a cross-source analysis is shown identifying consensus, divergence, and single-source claims
- **Single article summarization** — summarize an individual article from the detail view
- **Read article** — scrape and display the full article content in a styled reader window
- **Bias detection** — LLM-powered per-article bias tagging, run in parallel with summarization
- **Dark theme** — Catppuccin Mocha applied globally

### Planned
- Navigation sidebar with additional views (bookmarks, history, profiles)
- User profiles — configure preferred sources and topics
- Persistent storage — save articles, summaries, and syntheses locally
- Multi-provider support — plug in additional news sources beyond NewsAPI
- Article filtering by bias tag
- Export summaries and synthesis to markdown or PDF

---

## Limitations

- **NewsAPI free tier** — limited to 100 requests/day, no full article content, sources restricted on the free plan
- **Content extraction is brittle** — `newspaper3k` fails on paywalled articles and some dynamic sites; content will be empty in those cases
- **No persistence** — everything is in-memory; closing the app loses all fetched articles and summaries
- **Single provider** — only NewsAPI is wired up; the `NewsProvider` base class exists for future providers but nothing else is implemented
- **Singular summarization bug** — the LangGraph singular pipeline runs but the summary is not yet returned to the client correctly; only batch summarization is fully functional end-to-end
- **No authentication** — the backend has no auth layer; it is intended for local use only

---

## Running locally

### Backend

```bash
cd backend
python -m uvicorn backend.main:app --reload
```

Requires a `.env` file (or environment variables) with:
```
NEWSAPI_KEY=your_key
GROQ_API_KEY=your_key
```

### Client

```bash
cd client
cmake -B build
cmake --build build
./build/solon
```

Requires Qt6 with `QtWidgets`, `QtNetwork`, and `QtCore`.

---

## Project structure

```
solon/
├── backend/
│   ├── main.py                   # FastAPI routes
│   ├── models.py                 # Pydantic models
│   ├── NewsProviders/            # NewsAPI provider
│   └── Summarization/            # LangGraph pipeline
└── client/
    ├── CMakeLists.txt
    └── src/
        ├── main.cpp
        ├── app/                  # Application entry point
        ├── network/              # ApiClient (HTTP layer)
        ├── models/               # Article struct, ArticleListModel
        └── ui/
            ├── MainWindow        # Main layout and signal wiring
            └── views/            # ArticleDetailView, SynthesisView
```
