"""LLM client protocol and response dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    text: str
    tokens_used: int = 0
    model: str = ""


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM providers. Implementations must be async."""

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The user/content prompt.
            system_prompt: Optional system instructions.
            json_mode: If True, request JSON output format.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Max output tokens (None = provider default).

        Returns:
            LLMResponse with text, token count, and model name.
        """
        ...
