"""Anthropic Claude LLM client."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

import httpx

from readme_ai.llm.base import BaseLLMClient, GeneratedContent, SYSTEM_PROMPT, build_user_prompt

if TYPE_CHECKING:
    from readme_ai.analyzer import ProjectInfo
    from readme_ai.sampler import CodeSample

DEFAULT_MODEL = "claude-3-haiku-20240307"
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass --api-key."
            )
        self.model = model or DEFAULT_MODEL

    def generate(self, project_info: "ProjectInfo", code_samples: list["CodeSample"]) -> GeneratedContent:
        prompt = build_user_prompt(project_info, code_samples)
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(
                API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        raw = data["content"][0]["text"]
        return self._parse_response(raw)
