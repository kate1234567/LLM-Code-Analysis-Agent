import os
import re

INCLUDE_REGEX = re.compile(r'#include\s*[<"]([^">]+)[">]')
CLASS_REGEX = re.compile(r'\b(class|struct)\s+(\w+)(?:\s*:\s*public\s+(\w+))?')
RAW_POINTER_REGEX = re.compile(r'\b(\w+)\s*\*\s*(\w+)\s*;')

IGNORE_LIBS = {
    "iostream",
    "vector",
    "string",
    "map",
    "unordered_map",
    "memory",
    "cstdlib",
    "cstdio",
    "algorithm",
    "set",
    "regex",
    "filesystem",
    "fstream",
    "sstream",
    "array",
    "stdexcept"
}


def is_code_file(filename):
    return (
        filename.endswith(".cpp")
        or filename.endswith(".h")
        or filename.endswith(".hpp")
    )


def build_graph(project_path):
    graph = {}

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".vs",
                "x64",
                "Debug",
                "Release",
                "build"
            }
        ]

        for file in files:
            if not is_code_file(file):
                continue

            full_path = os.path.join(root, file)

            try:
                with open(
                    full_path,
                    "r",
                    encoding="utf-8",
                    errors="ignore"
                ) as f:
                    content = f.read()
            except Exception:
                continue

            includes = INCLUDE_REGEX.findall(content)

            deps = []
            for inc in includes:
                inc_name = os.path.basename(inc)

                if inc in IGNORE_LIBS or inc_name in IGNORE_LIBS:
                    continue

                deps.append(inc)

            classes = []
            inheritance = []
            raw_pointers = []

            for match in CLASS_REGEX.findall(content):
                class_name = match[1]
                parent = match[2]

                classes.append(class_name)

                if parent:
                    inheritance.append({
                        "child": class_name,
                        "parent": parent
                    })

            for match in RAW_POINTER_REGEX.findall(content):
                pointer_type = match[0]
                pointer_name = match[1]

                raw_pointers.append({
                    "type": pointer_type,
                    "name": pointer_name
                })

            graph[full_path] = {
                "includes": deps,
                "classes": classes,
                "inheritance": inheritance,
                "raw_pointers": raw_pointers,
                "type": os.path.splitext(file)[1]
            }

    return graph


def build_structural_graph(project_path):
    graph = build_graph(project_path)

    structural_nodes = 0
    structural_edges = 0
    graph_types = set()

    for file_data in graph.values():
        structural_nodes += 1

        structural_edges += len(file_data["includes"])
        if file_data["includes"]:
            graph_types.add("file_dependency_graph")

        structural_nodes += len(file_data["classes"])
        if file_data["classes"]:
            graph_types.add("class_structure_graph")

        structural_edges += len(file_data["inheritance"])
        if file_data["inheritance"]:
            graph_types.add("inheritance_graph")

        structural_edges += len(file_data["raw_pointers"])
        if file_data["raw_pointers"]:
            graph_types.add("ownership_risk_graph")

    return {
        "graph": graph,
        "structural_graph_nodes": structural_nodes,
        "structural_graph_edges": structural_edges,
        "structural_graph_types": list(graph_types)
    }


def print_tree(graph):
    print("\n===== PROJECT STRUCTURAL GRAPH =====\n")

    for file, data in graph.items():
        print(file)

        if data["includes"]:
            print("  Includes:")
            for dep in data["includes"]:
                print(f"    -> {dep}")

        if data["classes"]:
            print("  Classes:")
            for cls in data["classes"]:
                print(f"    -> {cls}")

        if data["inheritance"]:
            print("  Inheritance:")
            for item in data["inheritance"]:
                print(
                    f"    -> {item['child']} : {item['parent']}"
                )

        if data["raw_pointers"]:
            print("  Raw pointers:")
            for ptr in data["raw_pointers"]:
                print(
                    f"    -> {ptr['type']}* {ptr['name']}"
                )

        print()


if __name__ == "__main__":
    path = input("Project path: ")

    result = build_structural_graph(path)

    print_tree(result["graph"])

    print("\nSTRUCTURAL GRAPH BUILT:")
    print(
        f"STRUCTURAL NODES: "
        f"{result['structural_graph_nodes']}"
    )
    print(
        f"STRUCTURAL EDGES: "
        f"{result['structural_graph_edges']}"
    )
    print(
        f"GRAPH TYPES: "
        f"{result['structural_graph_types']}"
    )