"""Tests for LLM abstraction layer."""

import pytest

from piqued.llm.base import LLMClient, LLMResponse
from piqued.llm.factory import create_client


class TestLLMResponse:
    def test_defaults(self):
        r = LLMResponse(text="hello")
        assert r.text == "hello"
        assert r.tokens_used == 0
        assert r.model == ""

    def test_all_fields(self):
        r = LLMResponse(text="hi", tokens_used=100, model="test-model")
        assert r.tokens_used == 100
        assert r.model == "test-model"


class TestFactory:
    def test_gemini_creates_client(self):
        client = create_client("gemini", "gemini-2.5-flash", api_key="fake-key")
        assert isinstance(client, LLMClient)

    def test_ollama_creates_client(self):
        client = create_client("ollama", "llama3.2")
        assert isinstance(client, LLMClient)

    def test_ollama_custom_base_url(self):
        client = create_client("ollama", "llama3.2", base_url="http://myhost:11434")
        assert client._base_url == "http://myhost:11434"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_client("gpt4all", "some-model")

    def test_provider_case_insensitive(self):
        client = create_client("GEMINI", "gemini-2.5-flash", api_key="fake")
        assert isinstance(client, LLMClient)

    def test_provider_strips_whitespace(self):
        client = create_client("  ollama  ", "llama3.2")
        assert isinstance(client, LLMClient)


class TestProtocolConformance:
    """Verify that concrete clients satisfy the LLMClient protocol."""

    def test_gemini_is_llm_client(self):
        from piqued.llm.gemini import GeminiClient

        assert issubclass(GeminiClient, LLMClient)

    def test_ollama_is_llm_client(self):
        from piqued.llm.ollama import OllamaClient

        assert issubclass(OllamaClient, LLMClient)
