"""Analyzes a repository to extract project metadata."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

try:
    import tomllib  # Python 3.11+
    def _load_toml(path: "Path"):  # type: ignore[return]
        with open(path, "rb") as f:
            return tomllib.load(f)
    HAS_TOML = True
except ImportError:
    try:
        import toml  # type: ignore[import]
        def _load_toml(path: "Path"):  # type: ignore[return]
            return toml.loads(path.read_text())
        HAS_TOML = True
    except ImportError:
        HAS_TOML = False
        def _load_toml(path: "Path"):  # type: ignore[return]
            return {}


LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".php": "PHP",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".hs": "Haskell",
    ".scala": "Scala",
    ".clj": "Clojure",
    ".r": "R",
    ".jl": "Julia",
    ".lua": "Lua",
    ".dart": "Dart",
    ".zig": "Zig",
    ".nim": "Nim",
    ".ml": "OCaml",
    ".sh": "Shell",
    ".bash": "Shell",
}

# Files that hint at frameworks / tools
FRAMEWORK_HINTS: dict[str, str] = {
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "express": "Express",
    "nextjs": "Next.js",
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "angular": "Angular",
    "svelte": "Svelte",
    "rails": "Ruby on Rails",
    "spring": "Spring",
    "gin": "Gin",
    "fiber": "Fiber",
    "actix": "Actix",
    "rocket": "Rocket",
    "axum": "Axum",
    "laravel": "Laravel",
    "symfony": "Symfony",
    "nestjs": "NestJS",
    "nuxt": "Nuxt.js",
    "remix": "Remix",
    "astro": "Astro",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "keras": "Keras",
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
}


@dataclass
class ProjectInfo:
    """All metadata extracted from a repository."""

    name: str
    description: str = ""
    language: str = "Unknown"
    frameworks: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    python_version: str = ""
    node_version: str = ""
    license_type: str = ""
    has_tests: bool = False
    has_docker: bool = False
    has_ci: bool = False
    has_docs: bool = False
    entry_points: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    repo_url: str = ""
    scripts: dict[str, str] = field(default_factory=dict)
    file_tree: str = ""
    extra: dict = field(default_factory=dict)


class ProjectAnalyzer:
    """Analyzes a local or remote git repository."""

    def __init__(self, repo: str) -> None:
        self.repo_input = repo
        self.repo_path: Path = Path()
        self._temp_dir: Optional[str] = None
        self._repo_name: str = ""

    def analyze(self) -> ProjectInfo:
        self._resolve_path()
        name = self._repo_name or self.repo_path.name
        info = ProjectInfo(name=name)
        info.repo_url = self._detect_remote_url()

        self._detect_language(info)
        self._detect_dependencies(info)
        self._detect_env_vars(info)
        self._detect_features(info)
        info.file_tree = self._build_file_tree()

        return info

    def _resolve_path(self) -> None:
        """Handle local path or GitHub URL."""
        parsed = urlparse(self.repo_input)
        if parsed.scheme in ("http", "https") and "github.com" in (parsed.netloc or ""):
            # Extract repo name from URL: https://github.com/user/repo -> repo
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) >= 2:
                self._repo_name = path_parts[1].removesuffix(".git")
            self._temp_dir = tempfile.mkdtemp(prefix="readme-ai-")
            try:
                subprocess.run(
                    ["git", "clone", "--depth=1", self.repo_input, self._temp_dir],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                raise RuntimeError(f"Failed to clone repository: {e.stderr}") from e
            self.repo_path = Path(self._temp_dir)
        else:
            self.repo_path = Path(self.repo_input).resolve()
            if not self.repo_path.exists():
                raise FileNotFoundError(f"Path not found: {self.repo_path}")

    def _detect_remote_url(self) -> str:
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            url = result.stdout.strip()
            # Normalize git@ to https://
            if url.startswith("git@github.com:"):
                url = url.replace("git@github.com:", "https://github.com/").rstrip(".git")
            return url
        except Exception:
            return ""

    def _detect_language(self, info: ProjectInfo) -> None:
        """Detect primary language by file count."""
        counts: dict[str, int] = {}
        skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}

        for p in self.repo_path.rglob("*"):
            if any(part in skip for part in p.parts):
                continue
            if p.is_file() and p.suffix in LANGUAGE_EXTENSIONS:
                lang = LANGUAGE_EXTENSIONS[p.suffix]
                counts[lang] = counts.get(lang, 0) + 1

        if counts:
            info.language = max(counts, key=lambda k: counts[k])

    def _detect_dependencies(self, info: ProjectInfo) -> None:
        """Parse dependency files for each ecosystem."""
        # Python
        self._parse_pyproject(info)
        self._parse_requirements(info)
        # JavaScript / TypeScript
        self._parse_package_json(info)
        # Go
        self._parse_go_mod(info)
        # Rust
        self._parse_cargo_toml(info)
        # Ruby
        self._parse_gemfile(info)

        # Detect frameworks from dependency names
        all_deps = [d.lower() for d in info.dependencies + info.dev_dependencies]
        for dep in all_deps:
            for hint, framework in FRAMEWORK_HINTS.items():
                if hint in dep and framework not in info.frameworks:
                    info.frameworks.append(framework)

    def _parse_pyproject(self, info: ProjectInfo) -> None:
        path = self.repo_path / "pyproject.toml"
        if not path.exists() or not HAS_TOML:
            return
        try:
            data = _load_toml(path)
            project = data.get("project", {})
            info.description = info.description or project.get("description", "")
            info.python_version = project.get("requires-python", "")
            info.dependencies += [
                re.split(r"[>=<!]", d)[0].strip()
                for d in project.get("dependencies", [])
            ]
            dev_deps = (
                data.get("tool", {}).get("hatch", {}).get("envs", {}).get("dev", {}).get("dependencies", [])
                or project.get("optional-dependencies", {}).get("dev", [])
            )
            info.dev_dependencies += [re.split(r"[>=<!]", d)[0].strip() for d in dev_deps]
            scripts = project.get("scripts", {})
            info.entry_points += list(scripts.keys())
            info.scripts.update(scripts)
        except Exception:
            pass

    def _parse_requirements(self, info: ProjectInfo) -> None:
        for fname in ("requirements.txt", "requirements/base.txt", "requirements/prod.txt"):
            path = self.repo_path / fname
            if not path.exists():
                continue
            try:
                for line in path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        pkg = re.split(r"[>=<!;\[]", line)[0].strip()
                        if pkg and pkg not in info.dependencies:
                            info.dependencies.append(pkg)
            except Exception:
                pass

    def _parse_package_json(self, info: ProjectInfo) -> None:
        path = self.repo_path / "package.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            info.description = info.description or data.get("description", "")
            info.node_version = data.get("engines", {}).get("node", "")
            info.dependencies += list(data.get("dependencies", {}).keys())
            info.dev_dependencies += list(data.get("devDependencies", {}).keys())
            scripts = data.get("scripts", {})
            info.scripts.update(scripts)
            if "main" in data:
                info.entry_points.append(data["main"])
        except Exception:
            pass

    def _parse_go_mod(self, info: ProjectInfo) -> None:
        path = self.repo_path / "go.mod"
        if not path.exists():
            return
        try:
            content = path.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("require"):
                    continue
                match = re.match(r"^\s*([\w./\-]+)\s+v[\d.]+", line)
                if match:
                    pkg = match.group(1).split("/")[-1]
                    info.dependencies.append(pkg)
        except Exception:
            pass

    def _parse_cargo_toml(self, info: ProjectInfo) -> None:
        path = self.repo_path / "Cargo.toml"
        if not path.exists() or not HAS_TOML:
            return
        try:
            data = _load_toml(path)
            pkg = data.get("package", {})
            info.description = info.description or pkg.get("description", "")
            info.dependencies += list(data.get("dependencies", {}).keys())
            info.dev_dependencies += list(data.get("dev-dependencies", {}).keys())
        except Exception:
            pass

    def _parse_gemfile(self, info: ProjectInfo) -> None:
        path = self.repo_path / "Gemfile"
        if not path.exists():
            return
        try:
            for line in path.read_text().splitlines():
                match = re.match(r"^\s*gem\s+['\"]([^'\"]+)['\"]", line)
                if match:
                    info.dependencies.append(match.group(1))
        except Exception:
            pass

    def _detect_env_vars(self, info: ProjectInfo) -> None:
        """Extract env var names from .env.example or source code."""
        env_example = self.repo_path / ".env.example"
        if env_example.exists():
            for line in env_example.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key = line.split("=")[0].strip()
                    if key:
                        info.env_vars.append(key)

    def _detect_features(self, info: ProjectInfo) -> None:
        """Detect structural features: tests, docker, CI, docs."""
        root = self.repo_path

        # Tests
        info.has_tests = any([
            (root / "tests").is_dir(),
            (root / "test").is_dir(),
            (root / "spec").is_dir(),
            any(root.glob("test_*.py")),
            any(root.glob("*_test.go")),
            any(root.glob("*.test.js")),
            any(root.glob("*.spec.ts")),
        ])

        # Docker
        info.has_docker = (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists()

        # CI
        info.has_ci = (root / ".github" / "workflows").is_dir() or (root / ".gitlab-ci.yml").exists()

        # Docs
        info.has_docs = (root / "docs").is_dir() or any(root.glob("*.md"))

        # License
        for fname in ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"):
            lpath = root / fname
            if lpath.exists():
                text = lpath.read_text()
                if "MIT" in text:
                    info.license_type = "MIT"
                elif "Apache" in text:
                    info.license_type = "Apache-2.0"
                elif "GPL" in text:
                    info.license_type = "GPL-3.0"
                elif "BSD" in text:
                    info.license_type = "BSD"
                else:
                    info.license_type = "Custom"
                break

    def _build_file_tree(self, max_depth: int = 3, max_items: int = 30) -> str:
        """Build a compact ASCII file tree."""
        skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".mypy_cache"}
        lines: list[str] = [self.repo_path.name + "/"]
        count = [0]

        def walk(path: Path, prefix: str, depth: int) -> None:
            if depth > max_depth or count[0] >= max_items:
                return
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
            for i, entry in enumerate(entries):
                if entry.name in skip or entry.name.startswith("."):
                    continue
                if count[0] >= max_items:
                    lines.append(prefix + "└── ...")
                    return
                connector = "└── " if i == len(entries) - 1 else "├── "
                lines.append(prefix + connector + entry.name + ("/" if entry.is_dir() else ""))
                count[0] += 1
                if entry.is_dir():
                    extension = "    " if i == len(entries) - 1 else "│   "
                    walk(entry, prefix + extension, depth + 1)

        walk(self.repo_path, "", 1)
        return "\n".join(lines)

    def __del__(self) -> None:
        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
