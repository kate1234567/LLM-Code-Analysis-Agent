import os
import re

INCLUDE_REGEX = re.compile(r'#include\s*[<"]([^">]+)[">]')

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
    return filename.endswith(".cpp") or filename.endswith(".h") or filename.endswith(".hpp")


def build_graph(project_path):
    graph = {}

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in {".vs", "x64", "Debug", "Release", "build"}]

        for file in files:
            if not is_code_file(file):
                continue

            full_path = os.path.join(root, file)

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
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

            graph[full_path] = {
                "includes": deps,
                "type": os.path.splitext(file)[1]
            }

    return graph


def print_tree(graph):
    print("\n===== PROJECT DEPENDENCY TREE =====\n")

    for file, data in graph.items():
        print(file)

        if not data["includes"]:
            print("   └── (no dependencies)")
        else:
            for dep in data["includes"]:
                print(f"   ├── {dep}")

        print()


if __name__ == "__main__":
    path = input("Project path: ")
    graph = build_graph(path)
    print_tree(graph)