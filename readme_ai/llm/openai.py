"""OpenAI LLM client."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

import httpx

from readme_ai.llm.base import BaseLLMClient, GeneratedContent, SYSTEM_PROMPT, build_user_prompt

if TYPE_CHECKING:
    from readme_ai.analyzer import ProjectInfo
    from readme_ai.sampler import CodeSample

DEFAULT_MODEL = "gpt-4o-mini"
API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or pass --api-key."
            )
        self.model = model or DEFAULT_MODEL

    def generate(self, project_info: "ProjectInfo", code_samples: list["CodeSample"]) -> GeneratedContent:
        prompt = build_user_prompt(project_info, code_samples)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(
                API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        raw = data["choices"][0]["message"]["content"]
        return self._parse_response(raw)
