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

    target_norm = normalize_path(target_file)
    target_base = os.path.basename(target_file).lower()
    target_name = os.path.splitext(target_base)[0].lower()

    for file_path, node in graph.items():
        if normalize_path(file_path) == target_norm:
            continue

        includes = node.get("includes", []) if isinstance(node, dict) else []

        found = False

        for inc in includes:
            inc_normalized = inc.replace("\\", "/").lower()

            inc_base = os.path.basename(inc_normalized)
            inc_name = os.path.splitext(inc_base)[0]

            python_style = inc_normalized.replace(".", "/")
            python_last = python_style.split("/")[-1]

            candidates = {
                inc_normalized,
                inc_base,
                inc_name,
                python_last
            }

            if (
                target_base in candidates
                or target_name in candidates
                or target_name in inc_normalized
            ):
                found = True
                break

        if found:
            ctx = get_context(context_map, file_path)

            result.append({
                "path": file_path,
                "symbols": ctx.get("symbols", {}),
                "code": ctx.get("file_code", "")[:700]
            })

    return result[:5]


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

    imported_modules_context = []

    for dep in direct_dependencies:
        dep_name = str(dep).lower()

        for path, ctx in context_map.items():
            file_name = os.path.basename(path).lower()
            file_without_ext = os.path.splitext(file_name)[0]

            if (
                    dep_name == file_name
                    or dep_name == file_without_ext
                    or dep_name.endswith(file_without_ext)
            ):
                imported_modules_context.append({
                    "path": path,
                    "code": ctx.get("file_code", "")[:1000],
                    "symbols": ctx.get("symbols", {})
                })
                break

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
        "project_summary": build_project_summary(context_map, graph),
        "imported_modules_context": imported_modules_context,
    }