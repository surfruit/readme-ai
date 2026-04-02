"""Samples representative code files from a repository for LLM context."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Files that give the most context about a project
HIGH_PRIORITY_NAMES = {
    "main.py", "app.py", "server.py", "index.py",
    "main.go", "main.rs", "main.js", "index.js", "index.ts",
    "app.js", "app.ts", "server.js", "server.ts",
    "cli.py", "cli.go", "cli.rs",
    "lib.rs", "lib.py",
    "__main__.py",
    "Makefile",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".mypy_cache", "coverage",
    "migrations", ".tox", "eggs", ".eggs", "htmlcov",
}

SKIP_EXTENSIONS = {
    ".min.js", ".min.css", ".map", ".lock",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo",
    ".zip", ".tar", ".gz", ".exe", ".bin",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".rb", ".java", ".kt",
    ".swift", ".cpp", ".c", ".cs", ".php",
    ".vue", ".svelte", ".ex", ".exs",
    ".hs", ".scala", ".clj", ".r", ".jl",
    ".lua", ".dart", ".zig", ".nim", ".ml",
    ".sh", ".bash",
}

MAX_FILE_BYTES = 8_000
MAX_TOTAL_BYTES = 40_000


@dataclass
class CodeSample:
    path: str
    content: str
    language: str
    priority: int  # lower = higher priority


class CodeSampler:
    """Selects the most informative code samples within a token budget."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def sample(self) -> list[CodeSample]:
        candidates = self._collect_candidates()
        candidates.sort(key=lambda s: s.priority)
        return self._fit_to_budget(candidates)

    def _collect_candidates(self) -> list[CodeSample]:
        samples: list[CodeSample] = []

        for path in self.repo_path.rglob("*"):
            # Skip dirs and hidden/vendor paths
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue

            # Skip by extension combos (e.g. .min.js)
            name_lower = path.name.lower()
            if any(name_lower.endswith(ext) for ext in SKIP_EXTENSIONS):
                continue

            suffix = path.suffix.lower()
            if suffix not in CODE_EXTENSIONS:
                continue

            # Skip very large files
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES * 5:
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            if not content.strip():
                continue

            content = self._truncate(content)
            priority = self._score(path, content)
            rel = str(path.relative_to(self.repo_path))
            lang = _ext_to_lang(suffix)
            samples.append(CodeSample(path=rel, content=content, language=lang, priority=priority))

        return samples

    def _truncate(self, content: str) -> str:
        """Trim to MAX_FILE_BYTES, keeping the top of the file."""
        if len(content.encode()) > MAX_FILE_BYTES:
            content = content[:MAX_FILE_BYTES] + "\n# ... (truncated)"
        return content

    def _score(self, path: Path, content: str) -> int:
        """Lower score = higher priority."""
        score = 50

        # Reward high-priority filenames
        if path.name.lower() in HIGH_PRIORITY_NAMES:
            score -= 30

        # Reward shallow paths (closer to root)
        depth = len(path.relative_to(self.repo_path).parts)
        score += depth * 3

        # Reward files with docstrings or comments (informative)
        if re.search(r'""".*?"""', content, re.DOTALL) or "/**" in content:
            score -= 5

        # Penalise test files (still useful but lower priority)
        if "test" in path.stem.lower() or "spec" in path.stem.lower():
            score += 20

        # Penalise generated files
        if "generated" in content[:200].lower() or "do not edit" in content[:200].lower():
            score += 40

        return score

    def _fit_to_budget(self, candidates: list[CodeSample]) -> list[CodeSample]:
        """Keep top files within MAX_TOTAL_BYTES budget."""
        selected: list[CodeSample] = []
        total = 0
        for sample in candidates:
            size = len(sample.content.encode())
            if total + size > MAX_TOTAL_BYTES:
                break
            selected.append(sample)
            total += size
        return selected


def _ext_to_lang(ext: str) -> str:
    mapping = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "jsx", ".tsx": "tsx", ".go": "go", ".rs": "rust",
        ".rb": "ruby", ".java": "java", ".kt": "kotlin",
        ".swift": "swift", ".cpp": "cpp", ".c": "c",
        ".cs": "csharp", ".php": "php", ".vue": "vue",
        ".svelte": "svelte", ".sh": "bash", ".bash": "bash",
    }
    return mapping.get(ext, "text")
