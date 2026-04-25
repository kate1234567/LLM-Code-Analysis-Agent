import os


def normalize_path(path):
    if not path:
        return ""
    return os.path.normcase(os.path.abspath(path))


def get_context(context_map, file_path):
    norm_target = normalize_path(file_path)

    for path, ctx in context_map.items():
        if normalize_path(path) == norm_target:
            return ctx

    return {}


def find_reverse_dependencies(target_file, context_map, graph):
    result = []
    target_name = os.path.basename(target_file).lower()

    for file_path, node in graph.items():
        if normalize_path(file_path) == normalize_path(target_file):
            continue

        includes = node.get("includes", []) if isinstance(node, dict) else []

        for inc in includes:
            if os.path.basename(inc).lower() == target_name:
                ctx = get_context(context_map, file_path)
                result.append({
                    "path": file_path,
                    "symbols": ctx.get("symbols", {}),
                    "code": ctx.get("file_code", "")[:700]
                })
                break

    return result[:3]


def build_project_summary(context_map, graph):
    files = list(context_map.keys())

    cpp_count = sum(1 for f in files if f.lower().endswith((".cpp", ".cc", ".cxx")))
    header_count = sum(1 for f in files if f.lower().endswith((".h", ".hpp")))

    dependency_edges = 0
    for _, node in graph.items():
        if isinstance(node, dict):
            dependency_edges += len(node.get("includes", []))

    return {
        "files_count": len(files),
        "cpp_count": cpp_count,
        "header_count": header_count,
        "graph_nodes": len(graph),
        "dependency_edges": dependency_edges
    }


def build_selected_context(target_file, context_map, graph):
    file_context = get_context(context_map, target_file)

    paired_header = file_context.get("paired_header", {}) or {}
    related_cpp = file_context.get("related_cpp", {}) or {}
    direct_dependencies = file_context.get("dependencies", []) or []

    reverse_dependencies = find_reverse_dependencies(
        target_file=target_file,
        context_map=context_map,
        graph=graph
    )

    return {
        "target_file": target_file,
        "file_code": file_context.get("file_code", ""),
        "diff": file_context.get("diff", ""),
        "symbols": file_context.get("symbols", {
            "classes": [],
            "structs": [],
            "functions": []
        }),
        "paired_header": paired_header,
        "related_cpp": related_cpp,
        "direct_dependencies": direct_dependencies,
        "reverse_dependencies": reverse_dependencies,
        "project_summary": build_project_summary(context_map, graph)
    }