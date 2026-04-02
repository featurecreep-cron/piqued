# Piqued

AI-powered personal interest filter for RSS feeds. Segments articles, scores sections against user interest profiles, learns from feedback.

## Stack

- **Framework:** FastAPI + Starlette, async throughout
- **Database:** SQLite via SQLAlchemy 2.0 async + aiosqlite
- **LLM:** Multi-provider (Gemini, OpenAI, Claude, Ollama) via `piqued/llm/` abstraction
- **Templates:** Jinja2 (server-rendered, no frontend framework)
- **Auth:** OIDC, local password, forward-auth headers (configurable)
- **Scheduler:** APScheduler for background jobs (feed polling, nightly decay)

## Package Structure

```
piqued/
  main.py          — FastAPI app, lifespan, scheduler setup
  config.py        — Two-tier config: env bootstrap + DB runtime settings
  db.py            — SQLAlchemy engine + async session factory
  models.py        — All SQLAlchemy models (User, Article, Feed, InterestWeight, etc.)
  auth/            — Authentication: deps (get_current_user), router (login/logout/OIDC)
  feedback/        — Interest model: learner (EWA weight updates, decay), synthesizer (profile generation), router
  ingestion/       — FreshRSS polling, HTML extraction, LLM classification
  llm/             — Provider abstraction: base protocol, factory, per-provider clients
  processing/      — Pipeline (orchestrates ingest→classify→segment→score), scorer, segmenter, profile_scorer
  web/             — Web UI router + Jinja2 templates
```

## Config System

`piqued/config.py` uses a two-tier approach:
1. **Bootstrap (env only):** `PIQUED_DATABASE_PATH` — needed to find the DB
2. **Runtime (DB → env → default):** Everything else via `config.get(key)`

The `_cache` dict holds DB values. `_cache_loaded` flag controls whether the cache is consulted. Tests set both directly.

## Running Tests

```bash
conda run -n piqued --cwd ~/piqued python -m pytest tests/ -v
```

Lint and format:
```bash
conda run -n piqued --cwd ~/piqued ruff check .
conda run -n piqued --cwd ~/piqued ruff format --check .
```

## Test Patterns

- Tests use `os.environ["PIQUED_DATABASE_PATH"] = "/tmp/piqued_test_*.db"` before imports
- Config is set via `config._cache["key"] = "value"` and `config._cache_loaded = True` (not mock.patch — lazy imports make patching unreliable)
- Web flow tests use `httpx.AsyncClient` with `ASGITransport(app=app)`
- Each test file gets its own test DB to avoid cross-contamination

## Code Style

- Ruff for lint and format (project defaults)
- Conventional commits: `feat(scope):`, `fix(scope):`, `chore:`
- Intentional late imports in `main.py` use `# noqa: E402`
