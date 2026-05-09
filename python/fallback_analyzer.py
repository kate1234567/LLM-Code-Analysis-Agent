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

def analyze_cpp_lifecycle_risks(file_path, file_code):
    findings = []
    lines = file_code.splitlines()
    text = file_code.lower()

    has_new = re.search(r"\bnew\s+", text) is not None
    has_delete = re.search(r"\bdelete\b", text) is not None

    has_malloc = re.search(r"\bmalloc\s*\(", text) is not None
    has_free = re.search(r"\bfree\s*\(", text) is not None

    if has_new and not has_delete:
        line_number = find_first_matching_line(lines, r"\bnew\s+")
        findings.append(make_lightweight_bug(
            "memory-leak-new-without-delete",
            "high",
            "The file allocates memory with new, but no matching delete is visible in the same file.",
            "Use std::unique_ptr/std::shared_ptr or add deterministic cleanup.",
            line_number
        ))

    if has_malloc and not has_free:
        line_number = find_first_matching_line(lines, r"\bmalloc\s*\(")
        findings.append(make_lightweight_bug(
            "memory-leak-malloc-without-free",
            "high",
            "The file allocates memory with malloc, but no matching free is visible in the same file.",
            "Use RAII wrappers or ensure free() is called on all execution paths.",
            line_number
        ))

    for i, line in enumerate(lines, 1):
        l = line.lower()

        if "->" in l and ("nullptr" in l or "null" in l):
            findings.append(make_lightweight_bug(
                "possible-null-dereference",
                "high",
                "Pointer may be dereferenced after null/nullptr usage.",
                "Check pointer validity before dereference.",
                i
            ))

        if "return" in l and "*" in l and ("new " in l or "malloc(" in l):
            findings.append(make_lightweight_bug(
                "ownership-transfer-risk",
                "high",
                "Function returns manually allocated memory, making ownership unclear for the caller.",
                "Return RAII-managed objects such as std::unique_ptr or value types.",
                i
            ))

    return findings

