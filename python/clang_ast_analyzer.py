import json
import os
import subprocess


def is_cpp_like_file(file_path):
    return file_path.lower().endswith((".cpp", ".cc", ".cxx", ".c", ".h", ".hpp"))


def run_clang_ast_dump(file_path):
    command = [
        r"C:\Program Files\LLVM\bin\clang++.exe",
        "-std=c++17",
        "-Xclang",
        "-ast-dump=json",
        "-fsyntax-only",
        file_path
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
    except Exception as e:
        return {
            "file": file_path,
            "success": False,
            "error": f"clang execution failed: {str(e)}",
            "classes": [],
            "functions": [],
            "fields": [],
            "classes_count": 0,
            "functions_count": 0,
            "fields_count": 0,
            "raw_pointer_fields_count": 0
        }

    if result.returncode != 0:
        return {
            "file": file_path,
            "success": False,
            "error": result.stderr[:3000],
            "classes": [],
            "functions": [],
            "fields": [],
            "classes_count": 0,
            "functions_count": 0,
            "fields_count": 0,
            "raw_pointer_fields_count": 0
        }

    try:
        ast_json = json.loads(result.stdout)
    except Exception as e:
        return {
            "file": file_path,
            "success": False,
            "error": str(e),
            "classes": [],
            "functions": [],
            "fields": [],
            "classes_count": 0,
            "functions_count": 0,
            "fields_count": 0,
            "raw_pointer_fields_count": 0
        }

    return parse_ast_json(file_path, ast_json)


def parse_ast_json(file_path, node):
    classes = []
    functions = []
    fields = []

    def walk(current):
        if not isinstance(current, dict):
            return

        kind = current.get("kind", "")
        name = current.get("name", "")

        if kind in {"CXXRecordDecl", "ClassTemplateDecl"} and name:
            classes.append({
                "name": name,
                "kind": kind,
                "location": current.get("loc", {})
            })

        if kind in {"FunctionDecl", "CXXMethodDecl", "CXXConstructorDecl", "CXXDestructorDecl"} and name:
            functions.append({
                "name": name,
                "kind": kind,
                "location": current.get("loc", {})
            })

        if kind == "FieldDecl" and name:
            field_type = current.get("type", {}).get("qualType", "")

            fields.append({
                "name": name,
                "type": field_type,
                "location": current.get("loc", {}),
                "is_raw_pointer": "*" in field_type
            })

        for child in current.get("inner", []):
            walk(child)

    walk(node)

    return {
        "file": file_path,
        "success": True,
        "error": "",
        "classes": classes,
        "functions": functions,
        "fields": fields,
        "classes_count": len(classes),
        "functions_count": len(functions),
        "fields_count": len(fields),
        "raw_pointer_fields_count": len([
            field for field in fields
            if field.get("is_raw_pointer")
        ])
    }


def build_clang_ast_report(files):
    report = {}

    for file_path in files:
        if not is_cpp_like_file(file_path):
            continue

        report[file_path] = run_clang_ast_dump(file_path)

    return report