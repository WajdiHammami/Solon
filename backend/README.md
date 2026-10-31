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

| Variable | Required | Description |
|---|---|---|
| `NEWSAPI_KEY` | yes | NewsAPI key (https://newsapi.org) |
| `LLM_PROVIDER` | no | `groq` (default) or `azure` |
| `GROQ_API_KEY` | for Groq | Groq API key (https://console.groq.com) |
| `GROQ_MODEL` | no | Groq model id (default `openai/gpt-oss-120b`) |
| `AZURE_OPENAI_ENDPOINT` | for Azure | e.g. `https://<resource>.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | for Azure | Azure OpenAI key |
| `AZURE_OPENAI_DEPLOYMENT` | for Azure | Deployment name (not the model name) |
| `AZURE_OPENAI_API_VERSION` | no | default `2024-10-21` |
| `BATCH_MAX_TOKENS` | no | Estimated-token budget per batch (default `100000`) |
| `BATCH_MAX_CONCURRENCY` | no | Articles analyzed at once (default `4`) |
| `MIN_CONTENT_CHARS` | no | Articles with less text are scraped first (default `600`) |
| `LOG_LEVEL` | no | default `INFO` |
| `LOG_FILE` | no | default `logs/solon.log` (relative to `backend/`; empty disables) |
| `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT` | no | Log rotation (default 10 MB × 5) |
| `PROFILE_PATH` | no | Path to the profile JSON (default `profiles/default.json`) |

## Running

From the repository root (so the `backend` package resolves):

```bash
uvicorn backend.main:app --reload
```

## API

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/feed` | Fetch articles (`topic`, `page_size`, `page`) |
| POST | `/analyze` | Analyze articles + synthesize → `BatchAnalysis` |
| POST | `/analyze/article` | Summarize and bias-tag one article → `ArticleResult` |
| POST | `/summarize` | **Deprecated** legacy shape for the current client; use `/analyze` |
| GET | `/article/content` | Scrape full article text for a `url` |

`BatchAnalysis` contains `analyses` (keyed by article id), `synthesis`,
`sources` (ids the synthesis was built from), `failed` (per-task failures
with a `retryable` flag), `skipped` (ids dropped by the token budget) and
`estimated_tokens`. A failing task never fails the request.

Summaries and bias tags are cached by article URL, so repeat requests only
pay for the synthesis.

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
├── logging_config.py        # Console + rotating file logging
├── llm/                     # Provider-agnostic LLM layer
│   ├── base.py              # LLMClient interface
│   ├── models.py            # GenerationRequest / GenerationResponse
│   ├── errors.py            # LLMError hierarchy (retryable flag)
│   ├── openai_compatible.py # Shared chat.completions implementation
│   ├── groq_llm.py          # GroqLLM
│   ├── azure_llm.py         # AzureLLM
│   └── factory.py           # create_llm(settings)
├── workflows/               # LangGraph analysis workflows
│   ├── prompts.py           # All prompt text
│   ├── tasks.py             # summarize / detect_bias / synthesize
│   ├── budget.py            # Token estimation + article selection
│   ├── article_workflow.py  # One article: only the missing work
│   └── batch_workflow.py    # Many articles: plan, analyze, synthesize
├── cache/                   # AnalysisCache interface + in-memory store
├── profiles/default.json    # Default source/topic profile
└── tests/                   # Tests (NewsAPI test marked `integration`)
```

## Tests

```bash
pytest
```

The NewsAPI test is marked `integration` and hits the live API; it skips
automatically when `NEWSAPI_KEY` is not set.
