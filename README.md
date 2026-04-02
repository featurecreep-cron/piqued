# Piqued

[![CI](https://github.com/featurecreep-cron/piqued/actions/workflows/ci.yml/badge.svg)](https://github.com/featurecreep-cron/piqued/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/featurecreep-cron/piqued)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

An AI-powered personal interest filter for RSS feeds, newsletters, and links. Piqued segments long-form content, learns what you care about from your feedback, and surfaces the sections worth reading.

## Quick Start

```bash
docker compose up -d
```

Open `http://localhost:8400` — the setup wizard walks you through configuration (admin account, LLM provider, FreshRSS connection).

## What It Does

1. **Ingests** articles from FreshRSS via the GReader API
2. **Classifies** content (full article, teaser, paywall, error page) using an LLM
3. **Segments** long-form articles into sections with summaries, topic tags, and quality flags
4. **Scores** each section against your natural language interest profile
5. **Learns** from your thumbs-up/down feedback — with optional reasoning ("not because it's about finance, but because it's regulatory procedure")
6. **Synthesizes** your feedback into a readable interest profile that evolves over time

## How Scoring Works

Piqued uses **hybrid scoring**: an LLM reads your interest profile and each section summary, then assigns a confidence score with reasoning. Formula-based scoring (`sigmoid(avg(tag_weights) * temperature)`) serves as a fallback when no profile exists or the LLM is unavailable.

Your interest profile is a natural language document maintained by the LLM. You can read it, edit it, or let it evolve purely from feedback. The system explains every score so you can give targeted corrections.

## Features

- **Multi-provider LLM support** — Gemini, OpenAI, Claude, Ollama. Separate model tiers for classification, segmentation, and scoring.
- **Multi-user** — independent interest profiles per user, shared content processing
- **Three auth methods** — OIDC (Authentik, Keycloak), local username/password, forward-auth headers
- **Content enrichment** — follows links to full text, falls back to archive.is for paywalled content
- **Keyboard navigation** — j/k navigate, u/d vote, Enter expand, Escape back
- **Processing controls** — daily token budget, per-cycle rate limiting, backlog ordering, crash recovery
- **Self-hosted** — single Docker container, SQLite database, no external dependencies beyond an LLM API key

## Configuration

All configuration is managed through the web UI at `/settings`. On first boot, the setup wizard at `/setup` handles initial configuration.

Environment variables (for Docker):
- `PIQUED_DATABASE_PATH` — path to SQLite database (default: `/data/piqued.db`)
- `PIQUED_LLM_API_KEY` or `PIQUED_LLM_API_KEY_FILE` — LLM provider API key
- `PIQUED_FRESHRSS_API_PASS` or `PIQUED_FRESHRSS_API_PASS_FILE` — FreshRSS API password

All other settings can be configured via `PIQUED_<KEY>` environment variables or the web UI.

## Development

```bash
conda create -n piqued python=3.12
conda activate piqued
pip install -r requirements.txt
uvicorn piqued.main:app --reload --port 8400
```

Run tests:
```bash
pytest tests/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and how to submit changes.

## Support

If you find Piqued useful, consider [buying me a coffee](https://buymeacoffee.com/featurecreep).

## License

MIT
