"""LLM provider abstraction."""

from __future__ import annotations

from typing import Optional

from readme_ai.llm.base import BaseLLMClient, GeneratedContent
from readme_ai.llm.openai import OpenAIClient
from readme_ai.llm.anthropic import AnthropicClient
from readme_ai.llm.ollama import OllamaClient

__all__ = ["get_llm_client", "BaseLLMClient", "GeneratedContent"]


def get_llm_client(
    provider: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    ollama_host: str = "http://localhost:11434",
) -> BaseLLMClient:
    """Factory: return the right LLM client for the given provider."""
    provider = provider.lower().strip()

    if provider == "openai":
        return OpenAIClient(api_key=api_key, model=model)
    elif provider in ("anthropic", "claude"):
        return AnthropicClient(api_key=api_key, model=model)
    elif provider == "ollama":
        return OllamaClient(host=ollama_host, model=model)
    else:
        raise ValueError(
            f"Unknown provider: '{provider}'. "
            f"Supported: openai, anthropic, ollama"
        )
