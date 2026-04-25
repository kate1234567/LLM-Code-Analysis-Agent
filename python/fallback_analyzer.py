import re
import os


def parse_changed_lines(diff_text):
    changed_lines = set()

    if not diff_text:
        return changed_lines

    hunk_regex = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    current_new_line = None

    for line in diff_text.splitlines():
        hunk_match = hunk_regex.match(line)
        if hunk_match:
            start = int(hunk_match.group(1))
            current_new_line = start
            continue

        if current_new_line is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            changed_lines.add(current_new_line)
            current_new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        else:
            current_new_line += 1

    return changed_lines


def line_is_relevant(line_number, changed_lines):
    if line_number is None:
        return False
    if not changed_lines:
        return True
    return line_number in changed_lines


def is_header_file(file_path):
    path = file_path.lower()
    return path.endswith(".h") or path.endswith(".hpp")


def has_pattern(text, pattern):
    if not text:
        return False
    return re.search(pattern, text) is not None


def find_first_matching_line(lines, pattern):
    for idx, line in enumerate(lines, start=1):
        if re.search(pattern, line):
            return idx
    return None


def run_fallback_analysis(
    file_path,
    file_code,
    diff_text,
    paired_header_code="",
    related_cpp_code=""
):
    bugs = []
    changed_lines = parse_changed_lines(diff_text)
    seen = set()

    lines = file_code.splitlines()
    header_mode = is_header_file(file_path)

    common_checks = [
        {
            "pattern": r"_popen\s*\(",
            "bug": "unsafe-command-execution",
            "cause": "Use of _popen may allow unsafe command execution or command injection.",
            "fix": "Avoid raw shell execution when possible. Validate inputs and prefer safer process APIs.",
            "severity": "high"
        },
        {
            "pattern": r"\bsystem\s*\(",
            "bug": "unsafe-command-execution",
            "cause": "Use of system may allow unsafe command execution or command injection.",
            "fix": "Avoid raw shell execution when possible. Validate inputs and prefer safer process APIs.",
            "severity": "high"
        },
        {
            "pattern": r"password\s*=",
            "bug": "hardcoded-credentials",
            "cause": "Credentials appear directly in code or command strings.",
            "fix": "Move credentials to environment variables or protected configuration.",
            "severity": "high"
        },
        {
            "pattern": r"git\s+-C",
            "bug": "external-tool-dependency",
            "cause": "Code depends on external command-line tools without explicit availability checks.",
            "fix": "Check tool availability before execution and handle missing tools gracefully.",
            "severity": "medium"
        },
        {
            "pattern": r"\bpy\s+",
            "bug": "external-tool-dependency",
            "cause": "Code depends on external command-line tools without explicit availability checks.",
            "fix": "Check tool availability before execution and handle missing tools gracefully.",
            "severity": "medium"
        },
        {
            "pattern": r"catch\s*\(\s*const\s+std::exception\s*&",
            "bug": "weak-error-propagation",
            "cause": "Errors may be logged but not propagated to caller as failure status.",
            "fix": "Return a non-zero exit code or propagate failure state.",
            "severity": "medium"
        },
        {
            "pattern": r"\bnew\s+",
            "bug": "manual-memory-management",
            "cause": "Manual dynamic allocation may lead to leaks or ownership errors.",
            "fix": "Prefer smart pointers, RAII wrappers, or standard containers.",
            "severity": "medium"
        },
        {
            "pattern": r"\bdelete\s*\[\s*\]|\bdelete\b",
            "bug": "manual-memory-management",
            "cause": "Manual deallocation may indicate fragile ownership handling.",
            "fix": "Prefer smart pointers or standard containers where possible.",
            "severity": "medium"
        },
        {
            "pattern": r"\bmalloc\s*\(",
            "bug": "manual-memory-management",
            "cause": "malloc in C++ code may lead to unsafe memory management patterns.",
            "fix": "Prefer standard containers, RAII, or smart pointers.",
            "severity": "medium"
        },
        {
            "pattern": r"\bfree\s*\(",
            "bug": "manual-memory-management",
            "cause": "free in C++ code may indicate fragile memory lifecycle control.",
            "fix": "Prefer RAII and safer abstractions.",
            "severity": "medium"
        },
        {
            "pattern": r"\bstrcpy\s*\(",
            "bug": "unsafe-string-copy",
            "cause": "strcpy may overflow the destination buffer.",
            "fix": "Use bounded alternatives or std::string.",
            "severity": "high"
        },
        {
            "pattern": r"\bstrcat\s*\(",
            "bug": "unsafe-string-concatenation",
            "cause": "strcat may overflow the destination buffer.",
            "fix": "Use bounded alternatives or std::string.",
            "severity": "high"
        },
        {
            "pattern": r"\bgets\s*\(",
            "bug": "unsafe-input",
            "cause": "gets is unsafe and may cause buffer overflow.",
            "fix": "Use safer input functions.",
            "severity": "high"
        }
    ]

    header_checks = [
        {
            "pattern": r"\bchar\s*\*\s*[A-Za-z_]\w*\s*;",
            "bug": "raw-pointer-field-in-interface",
            "cause": "Header declares a raw pointer field, which may lead to ownership and lifetime issues.",
            "fix": "Prefer std::string, std::vector, smart pointers, or explicit ownership documentation.",
            "severity": "medium"
        },
        {
            "pattern": r"\bchar\s*\*\s+[A-Za-z_]\w*\s*\(",
            "bug": "unsafe-pointer-return-interface",
            "cause": "Header exposes an interface returning raw char pointers, which may lead to unsafe ownership handling.",
            "fix": "Prefer std::string, std::vector<char>, or smart pointer based interfaces.",
            "severity": "medium"
        }
    ]

    checks = list(common_checks)
    if header_mode:
        checks.extend(header_checks)

    for line_number, line in enumerate(lines, start=1):
        if not line_is_relevant(line_number, changed_lines):
            continue

        for check in checks:
            if re.search(check["pattern"], line):
                key = (check["bug"], line_number)
                if key in seen:
                    continue
                seen.add(key)

                bugs.append({
                    "bug": check["bug"],
                    "cause": check["cause"],
                    "fix": check["fix"],
                    "severity": check["severity"],
                    "line_start": line_number,
                    "line_end": line_number,
                    "finding_scope": "local"
                })

    # эвристика для header: raw pointer field + no destructor declaration
    if header_mode:
        has_raw_pointer_field = any(
            re.search(r"\bchar\s*\*\s*[A-Za-z_]\w*\s*;", line)
            for line in lines
        )
        has_destructor_decl = any(
            re.search(r"~[A-Za-z_]\w*\s*\(", line)
            for line in lines
        )

        if has_raw_pointer_field and not has_destructor_decl:
            key = ("missing-destructor-for-raw-pointer-field", None)
            if key not in seen:
                seen.add(key)
                bugs.append({
                    "bug": "missing-destructor-for-raw-pointer-field",
                    "cause": "Header declares a raw pointer field but does not declare a destructor, which may indicate unsafe ownership handling.",
                    "fix": "Declare and implement proper cleanup logic or replace the raw pointer with safer abstractions.",
                    "severity": "medium",
                    "line_start": None,
                    "line_end": None,
                    "finding_scope": "local"
                })

    # МЕЖФАЙЛОВАЯ ЭВРИСТИКА 1:
    # header exposes raw pointer + related cpp uses manual allocation
    if header_mode:
        header_has_raw_pointer = has_pattern(file_code, r"\bchar\s*\*\s*[A-Za-z_]\w*\s*;")
        header_returns_raw_pointer = has_pattern(file_code, r"\bchar\s*\*\s+[A-Za-z_]\w*\s*\(")
        cpp_uses_manual_alloc = (
            has_pattern(related_cpp_code, r"\bmalloc\s*\(")
            or has_pattern(related_cpp_code, r"\bnew\s+")
        )
        cpp_has_release = (
            has_pattern(related_cpp_code, r"\bfree\s*\(")
            or has_pattern(related_cpp_code, r"\bdelete\b")
        )

        if (header_has_raw_pointer or header_returns_raw_pointer) and cpp_uses_manual_alloc and not cpp_has_release:
            key = ("raw-pointer-interface-without-release", None)
            if key not in seen:
                seen.add(key)

                header_line = find_first_matching_line(
                    lines,
                    r"\bchar\s*\*\s*[A-Za-z_]\w*\s*;|\bchar\s*\*\s+[A-Za-z_]\w*\s*\("
                )

                bugs.append({
                    "bug": "raw-pointer-interface-without-release",
                    "cause": "Header exposes raw pointer ownership semantics, related implementation performs manual allocation, but no matching release operation is visible.",
                    "fix": "Add explicit safe cleanup logic or replace the interface and implementation with RAII-based ownership.",
                    "severity": "high",
                    "line_start": header_line,
                    "line_end": header_line,
                    "finding_scope": "interfile"
                })

        elif (header_has_raw_pointer or header_returns_raw_pointer) and cpp_uses_manual_alloc:
            key = ("raw-pointer-interface-with-manual-allocation", None)
            if key not in seen:
                seen.add(key)

                header_line = find_first_matching_line(
                    lines,
                    r"\bchar\s*\*\s*[A-Za-z_]\w*\s*;|\bchar\s*\*\s+[A-Za-z_]\w*\s*\("
                )

                bugs.append({
                    "bug": "raw-pointer-interface-with-manual-allocation",
                    "cause": "Header exposes raw pointer ownership semantics while the related implementation uses manual allocation, increasing the risk of leaks and unsafe ownership transfer.",
                    "fix": "Replace raw pointer based ownership with RAII-friendly abstractions such as std::string, std::vector, std::unique_ptr, or clearly defined ownership-safe interfaces.",
                    "severity": "high",
                    "line_start": header_line,
                    "line_end": header_line,
                    "finding_scope": "interfile"
                })

    # МЕЖФАЙЛОВАЯ ЭВРИСТИКА 2:
    # cpp uses manual allocation + paired header exposes raw pointer interface
    if not header_mode:
        cpp_uses_manual_alloc = (
            has_pattern(file_code, r"\bmalloc\s*\(")
            or has_pattern(file_code, r"\bnew\s+")
        )
        header_has_raw_pointer = (
            has_pattern(paired_header_code, r"\bchar\s*\*\s*[A-Za-z_]\w*\s*;")
            or has_pattern(paired_header_code, r"\bchar\s*\*\s+[A-Za-z_]\w*\s*\(")
        )
        cpp_has_release = (
            has_pattern(file_code, r"\bfree\s*\(")
            or has_pattern(file_code, r"\bdelete\b")
        )

        if cpp_uses_manual_alloc and header_has_raw_pointer and not cpp_has_release:
            key = ("manual-allocation-without-visible-release", None)
            if key not in seen:
                seen.add(key)

                cpp_line = find_first_matching_line(
                    lines,
                    r"\bmalloc\s*\(|\bnew\s+"
                )

                bugs.append({
                    "bug": "manual-allocation-without-visible-release",
                    "cause": "Implementation performs manual allocation for an interface exposing raw pointers, but no matching release operation is visible in the implementation.",
                    "fix": "Add explicit cleanup logic or replace manual ownership with RAII-based abstractions.",
                    "severity": "high",
                    "line_start": cpp_line,
                    "line_end": cpp_line,
                    "finding_scope": "interfile"
                })

        elif cpp_uses_manual_alloc and header_has_raw_pointer:
            key = ("manual-allocation-behind-raw-pointer-interface", None)
            if key not in seen:
                seen.add(key)

                cpp_line = find_first_matching_line(
                    lines,
                    r"\bmalloc\s*\(|\bnew\s+"
                )

                bugs.append({
                    "bug": "manual-allocation-behind-raw-pointer-interface",
                    "cause": "Implementation performs manual allocation while the paired header exposes raw pointer based interface semantics, which may indicate fragile ownership design.",
                    "fix": "Use RAII-based storage and safer return types, or redesign the interface to avoid exposing raw pointer ownership.",
                    "severity": "high",
                    "line_start": cpp_line,
                    "line_end": cpp_line,
                    "finding_scope": "interfile"
                })

    return {
        "file": file_path,
        "bugs": bugs
    }