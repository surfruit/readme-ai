# Contributing to readme-ai

Thanks for your interest in contributing! This document explains how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/readme-ai
cd readme-ai

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=readme_ai --cov-report=term-missing
```

## Code Style

We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting.

```bash
ruff check readme_ai/
ruff format readme_ai/
```

## Project Structure

```
readme_ai/
├── cli.py         # Typer CLI entry point
├── analyzer.py    # Reads repo structure and metadata
├── sampler.py     # Selects representative code files
├── builder.py     # Assembles final README markdown
├── badges.py      # Generates shields.io badges
└── llm/
    ├── base.py        # Abstract base + prompt builder
    ├── openai.py      # OpenAI client
    ├── anthropic.py   # Anthropic Claude client
    └── ollama.py      # Ollama (local) client
```

## Adding a New LLM Provider

1. Create `readme_ai/llm/yourprovider.py`
2. Subclass `BaseLLMClient` and implement `generate()`
3. Register it in `readme_ai/llm/__init__.py` factory function
4. Add tests and update the README

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Add tests for new functionality
- Update the README if you add/change CLI flags
- Run `pytest` and `ruff check` before submitting

## Good First Issues

Look for issues labeled [`good first issue`](../../issues?q=is%3Aopen+label%3A%22good+first+issue%22) — these are designed to be approachable for new contributors.

## Questions?

Open an issue or start a discussion. We're friendly!
