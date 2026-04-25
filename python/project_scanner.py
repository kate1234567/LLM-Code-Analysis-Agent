import os

IGNORE_DIRS = {".vs", "x64", "Debug", "Release", "build"}
IGNORE_EXT = {".exe", ".dll", ".obj", ".pdb", ".ilk", ".log", ".db"}

def scan_project(path):
    result = {
        "files": [],
        "cpp_files": [],
        "header_files": []
    }

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for f in files:
            ext = os.path.splitext(f)[1]

            if ext in IGNORE_EXT:
                continue

            full = os.path.join(root, f)
            result["files"].append(full)

            if f.endswith(".cpp"):
                result["cpp_files"].append(full)

            if f.endswith(".h"):
                result["header_files"].append(full)

    return result


if __name__ == "__main__":
    path = input("Project path: ")
    data = scan_project(path)

    print("\n=== CPP FILES ===")
    for f in data["cpp_files"]:
        print(f)

    print("\n=== HEADER FILES ===")
    for f in data["header_files"]:
        print(f)