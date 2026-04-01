"""Anthropic Claude LLM client."""

import logging

from piqued.llm.base import LLMResponse

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Anthropic Claude API client conforming to LLMClient protocol."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "",
    ):
        self._api_key = api_key
        self._model_name = model
        self._base_url = base_url or None
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        client = self._get_client()

        kwargs: dict = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        # Claude doesn't have a native json_mode — instruct via system prompt
        if json_mode and system_prompt:
            kwargs["system"] = system_prompt + "\n\nRespond with valid JSON only."
        elif json_mode:
            kwargs["system"] = "Respond with valid JSON only."

        response = await client.messages.create(**kwargs)

        text = response.content[0].text if response.content else ""
        tokens_used = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0

        return LLMResponse(text=text, tokens_used=tokens_used, model=self._model_name)
