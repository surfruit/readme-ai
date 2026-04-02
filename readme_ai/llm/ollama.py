"""Ollama local LLM client — runs 100% offline."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

import httpx

from readme_ai.llm.base import BaseLLMClient, GeneratedContent

if TYPE_CHECKING:
    from readme_ai.analyzer import ProjectInfo
    from readme_ai.sampler import CodeSample

DEFAULT_MODEL = "llama3"

# Compact prompt for Ollama — local models have smaller context windows
OLLAMA_SYSTEM = (
    "You are a technical writer. Respond ONLY with a valid JSON object. "
    "No explanation, no markdown fences, no text before or after the JSON."
)


def build_ollama_prompt(project_info: "ProjectInfo", code_samples: list["CodeSample"]) -> str:
    """Shorter prompt optimized for local models."""
    samples_text = "\n\n".join(
        f"File: {s.path}\n```{s.language}\n{s.content[:2000]}\n```"
        for s in code_samples[:5]  # limit to 5 files for local models
    )
    deps = ", ".join(project_info.dependencies[:15]) or "none"
    frameworks = ", ".join(project_info.frameworks) or "none"

    return f"""Project: {project_info.name}
Language: {project_info.language}
Frameworks: {frameworks}
Dependencies: {deps}
Has tests: {project_info.has_tests}
Has Docker: {project_info.has_docker}
Env vars: {', '.join(project_info.env_vars[:8]) or 'none'}

File structure:
{project_info.file_tree}

Code samples:
{samples_text or 'none'}

Return a JSON object with EXACTLY these keys (all required, use empty string if unknown):
{{
  "tagline": "one sentence, max 12 words",
  "description": "2-3 sentences about what this project does",
  "features": ["feature 1", "feature 2", "feature 3", "feature 4"],
  "installation": "installation steps in markdown",
  "quick_start": "minimal usage example in markdown",
  "usage_examples": "2 usage examples in markdown",
  "api_overview": "CLI commands or API overview, or empty string",
  "configuration": "configuration options, or empty string",
  "roadmap": ["planned feature 1", "planned feature 2"]
}}"""


class OllamaClient(BaseLLMClient):
    def __init__(self, host: str = "http://localhost:11434", model: Optional[str] = None) -> None:
        self.host = host.rstrip("/")
        self.model = model or DEFAULT_MODEL

    def generate(self, project_info: "ProjectInfo", code_samples: list["CodeSample"]) -> GeneratedContent:
        # Check Ollama is running
        try:
            with httpx.Client(timeout=5) as client:
                client.get(f"{self.host}/api/tags")
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.host}. "
                f"Is Ollama running? Try: ollama serve"
            ) from e

        prompt = build_ollama_prompt(project_info, code_samples)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": OLLAMA_SYSTEM,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 2048,   # enough for full JSON
                "num_ctx": 8192,       # context window
                "stop": ["\n\n\n"],    # stop at triple newline
            },
        }

        with httpx.Client(timeout=300) as client:
            response = client.post(f"{self.host}/api/generate", json=payload)
            response.raise_for_status()

        raw = response.json().get("response", "")
        raw = raw.strip()

        # Try to recover truncated JSON by finding the opening brace
        # and attempting to close any open structures
        if raw and not raw.endswith("}"):
            raw = self._repair_json(raw)

        return self._parse_response(raw)

    def _repair_json(self, raw: str) -> str:
        """Attempt to repair truncated JSON from local models."""
        # Find start of JSON object
        start = raw.find("{")
        if start == -1:
            return raw
        raw = raw[start:]

        # Count open braces and brackets to close them
        stack = []
        in_string = False
        escape_next = False

        for i, ch in enumerate(raw):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]":
                if stack and stack[-1] == ch:
                    stack.pop()

        # Close any open strings first
        if in_string:
            raw += '"'

        # Close open structures in reverse order
        closing = "".join(reversed(stack))

        # If we're inside an array value, close it properly
        if raw.rstrip().endswith(","):
            raw = raw.rstrip().rstrip(",")

        raw += closing
        return raw
