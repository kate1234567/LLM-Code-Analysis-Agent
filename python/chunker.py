import re

def split_cpp_code(code: str):
    """
    Простейший chunker:
    режет код по функциям/блокам {}.
    """

    chunks = []
    buffer = []
    brace_level = 0

    lines = code.split("\n")

    for line in lines:
        stripped = line.strip()

        if "{" in stripped:
            brace_level += stripped.count("{")

        if brace_level > 0:
            buffer.append(line)

        if "}" in stripped:
            brace_level -= stripped.count("}")

            if brace_level == 0 and buffer:
                chunks.append("\n".join(buffer))
                buffer = []

    # fallback — если что-то осталось
    if buffer:
        chunks.append("\n".join(buffer))

    # если код без функций — вернём как один chunk
    if not chunks:
        chunks = [code]

    return chunks


if __name__ == "__main__":
    sample = """
int add(int a, int b) {
    return a + b;
}

int main() {
    int x = 5;
    return 0;
}
"""

    result = split_cpp_code(sample)

    for i, c in enumerate(result):
        print(f"\n--- CHUNK {i} ---\n")
        print(c)