import sys
import requests
import os

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

os.environ["NO_PROXY"] = "localhost,127.0.0.1"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "deepseek-coder"


def ask_llm(prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120,
            proxies={"http": None, "https": None}
        )

        if response.status_code != 200:
            return f"HTTP ERROR: {response.status_code}\n{response.text[:300]}"

        data = response.json()
        return data.get("response", "NO RESPONSE FIELD")

    except Exception as e:
        return f"REQUEST FAILED: {e}"


def build_prompt(code):
    return f"""
You are a strict C++ static analysis engine.

Return ONLY valid structured output:

BUG: ...
CAUSE: ...
FIX: ...
SEVERITY: low | medium | high

Rules:
- No explanations outside format
- No extra text
- No markdown
- Be precise

Code:
{code}
"""


def main():
    code = sys.argv[1]

    prompt = build_prompt(code)

    result = ask_llm(prompt)
    print(result)


if __name__ == "__main__":
    main()