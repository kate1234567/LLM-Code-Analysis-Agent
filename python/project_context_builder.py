import os
import re

def extract_includes(file_path):
    includes = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                match = re.match(r'\s*#include\s*[<"](.+?)[">]', line)
                if match:
                    includes.append(match.group(1))
    except:
        pass

    return includes


def build_project_graph(cpp_files):
    graph = {}

    for file in cpp_files:
        includes = extract_includes(file)
        graph[file] = includes

    return graph


def print_graph(graph):
    print("\n===== PROJECT DEPENDENCY GRAPH =====\n")

    for file, deps in graph.items():
        print(file)
        for d in deps:
            print("   ├──", d)


if __name__ == "__main__":
    from project_scanner import scan_project

    path = input("Project path: ")

    data = scan_project(path)

    graph = build_project_graph(data["cpp_files"])

    print_graph(graph)