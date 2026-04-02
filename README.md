<div align="center">

# readme-ai

**Generate beautiful, accurate READMEs from your actual code — not templates.**

![Python](https://img.shields.io/badge/python-3.9+-3776AB?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![CI](https://img.shields.io/github/actions/workflow/status/yourusername/readme-ai/ci.yml?style=flat-square&label=CI)
![PyPI](https://img.shields.io/pypi/v/readme-ai?style=flat-square)
![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)

<br/>

```bash
pip install readme-ai && readme-ai analyze ./your-project
```

<br/>

<!-- Replace with your actual demo GIF -->
<!-- Record with: vhs demo.tape -->

![demo](https://raw.githubusercontent.com/surfruit/readme-ai/main/assets/demo.gif)

</div>

---

## Why readme-ai?

Every developer has a graveyard of repos with a 3-line README.  
Writing a good one takes hours. Templates give you empty boxes to fill in manually.  
**readme-ai reads your code** — imports, docstrings, entry points, env vars, file structure —  
and writes a README that's actually accurate.

|                   | readme-ai   | ChatGPT (manual) | README templates |
| ----------------- | ----------- | ---------------- | ---------------- |
| Reads actual code | ✅          | ❌               | ❌               |
| Zero config       | ✅          | ❌               | ✅               |
| Works offline     | ✅ (Ollama) | ❌               | ✅               |
| Multiple LLMs     | ✅          | ❌               | —                |
| CI/CD ready       | ✅          | ❌               | ❌               |

---

## Features

- **Understands your code** — scans imports, docstrings, entry points, and file structure
- **Multi-provider** — OpenAI, Anthropic Claude, or fully local via Ollama (no API key needed)
- **Any language** — Python, JavaScript, TypeScript, Go, Rust, Ruby, Java, and more
- **Smart sampling** — picks the most informative files within a context budget
- **Auto badges** — generates shields.io badges for language, license, CI, and more
- **GitHub Actions** — drop-in workflow to regenerate README on every push
- **Analyze remote repos** — pass a GitHub URL directly, no cloning needed
- **Preview in terminal** — `readme-ai preview` renders markdown in your terminal

---

## Installation

### From PyPI (recommended)

```bash
pip install readme-ai
```

### From source

```bash
git clone https://github.com/surfruit/readme-ai
cd readme-ai
pip install -e ".[dev]"
```

### Requirements

- Python 3.9+
- An API key for OpenAI or Anthropic **OR** [Ollama](https://ollama.ai) running locally

---

## Quick Start

```bash
# With OpenAI (default)
export OPENAI_API_KEY=sk-...
readme-ai analyze ./my-project

# With Anthropic Claude
export ANTHROPIC_API_KEY=sk-ant-...
readme-ai analyze ./my-project --provider anthropic

# 100% local, no API key — requires Ollama running
ollama pull llama3
readme-ai analyze ./my-project --provider ollama

# Analyze a GitHub repo directly
readme-ai analyze https://github.com/tiangolo/fastapi --provider openai
```

Output is saved to `README.md` in the current directory. Pass `--output` to change the path.

---

## Usage

### CLI reference

```
readme-ai analyze [REPO] [OPTIONS]

Arguments:
  REPO  Local path or GitHub URL  [required]

Options:
  -o, --output PATH          Output file (default: README.md)
  -p, --provider TEXT        LLM provider: openai | anthropic | ollama
  -m, --model TEXT           Model name (uses provider default if omitted)
  --api-key TEXT             API key (or set via env var)
  --ollama-host TEXT         Ollama URL (default: http://localhost:11434)
  -y, --overwrite            Skip overwrite confirmation
  --version                  Show version and exit
```

```
readme-ai preview [README]

Arguments:
  README  Path to README file (default: README.md)
```

### Providers and default models

| Provider  | Flag                   | Default model             | Needs API key |
| --------- | ---------------------- | ------------------------- | ------------- |
| OpenAI    | `--provider openai`    | `gpt-4o-mini`             | Yes           |
| Anthropic | `--provider anthropic` | `claude-3-haiku-20240307` | Yes           |
| Ollama    | `--provider ollama`    | `llama3`                  | No            |

### Examples

```bash
# Use a specific model
readme-ai analyze . --provider openai --model gpt-4o

# Save to a different file
readme-ai analyze . --output docs/README.md

# Analyze a specific GitHub repo and skip confirmation
readme-ai analyze https://github.com/sindresorhus/got -y

# Preview the generated README in your terminal
readme-ai preview README.md
```

---

## GitHub Actions — Auto-update README

Add this to `.github/workflows/readme.yml` to regenerate your README on every push to `main`:

```yaml
name: Update README

on:
  push:
    branches: [main]
    paths-ignore:
      - 'README.md'

jobs:
  readme:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install readme-ai
      - run: readme-ai analyze . --provider openai -y
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: 'docs: regenerate README [skip ci]'
```

---

## Configuration

readme-ai works with zero configuration. All options are available as CLI flags or environment variables.

| Environment Variable | CLI flag     | Description          |
| -------------------- | ------------ | -------------------- |
| `OPENAI_API_KEY`     | `--api-key`  | OpenAI API key       |
| `ANTHROPIC_API_KEY`  | `--api-key`  | Anthropic API key    |
| `README_AI_PROVIDER` | `--provider` | Default LLM provider |
| `README_AI_MODEL`    | `--model`    | Default model name   |

---

## How it works

```
Your repo
    │
    ▼
ProjectAnalyzer ──── reads pyproject.toml / package.json / go.mod / Cargo.toml
    │                 detects language, frameworks, deps, env vars, entry points
    ▼
CodeSampler ──────── picks the most informative files within a ~40KB budget
    │                 prioritizes: main.py, cli.py, lib.rs, index.ts, etc.
    ▼
LLM Engine ──────── sends structured prompt to OpenAI / Anthropic / Ollama
    │                returns JSON with tagline, features, installation, examples...
    ▼
ReadmeBuilder ────── assembles sections, generates badges, formats markdown
    │
    ▼
README.md
```

---

## Roadmap

- [ ] `--watch` mode — regenerate on file changes during development
- [ ] Notion export
- [ ] Multilingual README (generate in any language with `--lang`)
- [ ] VS Code extension
- [ ] Web UI for non-CLI users
- [ ] Support for monorepos (per-package READMEs)

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

```bash
git clone https://github.com/surfruit/readme-ai
cd readme-ai
pip install -e ".[dev]"
pytest tests/ -v
```

New to the codebase? Look for [`good first issue`](../../issues?q=label%3A%22good+first+issue%22) labels.

---

## License

[MIT](LICENSE) — free for personal and commercial use.

---

<div align="center">
  <sub>If readme-ai saved you time, consider giving it a ⭐</sub>
</div>
