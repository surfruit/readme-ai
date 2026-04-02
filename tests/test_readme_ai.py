"""Tests for readme-ai."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from readme_ai.analyzer import ProjectAnalyzer, ProjectInfo
from readme_ai.badges import generate_badges
from readme_ai.builder import ReadmeBuilder
from readme_ai.llm.base import GeneratedContent, BaseLLMClient, build_user_prompt
from readme_ai.sampler import CodeSampler, CodeSample


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_python_repo(tmp_path: Path) -> Path:
    """Create a minimal fake Python repo."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\ndescription = "A cool app"\n'
        'requires-python = ">=3.10"\ndependencies = ["httpx>=0.25", "typer>=0.9"]\n'
        '\n[project.scripts]\nmyapp = "myapp.cli:app"\n'
    )
    (tmp_path / "myapp").mkdir()
    (tmp_path / "myapp" / "__init__.py").write_text('"""myapp package."""\n__version__ = "0.1.0"\n')
    (tmp_path / "myapp" / "cli.py").write_text(
        '"""CLI entry point."""\nimport typer\napp = typer.Typer()\n\n@app.command()\ndef run():\n    """Run the app."""\n    pass\n'
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_cli.py").write_text("def test_placeholder(): assert True\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\n")
    (tmp_path / ".env.example").write_text("DATABASE_URL=postgres://localhost/myapp\nSECRET_KEY=changeme\n")
    (tmp_path / "LICENSE").write_text("MIT License\n\nCopyright (c) 2024\n")
    return tmp_path


@pytest.fixture
def sample_project_info() -> ProjectInfo:
    return ProjectInfo(
        name="myapp",
        description="A cool app",
        language="Python",
        frameworks=["FastAPI"],
        dependencies=["httpx", "typer", "fastapi"],
        has_tests=True,
        has_docker=True,
        has_ci=False,
        license_type="MIT",
        env_vars=["DATABASE_URL", "SECRET_KEY"],
        repo_url="https://github.com/user/myapp",
    )


@pytest.fixture
def sample_generated() -> GeneratedContent:
    return GeneratedContent(
        tagline="A blazing-fast CLI tool for developers",
        description="myapp is a command-line tool that does amazing things.",
        features=["Fast", "Extensible", "Zero config"],
        installation="```bash\npip install myapp\n```",
        quick_start="```bash\nmyapp run\n```",
        usage_examples="```bash\nmyapp run --verbose\n```",
        api_overview="| Command | Description |\n|---|---|\n| `run` | Run the app |",
        configuration="Set `DATABASE_URL` in your environment.",
        roadmap=["Add plugin system", "Web UI"],
    )


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------

class TestProjectAnalyzer:
    def test_analyze_local_path(self, sample_python_repo: Path) -> None:
        analyzer = ProjectAnalyzer(str(sample_python_repo))
        info = analyzer.analyze()

        assert info.name == sample_python_repo.name
        assert info.language == "Python"
        assert "httpx" in info.dependencies
        assert "typer" in info.dependencies
        assert info.has_tests is True
        assert info.has_docker is True
        assert info.license_type == "MIT"
        assert "DATABASE_URL" in info.env_vars
        assert "SECRET_KEY" in info.env_vars

    def test_description_from_pyproject(self, sample_python_repo: Path) -> None:
        analyzer = ProjectAnalyzer(str(sample_python_repo))
        info = analyzer.analyze()
        assert info.description == "A cool app"

    def test_entry_points_from_pyproject(self, sample_python_repo: Path) -> None:
        analyzer = ProjectAnalyzer(str(sample_python_repo))
        info = analyzer.analyze()
        assert "myapp" in info.entry_points

    def test_file_tree_not_empty(self, sample_python_repo: Path) -> None:
        analyzer = ProjectAnalyzer(str(sample_python_repo))
        info = analyzer.analyze()
        assert len(info.file_tree) > 10

    def test_invalid_path_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            analyzer = ProjectAnalyzer("/nonexistent/path/xyz")
            analyzer.analyze()

    def test_python_version_extracted(self, sample_python_repo: Path) -> None:
        analyzer = ProjectAnalyzer(str(sample_python_repo))
        info = analyzer.analyze()
        assert "3.10" in info.python_version


# ---------------------------------------------------------------------------
# Sampler tests
# ---------------------------------------------------------------------------

class TestCodeSampler:
    def test_samples_python_files(self, sample_python_repo: Path) -> None:
        sampler = CodeSampler(sample_python_repo)
        samples = sampler.sample()
        assert len(samples) > 0
        paths = [s.path for s in samples]
        assert any("cli.py" in p for p in paths)

    def test_skips_hidden_dirs(self, sample_python_repo: Path) -> None:
        (sample_python_repo / ".git").mkdir()
        (sample_python_repo / ".git" / "config").write_text("[core]")
        sampler = CodeSampler(sample_python_repo)
        samples = sampler.sample()
        assert not any(".git" in s.path for s in samples)

    def test_respects_budget(self, sample_python_repo: Path) -> None:
        sampler = CodeSampler(sample_python_repo)
        samples = sampler.sample()
        total = sum(len(s.content.encode()) for s in samples)
        assert total <= 40_000 * 1.1  # allow tiny overrun from last file

    def test_high_priority_files_first(self, sample_python_repo: Path) -> None:
        sampler = CodeSampler(sample_python_repo)
        samples = sampler.sample()
        # cli.py should appear before test files
        paths = [s.path for s in samples]
        cli_idx = next((i for i, p in enumerate(paths) if "cli.py" in p), 999)
        test_idx = next((i for i, p in enumerate(paths) if "test_" in p), 999)
        assert cli_idx < test_idx


# ---------------------------------------------------------------------------
# Builder tests
# ---------------------------------------------------------------------------

class TestReadmeBuilder:
    def test_build_returns_string(self, sample_project_info, sample_generated) -> None:
        builder = ReadmeBuilder(sample_project_info)
        result = builder.build(sample_generated)
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_project_name(self, sample_project_info, sample_generated) -> None:
        builder = ReadmeBuilder(sample_project_info)
        result = builder.build(sample_generated)
        assert sample_project_info.name in result

    def test_contains_tagline(self, sample_project_info, sample_generated) -> None:
        builder = ReadmeBuilder(sample_project_info)
        result = builder.build(sample_generated)
        assert sample_generated.tagline in result

    def test_contains_features(self, sample_project_info, sample_generated) -> None:
        builder = ReadmeBuilder(sample_project_info)
        result = builder.build(sample_generated)
        for feature in sample_generated.features:
            assert feature in result

    def test_contains_env_vars(self, sample_project_info, sample_generated) -> None:
        builder = ReadmeBuilder(sample_project_info)
        result = builder.build(sample_generated)
        assert "DATABASE_URL" in result
        assert "SECRET_KEY" in result

    def test_contains_toc(self, sample_project_info, sample_generated) -> None:
        builder = ReadmeBuilder(sample_project_info)
        result = builder.build(sample_generated)
        assert "Table of Contents" in result

    def test_contains_watermark(self, sample_project_info, sample_generated) -> None:
        builder = ReadmeBuilder(sample_project_info)
        result = builder.build(sample_generated)
        assert "readme-ai" in result

    def test_roadmap_checkboxes(self, sample_project_info, sample_generated) -> None:
        builder = ReadmeBuilder(sample_project_info)
        result = builder.build(sample_generated)
        assert "- [ ]" in result


# ---------------------------------------------------------------------------
# Badges tests
# ---------------------------------------------------------------------------

class TestBadges:
    def test_generates_language_badge(self, sample_project_info) -> None:
        badges = generate_badges(sample_project_info)
        assert "Python" in badges
        assert "img.shields.io" in badges

    def test_generates_license_badge(self, sample_project_info) -> None:
        badges = generate_badges(sample_project_info)
        assert "MIT" in badges

    def test_generates_prs_badge(self, sample_project_info) -> None:
        badges = generate_badges(sample_project_info)
        assert "PRs" in badges


# ---------------------------------------------------------------------------
# LLM base tests
# ---------------------------------------------------------------------------

class TestBaseLLM:
    def test_parse_valid_json(self) -> None:
        class DummyLLM(BaseLLMClient):
            def generate(self, *args): ...

        llm = DummyLLM()
        raw = json.dumps({
            "tagline": "Cool tool",
            "description": "A description",
            "features": ["Fast", "Reliable"],
            "installation": "pip install x",
            "quick_start": "x run",
            "usage_examples": "",
            "api_overview": "",
            "configuration": "",
            "roadmap": [],
        })
        result = llm._parse_response(raw)
        assert result.tagline == "Cool tool"
        assert result.features == ["Fast", "Reliable"]

    def test_parse_json_with_fences(self) -> None:
        class DummyLLM(BaseLLMClient):
            def generate(self, *args): ...

        llm = DummyLLM()
        raw = '```json\n{"tagline": "x", "description": "", "features": [], "installation": "", "quick_start": "", "usage_examples": "", "api_overview": "", "configuration": "", "roadmap": []}\n```'
        result = llm._parse_response(raw)
        assert result.tagline == "x"

    def test_parse_invalid_json_raises(self) -> None:
        class DummyLLM(BaseLLMClient):
            def generate(self, *args): ...

        llm = DummyLLM()
        with pytest.raises(ValueError, match="invalid JSON"):
            llm._parse_response("not valid json {{{")
