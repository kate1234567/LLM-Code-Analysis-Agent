import os
import re

CLASS_REGEX = re.compile(r'\bclass\s+([A-Za-z_]\w*)')
STRUCT_REGEX = re.compile(r'\bstruct\s+([A-Za-z_]\w*)')

# простое приближение для функций/методов
FUNCTION_REGEX = re.compile(
    r'(?:[A-Za-z_]\w*::)?([A-Za-z_]\w*)\s*\([^;{}()]*\)\s*(?:const)?\s*\{'
)


def extract_symbols_from_code(code):
    classes = CLASS_REGEX.findall(code)
    structs = STRUCT_REGEX.findall(code)
    functions = FUNCTION_REGEX.findall(code)

    # убираем служебные слова/шум
    filtered_functions = []
    ignored = {"if", "for", "while", "switch", "catch"}

    for fn in functions:
        if fn not in ignored:
            filtered_functions.append(fn)

    return {
        "classes": sorted(set(classes)),
        "structs": sorted(set(structs)),
        "functions": sorted(set(filtered_functions))
    }


def extract_symbols_from_file(file_path, max_chars=10000):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()[:max_chars]
        return extract_symbols_from_code(code)
    except Exception:
        return {
            "classes": [],
            "structs": [],
            "functions": []
        }


def build_symbol_index(project_path):
    symbol_index = {}

    for root, _, files in os.walk(project_path):
        for file in files:
            if file.endswith(".cpp") or file.endswith(".h") or file.endswith(".hpp"):
                full_path = os.path.join(root, file)
                symbol_index[full_path] = extract_symbols_from_file(full_path)

    return symbol_index


if __name__ == "__main__":
    project_path = input("Project path: ")
    symbol_index = build_symbol_index(project_path)

    print("\n===== SYMBOL INDEX =====\n")

    for file_path, symbols in symbol_index.items():
        print("FILE:", file_path)
        print("  classes:", symbols["classes"])
        print("  structs:", symbols["structs"])
        print("  functions:", symbols["functions"])
        print()