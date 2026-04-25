import os
import json
import requests
from typing import Optional


class BaseLLMClient:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class OllamaClient(BaseLLMClient):
    def __init__(
        self,
        model: str = "deepseek-coder",
        url: str = "http://localhost:11434/api/generate",
        timeout: int = 60
    ):
        self.model = model
        self.url = url
        self.timeout = timeout

        for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            os.environ.pop(k, None)

        os.environ["NO_PROXY"] = "localhost,127.0.0.1"

        self.session = requests.Session()
        self.session.trust_env = False

    def generate(self, prompt: str) -> str:
        response = self.session.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0
                }
            },
            timeout=self.timeout
        )

        print("\n=== LLM DEBUG ===")
        print("PROVIDER: ollama")
        print("STATUS:", response.status_code)
        print("RAW:", response.text[:300])
        print("=================\n")

        if response.status_code != 200:
            raise RuntimeError(f"Ollama error: status={response.status_code}")

        payload = response.json()
        return payload.get("response", "")


class MockClient(BaseLLMClient):
    def generate(self, prompt: str) -> str:
        return json.dumps({
            "bug": None
        })


class OpenAIClient(BaseLLMClient):
    def __init__(self, model: str = "gpt-4.1-mini", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

    def generate(self, prompt: str) -> str:
        raise NotImplementedError(
            "OpenAIClient placeholder is ready, but API request is not implemented yet"
        )


class QwenClient(BaseLLMClient):
    def __init__(self, model: str = "qwen-code"):
        self.model = model

    def generate(self, prompt: str) -> str:
        raise NotImplementedError(
            "QwenClient placeholder is ready, but CLI/API request is not implemented yet"
        )


def create_llm_client(provider: str = "ollama", model: Optional[str] = None) -> BaseLLMClient:
    provider = (provider or "ollama").lower()

    if provider == "ollama":
        return OllamaClient(model=model or "deepseek-coder")

    if provider == "mock":
        return MockClient()

    if provider == "openai":
        return OpenAIClient(model=model or "gpt-4.1-mini")

    if provider == "qwen":
        return QwenClient(model=model or "qwen-code")

    raise ValueError(f"Unknown LLM provider: {provider}")