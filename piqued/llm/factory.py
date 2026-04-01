"""Factory for creating LLM clients from provider configuration."""

import logging

from piqued.llm.base import LLMClient

logger = logging.getLogger(__name__)

PROVIDERS = {"gemini", "openai", "claude", "ollama"}


def create_client(
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
) -> LLMClient:
    """Create an LLM client for the given provider.

    Args:
        provider: One of 'gemini', 'openai', 'claude', 'ollama'.
        model: Model name (e.g. 'gemini-2.5-flash', 'gpt-4o-mini', 'claude-sonnet-4-20250514').
        api_key: API key (required for gemini/openai/claude, unused for ollama).
        base_url: Base URL override (ollama, or OpenAI-compatible endpoints).

    Returns:
        An LLMClient instance.

    Raises:
        ValueError: If provider is not supported.
    """
    provider = provider.lower().strip()

    if provider == "gemini":
        from piqued.llm.gemini import GeminiClient

        return GeminiClient(api_key=api_key, model=model)

    elif provider == "openai":
        from piqued.llm.openai_client import OpenAIClient

        return OpenAIClient(api_key=api_key, model=model, base_url=base_url)

    elif provider == "claude":
        from piqued.llm.claude import ClaudeClient

        return ClaudeClient(api_key=api_key, model=model, base_url=base_url)

    elif provider == "ollama":
        from piqued.llm.ollama import OllamaClient

        kwargs: dict = {"model": model}
        if base_url:
            kwargs["base_url"] = base_url
        return OllamaClient(**kwargs)

    else:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. Supported: {', '.join(sorted(PROVIDERS))}"
        )
