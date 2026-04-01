"""OpenAI-compatible LLM client (works with OpenAI, Azure, and compatible APIs)."""

import logging

from piqued.llm.base import LLMResponse

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI API client conforming to LLMClient protocol."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "",
    ):
        self._api_key = api_key
        self._model_name = model
        self._base_url = base_url or None
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
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

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = await client.chat.completions.create(**kwargs)

        text = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        return LLMResponse(text=text, tokens_used=tokens_used, model=self._model_name)
