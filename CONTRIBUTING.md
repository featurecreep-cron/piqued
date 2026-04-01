# Contributing to Piqued

## Development Setup

1. Clone the repo
2. Create a conda environment: `conda create -n piqued python=3.12`
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `uvicorn piqued.main:app --reload --port 8400`

## Testing

```bash
pytest tests/
```

## Code Style

- Python: Black + Ruff
- Conventional commits: `feat(scope): description`

## Pull Requests

- One feature per PR
- Tests for new functionality
- Update docs if behavior changes
