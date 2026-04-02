"""Gemini LLM client implementation using the google-genai SDK."""

import logging

from piqued.llm.base import LLMResponse

logger = logging.getLogger(__name__)


class GeminiClient:
    """Google Gemini API client conforming to LLMClient protocol.

    Uses the new google-genai SDK (not the deprecated google-generativeai).
    Native async via client.aio.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._api_key = api_key
        self._model_name = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
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
        from google.genai import types

        client = self._get_client()

        config_kwargs: dict = {"temperature": temperature}
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        if max_tokens:
            config_kwargs["max_output_tokens"] = max_tokens
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        config = types.GenerateContentConfig(**config_kwargs)

        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )

        tokens_used = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_used = getattr(response.usage_metadata, "total_token_count", 0) or 0

        try:
            text = response.text or ""
        except ValueError:
            text = ""
            logger.warning(
                "Gemini returned no valid text (candidates: %s)",
                response.candidates[:1] if response.candidates else "none",
            )

        return LLMResponse(text=text, tokens_used=tokens_used, model=self._model_name)
