"""Ollama LLM client implementation (local models via REST API)."""

import logging

import httpx

from piqued.llm.base import LLMResponse

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama REST API client conforming to LLMClient protocol."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        api_key: str = "",  # unused, kept for interface consistency
    ):
        self._model_name = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        payload: dict = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system_prompt:
            payload["system"] = system_prompt
        if json_mode:
            payload["format"] = "json"
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        resp = await self._client.post(
            f"{self._base_url}/api/generate",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        text = data.get("response", "")
        # Ollama reports tokens in eval_count + prompt_eval_count
        tokens_used = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)

        return LLMResponse(text=text, tokens_used=tokens_used, model=self._model_name)
