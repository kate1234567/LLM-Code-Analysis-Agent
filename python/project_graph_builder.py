import os
import re
from project_scanner import scan_project, detect_language


def normalize_path(path):
    return os.path.abspath(path).replace("\\", "/")


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def extract_dependencies(file_path, code):
    language = detect_language(file_path)
    deps = []

    patterns = []

    if language in {"cpp", "c"}:
        patterns = [
            r'#include\s*[<"]([^>"]+)[>"]'
        ]

    elif language == "python":
        patterns = [
            r'^\s*import\s+([A-Za-z_][\w\.]*)',
            r'^\s*from\s+([A-Za-z_][\w\.]*)\s+import\s+'
        ]

    elif language in {"javascript", "typescript"}:
        patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
        ]

    elif language == "java":
        patterns = [
            r'^\s*import\s+([A-Za-z_][\w\.]*);'
        ]

    elif language == "csharp":
        patterns = [
            r'^\s*using\s+([A-Za-z_][\w\.]*);'
        ]

    elif language == "go":
        patterns = [
            r'import\s+"([^"]+)"',
            r'^\s*"([^"]+)"'
        ]

    for pattern in patterns:
        for match in re.finditer(pattern, code, flags=re.MULTILINE):
            deps.append(match.group(1))

    return sorted(set(deps))


def build_file_index(code_files):
    index = {}

    for path in code_files:
        normalized = normalize_path(path)
        base = os.path.basename(path)
        name_without_ext = os.path.splitext(base)[0]

        index[base.lower()] = normalized
        index[name_without_ext.lower()] = normalized

    return index


def resolve_dependency(dep, file_index):
    dep = dep.replace("\\", "/").strip()

    dep_base = os.path.basename(dep)
    dep_name = os.path.splitext(dep_base)[0]

    python_style = dep.replace(".", "/")
    python_last = python_style.split("/")[-1]

    candidates = [
        dep.lower(),
        dep_base.lower(),
        dep_name.lower(),
        python_last.lower(),
        python_style.lower(),
    ]

    for candidate in candidates:
        if candidate in file_index:
            return file_index[candidate]

    for key, value in file_index.items():
        if python_last.lower() in key:
            return value

    return None


def build_graph(project_path):
    scan_data = scan_project(project_path)
    code_files = scan_data.get("code_files", [])

    file_index = build_file_index(code_files)
    graph = {}

    for file_path in code_files:
        normalized_path = normalize_path(file_path)
        code = read_file(file_path)
        language = detect_language(file_path)

        deps = extract_dependencies(file_path, code)

        resolved_dependencies = []

        for dep in deps:
            resolved = resolve_dependency(dep, file_index)

            resolved_dependencies.append({
                "dependency": dep,
                "resolved_path": resolved,
                "resolved": resolved is not None
            })

        graph[normalized_path] = {
            "path": normalized_path,
            "language": language,
            "includes": deps,
            "dependencies": resolved_dependencies,
            "resolved_dependencies_count": len([
                item for item in resolved_dependencies
                if item.get("resolved")
            ])
        }

    for file_path in graph:
        graph[file_path]["reverse_dependencies"] = []

    for file_path, node in graph.items():
        for dep in node["dependencies"]:
            resolved = dep.get("resolved_path")

            if resolved and resolved in graph:
                graph[resolved]["reverse_dependencies"].append(file_path)

    return graph