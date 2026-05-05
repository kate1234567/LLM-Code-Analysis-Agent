def build_structural_graph(clang_ast_report, dependency_graph, function_graph):
    nodes = []
    edges = []

    for file_path, ast_data in clang_ast_report.items():
        file_id = f"file:{file_path}"

        nodes.append({
            "id": file_id,
            "type": "file",
            "label": file_path
        })

        for cls in ast_data.get("classes", []):
            class_name = cls.get("name", "unknown")
            class_id = f"class:{file_path}:{class_name}"

            nodes.append({
                "id": class_id,
                "type": "class",
                "label": class_name,
                "file": file_path,
                "fields_count": cls.get("fields_count", 0),
                "methods_count": cls.get("methods_count", 0)
            })

            edges.append({
                "from": file_id,
                "to": class_id,
                "type": "contains_class"
            })

            if cls.get("raw_pointer_fields_count", 0) > 0:
                edges.append({
                    "from": class_id,
                    "to": file_id,
                    "type": "ownership_risk"
                })

    for file_path, node in dependency_graph.items():
        if not isinstance(node, dict):
            continue

        for include in node.get("includes", []):
            edges.append({
                "from": f"file:{file_path}",
                "to": f"include:{include}",
                "type": "include_dependency"
            })

    for file_path, node in function_graph.items():
        for call in node.get("external_calls", []):
            edges.append({
                "from": f"file:{file_path}",
                "to": f"call:{call}",
                "type": "function_call"
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "nodes_count": len(nodes),
        "edges_count": len(edges),
        "graph_types": [
            "file_dependency_graph",
            "function_call_graph",
            "class_structure_graph",
            "ownership_risk_graph"
        ]
    }