def run_fallback_analysis(
    file_path,
    file_code,
    diff_text,
    paired_header_code="",
    related_cpp_code=""
):
    bugs = []

    lightweight_findings = detect_lightweight_findings(
        file_path,
        file_code
    )

    for bug in lightweight_findings:
        bugs.append(bug)

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
            "pattern": r"(password|passwd|token|secret|api[_-]?key)\s*=\s*[\"'][^\"']+[\"']",
            "bug": "hardcoded-credentials",
            "cause": "Credentials appear directly in code as hardcoded string literals.",
            "fix": "Move credentials to environment variables or protected configuration.",
            "severity": "high"
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
        },
        {
            "pattern": r"\bnew\s+",
            "bug": "possible-memory-leak",
            "cause": "Dynamic allocation detected without guaranteed ownership-safe cleanup, which may lead to memory leaks.",
            "fix": "Use std::unique_ptr, std::shared_ptr, RAII wrappers, or ensure deterministic delete logic.",
            "severity": "high"
        },
        {
            "pattern": r"\bmalloc\s*\(",
            "bug": "possible-memory-leak",
            "cause": "Manual heap allocation via malloc may lead to memory leaks if release is not guaranteed.",
            "fix": "Prefer RAII abstractions or ensure matching free() on all execution paths.",
            "severity": "high"
        },
        {
            "pattern": r"nullptr.*->|NULL.*->",
            "bug": "possible-null-dereference",
            "cause": "Pointer dereference after nullptr/NULL usage may cause runtime crashes.",
            "fix": "Validate pointer before dereference and avoid unsafe null access.",
            "severity": "high"
        },
        {
            "pattern": r"\bfopen\s*\(",
            "bug": "missing-raii-resource-management",
            "cause": "Manual FILE* resource management may cause leaks if fclose is missed.",
            "fix": "Prefer std::ifstream/std::ofstream or RAII wrappers.",
            "severity": "medium"
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
        bugs.append({
            "bug": "missing-destructor-for-owned-resource",
            "cause": "Class owns raw pointer fields but does not declare a destructor, which may indicate broken ownership lifecycle management.",
            "fix": "Declare destructor or replace raw ownership with RAII-safe abstractions such as std::string or std::unique_ptr.",
            "severity": "high",
            "line_start": find_first_matching_line(
                lines,
                r"\bchar\s*\*\s*[A-Za-z_]\w*\s*;"
            ),
            "line_end": find_first_matching_line(
                lines,
                r"\bchar\s*\*\s*[A-Za-z_]\w*\s*;"
            ),
            "finding_scope": "interfile"
        })

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

def make_lightweight_bug(
    bug,
    severity,
    cause,
    fix,
    line_number
):
    return {
        "bug": bug,
        "severity": severity,
        "cause": cause,
        "fix": fix,
        "line_start": line_number,
        "line_end": line_number,
        "finding_scope": "local"
    }


def analyze_python(code):
    findings = []
    lines = code.splitlines()

    for i, line in enumerate(lines, 1):
        l = line.lower()

        if "eval(" in l or "exec(" in l:
            findings.append(make_lightweight_bug(
                "unsafe-dynamic-execution",
                "high",
                "Dynamic code execution may lead to security risks.",
                "Avoid eval()/exec() where possible.",
                i
            ))

        if "subprocess" in l and "shell=true" in l:
            findings.append(make_lightweight_bug(
                "unsafe-command-execution",
                "high",
                "Shell execution may allow command injection.",
                "Avoid shell=True and validate commands.",
                i
            ))

        if "password =" in l or "token =" in l or "api_key =" in l:
            findings.append(make_lightweight_bug(
                "hardcoded-credentials",
                "high",
                "Credentials appear directly in code.",
                "Move secrets to environment variables.",
                i
            ))

        if "except:" in l:
            findings.append(make_lightweight_bug(
                "broad-exception-handling",
                "medium",
                "Bare except may hide critical errors.",
                "Catch specific exceptions instead of using bare except.",
                i
            ))

        if "pickle.loads(" in l or "pickle.load(" in l:
            findings.append(make_lightweight_bug(
                "unsafe-deserialization",
                "high",
                "pickle deserialization may execute arbitrary code.",
                "Avoid untrusted pickle deserialization.",
                i
            ))

        if "requests.get(" in l and "timeout=" not in l:
            findings.append(make_lightweight_bug(
                "missing-timeout",
                "medium",
                "HTTP request without timeout may hang indefinitely.",
                "Specify timeout= in requests calls.",
                i
            ))

        if "subprocess.run(" in l and "shell=true" in l:
            findings.append(make_lightweight_bug(
                "unsafe-subprocess-shell",
                "high",
                "shell=True may allow command injection.",
                "Avoid shell=True and validate input.",
                i
            ))

        if "cursor.execute(" in l and "%" in l:
            findings.append(make_lightweight_bug(
                "possible-sql-injection",
                "high",
                "String-formatted SQL may lead to injection.",
                "Use parameterized SQL queries.",
                i
            ))

    return findings


def analyze_java(code):
    findings = []
    lines = code.splitlines()

    for i, line in enumerate(lines, 1):
        l = line.lower()

        if "runtime.getruntime().exec(" in l:
            findings.append(make_lightweight_bug(
                "unsafe-command-execution",
                "high",
                "Runtime.exec may execute unsafe commands.",
                "Avoid raw Runtime.exec() calls.",
                i
            ))

        if "password =" in l or "token =" in l or "secret" in l:
            findings.append(make_lightweight_bug(
                "hardcoded-credentials",
                "high",
                "Credentials appear directly in code.",
                "Use secure configuration storage.",
                i
            ))

    return findings


def analyze_javascript(code):
    findings = []
    lines = code.splitlines()

    for i, line in enumerate(lines, 1):
        l = line.lower()

        if "eval(" in l:
            findings.append(make_lightweight_bug(
                "unsafe-dynamic-execution",
                "high",
                "eval() may execute unsafe code.",
                "Avoid eval() usage.",
                i
            ))

        if "innerhtml" in l:
            findings.append(make_lightweight_bug(
                "unsafe-dom-manipulation",
                "medium",
                "innerHTML may introduce XSS risks.",
                "Prefer safer DOM APIs.",
                i
            ))

        if "password =" in l or "token =" in l:
            findings.append(make_lightweight_bug(
                "hardcoded-credentials",
                "high",
                "Credentials appear directly in code.",
                "Move secrets outside source code.",
                i
            ))

        if "child_process.exec(" in l:
            findings.append(make_lightweight_bug(
                "unsafe-command-execution",
                "high",
                "child_process.exec may execute unsafe commands.",
                "Avoid raw command execution.",
                i
            ))

        if "localstorage.setitem(" in l and "token" in l:
            findings.append(make_lightweight_bug(
                "token-storage-risk",
                "medium",
                "Sensitive token stored in localStorage may be stolen via XSS.",
                "Prefer HttpOnly cookies or safer storage.",
                i
            ))

        if "md5" in l:
            findings.append(make_lightweight_bug(
                "weak-crypto",
                "medium",
                "MD5 is considered cryptographically weak.",
                "Use stronger hashing like SHA-256 or bcrypt.",
                i
            ))

    return findings

def analyze_cross_file_risk(file_path, file_code):
    findings = []
    lines = file_code.splitlines()
    ext = os.path.splitext(file_path)[1].lower()

    imported_modules = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if ext == ".py":
            m1 = re.match(r"import\s+([A-Za-z_][\w\.]*)", stripped)
            m2 = re.match(r"from\s+([A-Za-z_][\w\.]*)\s+import", stripped)

            if m1:
                imported_modules.append((m1.group(1), i))

            if m2:
                imported_modules.append((m2.group(1), i))

        elif ext in [".js", ".ts"]:
            m1 = re.search(r"from\s+[\"']([^\"']+)[\"']", stripped)
            m2 = re.search(r"require\s*\(\s*[\"']([^\"']+)[\"']\s*\)", stripped)

            if m1:
                imported_modules.append((m1.group(1), i))

            if m2:
                imported_modules.append((m2.group(1), i))

    dangerous_modules = {
        "subprocess",
        "os",
        "sys",
        "pickle",
        "child_process",
        "fs",
        "crypto"
    }

    for module_name, line_number in imported_modules:
        short_name = module_name.split(".")[-1].replace("./", "").replace("../", "")

        if short_name in dangerous_modules:
            findings.append(make_lightweight_bug(
                "dangerous-dependency-import",
                "medium",
                f"Import of risky dependency detected: {module_name}",
                "Validate usage of this dependency and restrict dangerous operations.",
                line_number
            ))

            findings[-1]["finding_scope"] = "interfile"

    return findings

def detect_lightweight_findings(
    file_path,
    file_code,
    imported_modules_context=None
):
    ext = os.path.splitext(file_path)[1].lower()

    findings = []

    if ext == ".py":
        findings.extend(analyze_python(file_code))

    elif ext == ".java":
        findings.extend(analyze_java(file_code))

    elif ext in [".js", ".ts"]:
        findings.extend(analyze_javascript(file_code))

    findings.extend(
        analyze_cross_file_risk(
            file_path,
            file_code
        )
    )

    if imported_modules_context is None:
        imported_modules_context = []

    for imported in imported_modules_context:
        imported_code = imported.get("code", "").lower()
        imported_path = imported.get("path", "")

        dangerous_markers = [
            "secret_key",
            "api_key",
            "password",
            "token",
            "debug = true",
            "debug=true"
        ]

        for marker in dangerous_markers:
            if marker in imported_code:
                findings.append({
                    "bug": "shared-sensitive-config-across-files",
                    "severity": "high",
                    "cause": (
                        f"Imported module contains sensitive configuration "
                        f"or insecure debug setting: {marker}"
                    ),
                    "fix": (
                        "Move secrets to protected configuration "
                        "and disable debug mode in production."
                    ),
                    "line_start": 1,
                    "line_end": 1,
                    "finding_scope": "interfile"
                })
                break

    if ext in [".cpp", ".cc", ".cxx", ".c", ".h", ".hpp"]:
        findings.extend(
            analyze_cpp_lifecycle_risks(
                file_path,
                file_code
            )
        )

    return findings