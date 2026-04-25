import requests
from project_scanner import scan_project
from chunker import split_cpp_code

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "deepseek-coder"


def ask_llm(code, file_path):
    prompt = f"""
You are a senior C++ project-level analyzer.

File: {file_path}

Return ONLY:
BUG:
CAUSE:
FIX:
SEVERITY:

Code:
{code}
"""

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
            return f"ERROR {response.status_code}: {response.text[:200]}"

        return response.json().get("response", "")

    except Exception as e:
        return f"REQUEST ERROR: {e}"


def analyze_project(path):
    files = scan_project(path)

    results = []

    for file_path in files:
        print(f"\nANALYZING FILE: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()

            chunks = split_cpp_code(code)

            file_results = []

            for i, chunk in enumerate(chunks):
                print(f"  → chunk {i+1}/{len(chunks)}")

                result = ask_llm(chunk, file_path)

                file_results.append(result)

            results.append({
                "file": file_path,
                "chunks": file_results
            })

        except Exception as e:
            results.append({
                "file": file_path,
                "error": str(e)
            })

    return results


if __name__ == "__main__":
    path = input("Project path: ")

    results = analyze_project(path)

    print("\n\n===== FINAL REPORT =====\n")

    for r in results:
        print("\n----------------------")
        print("FILE:", r["file"])
        print(r["analysis"])