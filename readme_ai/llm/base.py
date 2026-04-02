"""Abstract base class for LLM clients and prompt construction."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from readme_ai.analyzer import ProjectInfo
    from readme_ai.sampler import CodeSample


@dataclass
class GeneratedContent:
    """Structured output from the LLM."""

    tagline: str = ""
    description: str = ""
    features: list[str] = field(default_factory=list)
    installation: str = ""
    quick_start: str = ""
    usage_examples: str = ""
    api_overview: str = ""
    configuration: str = ""
    roadmap: list[str] = field(default_factory=list)


SYSTEM_PROMPT = """\
You are an expert technical writer who specializes in open-source documentation.
Your job is to analyze a software project and generate a clear, accurate, and engaging README.
You write for developers — be precise, concrete, and avoid marketing fluff.
Always respond with valid JSON only. No markdown, no explanation outside JSON.
"""


def build_user_prompt(project_info: "ProjectInfo", code_samples: list["CodeSample"]) -> str:
    """Build the user prompt from project info and code samples."""
    samples_text = "\n\n".join(
        f"### {s.path}\n```{s.language}\n{s.content}\n```"
        for s in code_samples
    )

    deps_text = ", ".join(project_info.dependencies[:20]) or "none detected"
    frameworks_text = ", ".join(project_info.frameworks) or "none detected"

    return f"""
Analyze this software project and generate README content.

## Project Metadata
- Name: {project_info.name}
- Primary Language: {project_info.language}
- Frameworks: {frameworks_text}
- Main Dependencies: {deps_text}
- Has Tests: {project_info.has_tests}
- Has Docker: {project_info.has_docker}
- Has CI: {project_info.has_ci}
- Environment Variables: {', '.join(project_info.env_vars[:10]) or 'none'}
- Entry Points: {', '.join(project_info.entry_points) or 'none'}

## File Structure
```
{project_info.file_tree}
```

## Code Samples
{samples_text or "No code samples available."}

---

Based on the above, produce a JSON object with these exact keys:

{{
  "tagline": "One sharp sentence describing what this project does (max 15 words)",
  "description": "2-3 paragraph description of the project, its purpose, and who it's for",
  "features": ["list", "of", "5-8", "key", "features", "as", "short", "bullet", "strings"],
  "installation": "Step-by-step installation instructions in markdown (use code blocks)",
  "quick_start": "A minimal working example showing the most common use case (markdown with code block)",
  "usage_examples": "2-3 more usage examples showing different scenarios (markdown)",
  "api_overview": "Brief overview of public API / CLI commands if applicable (markdown table or list). Empty string if not applicable.",
  "configuration": "How to configure the project — env vars, config files, CLI flags. Empty string if none.",
  "roadmap": ["planned", "feature", "1", "planned", "feature", "2"]
}}

Be specific — reference actual function names, file names, and commands you see in the code.
Do not invent functionality that isn't in the code.
"""


class BaseLLMClient(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    def generate(
        self,
        project_info: "ProjectInfo",
        code_samples: list["CodeSample"],
    ) -> GeneratedContent:
        """Generate README content from project info."""
        ...

    def _parse_response(self, raw: str) -> GeneratedContent:
        """Parse JSON response into GeneratedContent."""
        # Strip markdown fences if model wrapped response
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw[:500]}") from e

        return GeneratedContent(
            tagline=data.get("tagline", ""),
            description=data.get("description", ""),
            features=data.get("features", []),
            installation=data.get("installation", ""),
            quick_start=data.get("quick_start", ""),
            usage_examples=data.get("usage_examples", ""),
            api_overview=data.get("api_overview", ""),
            configuration=data.get("configuration", ""),
            roadmap=data.get("roadmap", []),
        )
