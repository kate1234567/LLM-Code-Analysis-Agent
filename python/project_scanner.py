import os

IGNORE_DIRS = {".vs", "x64", "Debug", "Release", "build", ".git", "__pycache__", "node_modules", "bin", "obj"}
IGNORE_EXT = {".exe", ".dll", ".obj", ".pdb", ".ilk", ".log", ".db"}

SUPPORTED_EXTENSIONS = {
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".go": "go",
}


def detect_language(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    return SUPPORTED_EXTENSIONS.get(ext, "unknown")


def scan_project(path):
    result = {
        "files": [],
        "code_files": [],
        "cpp_files": [],
        "header_files": [],
        "files_by_language": {}
    }

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for f in files:
            ext = os.path.splitext(f)[1].lower()

            if ext in IGNORE_EXT:
                continue

            full = os.path.join(root, f)
            result["files"].append(full)

            language = detect_language(full)

            if language != "unknown":
                result["code_files"].append(full)

                if language not in result["files_by_language"]:
                    result["files_by_language"][language] = []

                result["files_by_language"][language].append(full)

            if ext in {".cpp", ".cc", ".cxx", ".c"}:
                result["cpp_files"].append(full)

            if ext in {".h", ".hpp"}:
                result["header_files"].append(full)

    return result


if __name__ == "__main__":
    path = input("Project path: ")
    data = scan_project(path)

    print("\n=== CODE FILES ===")
    for f in data["code_files"]:
        print(f, "| language:", detect_language(f))

    print("\n=== FILES BY LANGUAGE ===")
    for language, files in data["files_by_language"].items():
        print(language, ":", len(files))