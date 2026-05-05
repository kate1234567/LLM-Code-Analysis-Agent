import os
import json
import requests
from typing import Optional, List


class BaseLLMClient:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class OllamaClient(BaseLLMClient):
    def __init__(self, model: str = "deepseek-coder", timeout: int = 60):
        self.model = model
        self.url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
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

        if response.status_code != 200:
            raise RuntimeError(f"Ollama error: status={response.status_code}")

        payload = response.json()
        return payload.get("response", "")


class OpenAIClient(BaseLLMClient):
    def __init__(self, model: str = "gpt-4.1-mini", api_key: Optional[str] = None, timeout: int = 60):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

    def generate(self, prompt: str) -> str:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a strict code review formatter. Return JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            timeout=self.timeout
        )

        if response.status_code != 200:
            raise RuntimeError(f"OpenAI error: status={response.status_code}, body={response.text[:300]}")

        payload = response.json()
        return payload["choices"][0]["message"]["content"]


class MockClient(BaseLLMClient):
    def generate(self, prompt: str) -> str:
        return json.dumps({
            "bug": None
        })


class FallbackLLMClient(BaseLLMClient):
    def __init__(self, clients: List[BaseLLMClient]):
        self.clients = clients

    def generate(self, prompt: str) -> str:
        last_error = None

        for client in self.clients:
            try:
                print("TRY LLM PROVIDER:", client.__class__.__name__)
                return client.generate(prompt)
            except Exception as e:
                last_error = e
                print("LLM PROVIDER FAILED:", client.__class__.__name__, str(e))

        raise RuntimeError(f"All LLM providers failed: {last_error}")


def create_llm_client(provider: str = "auto", model: Optional[str] = None) -> BaseLLMClient:
    provider = (provider or "auto").lower()

    if provider == "ollama":
        return OllamaClient(model=model or "deepseek-coder")

    if provider == "openai":
        return OpenAIClient(model=model or "gpt-4.1-mini")

    if provider == "mock":
        return MockClient()

    if provider == "auto":
        clients = []

        clients.append(OllamaClient(model=model or "deepseek-coder"))

        if os.getenv("OPENAI_API_KEY"):
            clients.append(OpenAIClient(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini")))

        clients.append(MockClient())

        return FallbackLLMClient(clients)

    raise ValueError(f"Unknown LLM provider: {provider}")