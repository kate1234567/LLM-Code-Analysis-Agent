import re
import os


def extract_declared_functions(file_code):
    functions = []

    patterns = [
        r"\bdef\s+([A-Za-z_]\w*)\s*\(",
        r"\bfunction\s+([A-Za-z_]\w*)\s*\(",
        r"\b(?:void|int|long|double|float|bool|char|std::string|string|auto)\s+([A-Za-z_]\w*)\s*\("
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, file_code):
            functions.append(match.group(1))

    return sorted(set(functions))


def extract_function_calls(file_code):
    calls = []

    ignored = {
        "if", "for", "while", "switch", "catch", "return",
        "sizeof", "print", "printf", "cout", "cin"
    }

    for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", file_code):
        name = match.group(1)

        if name not in ignored:
            calls.append(name)

    return sorted(set(calls))


def build_function_call_graph(context_map):
    graph = {}

    declared_by_file = {}

    for file_path, data in context_map.items():
        code = data.get("file_code", "")
        declared = extract_declared_functions(code)
        calls = extract_function_calls(code)

        declared_by_file[file_path] = declared

        graph[file_path] = {
            "file": file_path,
            "declared_functions": declared,
            "called_functions": calls,
            "internal_calls": [],
            "external_calls": []
        }

    all_declared = {}

    for file_path, functions in declared_by_file.items():
        for fn in functions:
            all_declared.setdefault(fn, []).append(file_path)

    for file_path, node in graph.items():
        for call in node["called_functions"]:
            owners = all_declared.get(call, [])

            if file_path in owners:
                node["internal_calls"].append(call)
            elif owners:
                node["external_calls"].append({
                    "function": call,
                    "defined_in": owners
                })

    return graph