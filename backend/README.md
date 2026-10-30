# Solon Backend

FastAPI service that fetches news articles, summarizes them with an LLM,
detects per-article bias, and synthesizes a cross-source analysis.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file from the template and add your keys:

```bash
cp .env.example .env
# then edit .env
```

| Variable       | Required | Description                                   |
|----------------|----------|-----------------------------------------------|
| `NEWSAPI_KEY`  | yes      | NewsAPI key (https://newsapi.org)             |
| `GROQ_API_KEY` | yes      | Groq API key (https://console.groq.com)       |
| `GROQ_MODEL`   | no       | LLM model id (default `llama-3.3-70b-versatile`) |
| `PROFILE_PATH` | no       | Path to the profile JSON (default `profiles/default.json`) |

## Running

From the repository root (so the `backend` package resolves):

```bash
uvicorn backend.main:app --reload
```

## API

| Method | Path               | Description                                      |
|--------|--------------------|--------------------------------------------------|
| GET    | `/health`          | Liveness probe                                   |
| GET    | `/feed`            | Fetch articles (`topic`, `page_size`, `page`)    |
| POST   | `/summarize`       | Summarize one article, or batch + synthesize many |
| GET    | `/article/content` | Scrape full article text for a `url`             |

## Project layout

```
backend/
├── main.py                  # FastAPI routes
├── config.py                # Settings (env / .env via pydantic-settings)
├── models.py                # Pydantic models
├── profile.py               # Profile loading/validation
├── news_providers/          # News source adapters
│   ├── base.py              # NewsProvider abstract interface
│   └── newsapi_provider.py  # NewsAPI implementation
├── summarization/           # LangGraph summarization pipeline
│   ├── state.py             # Graph state (TypedDicts)
│   └── pipeline.py          # Batch + singular graphs
├── profiles/default.json    # Default source/topic profile
└── tests/                   # Tests (NewsAPI test marked `integration`)
```

## Tests

```bash
pytest
```

The NewsAPI test is marked `integration` and hits the live API; it skips
automatically when `NEWSAPI_KEY` is not set.
