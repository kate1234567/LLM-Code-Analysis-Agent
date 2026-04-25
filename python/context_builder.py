import os
from symbol_extractor import build_symbol_index


def safe_read_file(file_path, max_chars=3000):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()[:max_chars]
    except Exception:
        return ""


def resolve_local_dependency(project_path, dependency):
    for root, _, files in os.walk(project_path):
        for f in files:
            if f == os.path.basename(dependency):
                return os.path.join(root, f)
    return None


def build_file_context(project_path, file_path, graph, symbol_index, max_dependency_files=3):
    file_node = graph.get(file_path, {})

    if isinstance(file_node, list):
        includes = file_node
    else:
        includes = file_node.get("includes", [])

    dependency_contexts = []

    for dep in includes[:max_dependency_files]:
        dep_path = resolve_local_dependency(project_path, dep)

        if dep_path:
            dependency_contexts.append({
                "dependency": dep,
                "path": dep_path,
                "code": safe_read_file(dep_path, max_chars=1500),
                "symbols": symbol_index.get(dep_path, {
                    "classes": [],
                    "structs": [],
                    "functions": []
                })
            })
        else:
            dependency_contexts.append({
                "dependency": dep,
                "path": None,
                "code": "",
                "symbols": {
                    "classes": [],
                    "structs": [],
                    "functions": []
                }
            })

    context = {
        "file": file_path,
        "file_code": safe_read_file(file_path, max_chars=3000),
        "symbols": symbol_index.get(file_path, {
            "classes": [],
            "structs": [],
            "functions": []
        }),
        "dependencies": dependency_contexts
    }

    return context


def build_project_context(project_path, graph):
    context_map = {}
    symbol_index = build_symbol_index(project_path)

    for file_path in graph.keys():
        context_map[file_path] = build_file_context(
            project_path,
            file_path,
            graph,
            symbol_index
        )

    return context_map


if __name__ == "__main__":
    from project_graph_builder import build_graph

    project_path = input("Project path: ")
    graph = build_graph(project_path)
    context_map = build_project_context(project_path, graph)

    print("\n===== PROJECT CONTEXT =====\n")

    for file_path, ctx in context_map.items():
        print("FILE:", file_path)
        print("SYMBOLS:", ctx["symbols"])
        print("DEPENDENCIES:")
        for dep in ctx["dependencies"]:
            print("  -", dep["dependency"], "| path:", dep["path"], "| symbols:", dep["symbols"])
        print()