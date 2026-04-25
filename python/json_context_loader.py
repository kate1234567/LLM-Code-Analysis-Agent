import json
import os


def is_cpp_file(path):
    return path.lower().endswith(".cpp")


def is_header_file(path):
    p = path.lower()
    return p.endswith(".h") or p.endswith(".hpp")


def file_stem(path):
    return os.path.splitext(os.path.basename(path))[0].lower()


def load_context_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    files = data.get("files", [])
    context_map = {}

    header_by_stem = {}
    cpp_by_stem = {}

    for file_entry in files:
        path = file_entry.get("path", "")
        stem = file_stem(path)

        if is_header_file(path):
            header_by_stem[stem] = file_entry
        elif is_cpp_file(path):
            cpp_by_stem[stem] = file_entry

    for file_entry in files:
        file_path = file_entry.get("path", "")
        stem = file_stem(file_path)

        paired_header = None
        related_cpp = None

        if is_cpp_file(file_path):
            paired_header = header_by_stem.get(stem)

        if is_header_file(file_path):
            related_cpp = cpp_by_stem.get(stem)

        context_map[file_path] = {
            "file": file_path,
            "relative_path": file_entry.get("relative_path", ""),
            "file_code": file_entry.get("file_code", ""),
            "diff": file_entry.get("diff", ""),
            "symbols": file_entry.get("symbols", {
                "classes": [],
                "structs": [],
                "functions": []
            }),
            "dependencies": [
                {
                    "dependency": dep,
                    "path": None,
                    "code": "",
                    "symbols": {
                        "classes": [],
                        "structs": [],
                        "functions": []
                    }
                }
                for dep in file_entry.get("includes", [])
            ],
            "paired_header": {
                "path": paired_header.get("path") if paired_header else None,
                "code": paired_header.get("file_code", "") if paired_header else "",
                "symbols": paired_header.get("symbols", {
                    "classes": [],
                    "structs": [],
                    "functions": []
                }) if paired_header else {
                    "classes": [],
                    "structs": [],
                    "functions": []
                }
            },
            "related_cpp": {
                "path": related_cpp.get("path") if related_cpp else None,
                "code": related_cpp.get("file_code", "") if related_cpp else "",
                "symbols": related_cpp.get("symbols", {
                    "classes": [],
                    "structs": [],
                    "functions": []
                }) if related_cpp else {
                    "classes": [],
                    "structs": [],
                    "functions": []
                }
            }
        }

    return context_map