import json
import os
import re
from typing import Any, Dict, List, Optional

from fallback_analyzer import run_fallback_analysis
from llm_client import create_llm_client


for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)

os.environ["NO_PROXY"] = "localhost,127.0.0.1"


llm_client = create_llm_client(
    provider=os.getenv("LLM_PROVIDER", "ollama"),
    model=os.getenv("LLM_MODEL", "deepseek-coder")
)

ALLOWED_BUG_NAMES = {
    "unsafe-command-execution",
    "hardcoded-credentials",
    "unsafe-string-copy",
    "raw-pointer-field-in-interface",
    "raw-pointer-interface-without-release",
    "unsafe-pointer-return-interface",
    "weak-error-propagation",
    "external-tool-dependency",
    "manual-memory-management",
    "manual-allocation-without-visible-release",
    "unsafe-dynamic-execution",
    "unsafe-dom-manipulation",
    "unsafe-string-concatenation",
    "unsafe-input",
    "missing-destructor-for-raw-pointer-field",
    "raw-pointer-interface-with-manual-allocation",
    "manual-allocation-behind-raw-pointer-interface",
}

SCOPE_RANK = {
    "local": 1,
    "interfile": 2,
}

SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def shorten_list(items: Optional[List[Any]], max_items: int = 5) -> List[Any]:
    if not items:
        return []
    return items[:max_items]


def shorten_text(text: Optional[str], max_chars: int) -> str:
    if not text:
        return ""
    return text[:max_chars]


def normalize_bug_name(name: Optional[str]) -> str:
    if not name:
        return ""

    value = str(name).strip().lower().rstrip(".,:; ")

    replacements = {
        "unsafe command execution": "unsafe-command-execution",
        "hardcoded credentials": "hardcoded-credentials",
        "unsafe string copy": "unsafe-string-copy",
        "raw pointer field in interface": "raw-pointer-field-in-interface",
        "raw pointer interface without release": "raw-pointer-interface-without-release",
        "unsafe pointer return interface": "unsafe-pointer-return-interface",
        "weak error propagation": "weak-error-propagation",
        "external tool dependency": "external-tool-dependency",
        "manual memory management": "manual-memory-management",
        "manual allocation without visible release": "manual-allocation-without-visible-release",
    }

    return replacements.get(value, value)


def normalize_scope(value: Optional[str]) -> str:
    scope = str(value or "local").strip().lower()
    if scope not in {"local", "interfile"}:
        return "local"
    return scope


def normalize_severity(value: Optional[str]) -> str:
    sev = str(value or "").strip().lower()
    if sev not in {"low", "medium", "high"}:
        return "medium"
    return sev


def looks_like_refusal_or_garbage(text: Optional[str]) -> bool:
    if not text:
        return True

    lowered = text.lower()

    bad_phrases = [
        "i'm sorry",
        "i am sorry",
        "i can only provide assistance",
        "i don't have access",
        "i do not have access",
        "without full context",
        "review is not possible",
        "cannot review",
        "can't review",
        "not possible without",
        "here are some of them",
        "based on my understanding",
        "the provided code seems to be",
        "not in my area",
        "however, based on my understanding",
        "candidate bug type",
        "not used correctly",
        "not correctly configured",
        "deprecated",
    ]

    return any(phrase in lowered for phrase in bad_phrases)


def extract_changed_lines(diff_text: Optional[str]) -> set:
    changed_lines = set()

    if not diff_text:
        return changed_lines

    current_new_line = None

    for line in diff_text.splitlines():
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                current_new_line = int(m.group(1))
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


def is_valid_line_range(file_code: str, line_start: Any, line_end: Any) -> bool:
    try:
        line_start = int(line_start)
        line_end = int(line_end)
    except Exception:
        return False

    lines_count = len(file_code.splitlines())
    if lines_count <= 0:
        return False

    if line_start < 1 or line_end < 1:
        return False

    if line_start > lines_count or line_end > lines_count:
        return False

    if line_start > line_end:
        return False

    return True


def get_code_fragment(file_code: str, line_start: int, line_end: int) -> str:
    if not is_valid_line_range(file_code, line_start, line_end):
        return ""
    lines = file_code.splitlines()
    return "\n".join(lines[line_start - 1:line_end])


def bug_supported_by_code(bug_name: str, file_code: str, line_start: int, line_end: int) -> bool:
    if not is_valid_line_range(file_code, line_start, line_end):
        return False

    fragment = get_code_fragment(file_code, line_start, line_end).lower()
    whole_code = file_code.lower()

    if bug_name == "unsafe-command-execution":
        markers = ["system(", "_popen(", "popen(", "cmd /c", "shell"]
        return any(m in fragment for m in markers)

    if bug_name == "hardcoded-credentials":
        markers = ["password", "passwd", "token", "secret", "apikey", "api_key"]
        return any(m in fragment for m in markers)

    if bug_name == "unsafe-string-copy":
        markers = ["strcpy(", "strcat(", "sprintf(", "gets("]
        return any(m in fragment for m in markers)

    if bug_name == "raw-pointer-field-in-interface":
        return "*" in fragment and ("class " in whole_code or "struct " in whole_code)

    if bug_name == "unsafe-pointer-return-interface":
        return "*" in fragment and "(" in fragment and ")" in fragment

    if bug_name == "raw-pointer-interface-without-release":
        has_alloc = any(x in whole_code for x in ["malloc(", "new ", "new[]"])
        has_free = any(x in whole_code for x in ["free(", "delete ", "delete[]"])
        return has_alloc and not has_free

    if bug_name == "manual-memory-management":
        markers = ["malloc(", "free(", "new ", "delete ", "new[]", "delete[]"]
        return any(x in fragment for x in markers)

    if bug_name == "manual-allocation-without-visible-release":
        has_alloc = any(x in whole_code for x in ["malloc(", "new ", "new[]"])
        has_free = any(x in whole_code for x in ["free(", "delete ", "delete[]"])
        return has_alloc and not has_free

    if bug_name == "external-tool-dependency":
        markers = ["_popen(", "system(", ".exe", "git ", "clang ", "python "]
        return any(m in fragment for m in markers)

    if bug_name == "weak-error-propagation":
        markers = ["return false", "return 0", "cerr", "cout"]
        return any(m in fragment for m in markers)

    return False


def reason_matches_bug_type(bug_name: str, cause_text: str, fix_text: str) -> bool:
    text = ((cause_text or "") + " " + (fix_text or "")).lower()

    expected = {
        "unsafe-command-execution": ["command", "shell", "system", "_popen", "popen", "execution", "injection"],
        "hardcoded-credentials": ["password", "token", "secret", "credential", "api key", "apikey"],
        "unsafe-string-copy": ["strcpy", "strcat", "sprintf", "buffer", "overflow", "copy"],
        "raw-pointer-field-in-interface": ["pointer", "ownership", "lifetime", "raw pointer"],
        "unsafe-pointer-return-interface": ["pointer", "return", "ownership", "raw pointer"],
        "raw-pointer-interface-without-release": ["pointer", "ownership", "release", "cleanup", "delete", "free"],
        "weak-error-propagation": ["error", "return", "propagate", "failure", "status"],
        "external-tool-dependency": ["tool", "external", "dependency", "availability", "command"],
        "manual-memory-management": ["memory", "malloc", "free", "new", "delete", "manual"],
        "manual-allocation-without-visible-release": ["allocation", "release", "cleanup", "delete", "free", "ownership"],
    }

    words = expected.get(bug_name, [])
    if not words:
        return True

    return any(word in text for word in words)


def sanitize_fallback_bug(bug: Dict[str, Any], file_code: str) -> Optional[Dict[str, Any]]:
    bug_name = normalize_bug_name(bug.get("bug", ""))
    if bug_name not in ALLOWED_BUG_NAMES:
        return None

    line_start = bug.get("line_start")
    line_end = bug.get("line_end")

    if not is_valid_line_range(file_code, line_start, line_end):
        return None

    sanitized = {
        "bug": bug_name,
        "cause": str(bug.get("cause", "") or "").strip(),
        "fix": str(bug.get("fix", "") or "").strip(),
        "severity": normalize_severity(bug.get("severity")),
        "line_start": int(line_start),
        "line_end": int(line_end),
        "finding_scope": normalize_scope(bug.get("finding_scope")),
    }

    return sanitized


def sanitize_fallback_result(file_path: str, file_code: str, fallback_result: Dict[str, Any]) -> Dict[str, Any]:
    bugs = fallback_result.get("bugs", []) or []
    clean_bugs = []

    for bug in bugs:
        clean_bug = sanitize_fallback_bug(bug, file_code)
        if clean_bug:
            clean_bugs.append(clean_bug)

    return {
        "file": file_path,
        "bugs": clean_bugs,
    }


def deduplicate_bugs(bugs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_key: Dict[Any, Dict[str, Any]] = {}

    for bug in bugs:
        key = (
            bug.get("bug"),
            bug.get("line_start"),
            bug.get("line_end"),
        )

        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = bug
            continue

        current_scope = SCOPE_RANK.get(current.get("finding_scope", "local"), 0)
        new_scope = SCOPE_RANK.get(bug.get("finding_scope", "local"), 0)

        if new_scope > current_scope:
            best_by_key[key] = bug
            continue

        if new_scope == current_scope:
            current_sev = SEVERITY_RANK.get(current.get("severity", "medium"), 0)
            new_sev = SEVERITY_RANK.get(bug.get("severity", "medium"), 0)
            if new_sev > current_sev:
                best_by_key[key] = bug

    return list(best_by_key.values())

def enrich_priority_scores(
    bugs: List[Dict[str, Any]],
    historical_findings: Optional[List[Dict[str, Any]]] = None,
    reverse_dependencies: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:

    history_count = len(historical_findings or [])
    reverse_count = len(reverse_dependencies or [])

    for bug in bugs:
        score = 0
        reasons = []

        severity = normalize_severity(
            bug.get("severity", "medium")
        )

        if severity == "high":
            score += 40
            reasons.append("high severity")
        elif severity == "medium":
            score += 20
            reasons.append("medium severity")
        else:
            score += 10
            reasons.append("low severity")

        scope = normalize_scope(
            bug.get("finding_scope", "local")
        )

        if scope == "interfile":
            score += 30
            reasons.append("interfile issue")
        else:
            score += 10
            reasons.append("local issue")

        if history_count > 0:
            score += min(history_count * 5, 20)
            reasons.append("historical issue")

        if reverse_count > 0:
            score += min(reverse_count * 5, 20)
            reasons.append("has reverse dependencies")

        bug["priority_score"] = score
        bug["priority_reason"] = reasons

    return bugs

def limit_candidate_bugs(candidate_bugs: List[Dict[str, Any]], max_bugs: int = 5) -> List[Dict[str, Any]]:
    def sort_key(bug: Dict[str, Any]):
        scope_rank = 1 if bug.get("finding_scope") == "interfile" else 0
        sev_rank = SEVERITY_RANK.get((bug.get("severity") or "medium").lower(), 2)
        return (-scope_rank, -sev_rank, bug.get("line_start", 999999))

    return sorted(candidate_bugs, key=sort_key)[:max_bugs]


def build_dependency_block(dependencies: Optional[List[Dict[str, Any]]]) -> str:
    if not dependencies:
        return "(no dependencies)"

    lines = []
    for dep in dependencies[:2]:
        dep_name = dep.get("dependency", "")
        dep_path = dep.get("path", "")
        dep_symbols = dep.get("symbols", {})
        dep_code = shorten_text(dep.get("code", ""), 500)

        lines.append(
            f"""DEPENDENCY: {dep_name}
PATH: {dep_path}
FUNCTIONS: {shorten_list(dep_symbols.get("functions", []))}
CLASSES: {shorten_list(dep_symbols.get("classes", []))}
STRUCTS: {shorten_list(dep_symbols.get("structs", []))}
CODE_SNIPPET:
{dep_code}
"""
        )

    return "\n".join(lines)


def build_header_block(paired_header: Optional[Dict[str, Any]]) -> str:
    if not paired_header:
        return "(no paired header)"

    header_path = paired_header.get("path")
    if not header_path:
        return "(no paired header)"

    header_symbols = paired_header.get("symbols", {})
    header_code = shorten_text(paired_header.get("code", ""), 700)

    return f"""PATH: {header_path}
FUNCTIONS: {shorten_list(header_symbols.get("functions", []))}
CLASSES: {shorten_list(header_symbols.get("classes", []))}
STRUCTS: {shorten_list(header_symbols.get("structs", []))}
CODE_SNIPPET:
{header_code}
"""


def build_related_cpp_block(related_cpp: Optional[Dict[str, Any]]) -> str:
    if not related_cpp:
        return "(no related cpp)"

    cpp_path = related_cpp.get("path")
    if not cpp_path:
        return "(no related cpp)"

    cpp_symbols = related_cpp.get("symbols", {})
    cpp_code = shorten_text(related_cpp.get("code", ""), 700)

    return f"""PATH: {cpp_path}
FUNCTIONS: {shorten_list(cpp_symbols.get("functions", []))}
CLASSES: {shorten_list(cpp_symbols.get("classes", []))}
STRUCTS: {shorten_list(cpp_symbols.get("structs", []))}
CODE_SNIPPET:
{cpp_code}
"""


def build_history_block(historical_findings: Optional[List[Dict[str, Any]]]) -> str:
    if not historical_findings:
        return "(no historical findings)"

    lines = []
    for item in historical_findings[:4]:
        lines.append(
            f"- type={item.get('finding_type')} | severity={item.get('severity')} | "
            f"scope={item.get('finding_scope')} | source={item.get('source_type')} | "
            f"description={item.get('description')}"
        )

    return "\n".join(lines)

def build_reverse_dependencies_block(reverse_dependencies):
    if not reverse_dependencies:
        return "(no reverse dependencies)"

    lines = []

    for dep in reverse_dependencies[:3]:
        lines.append(
            f"""REVERSE_DEPENDENCY:
PATH: {dep.get("path", "")}
SYMBOLS: {dep.get("symbols", {})}
CODE_SNIPPET:
{shorten_text(dep.get("code", ""), 500)}
"""
        )

    return "\n".join(lines)


def build_project_summary_block(project_summary):
    if not project_summary:
        return "(no project summary)"

    return json.dumps(project_summary, ensure_ascii=False, indent=2)

def should_use_dependencies(file_kind: str, dependencies: Optional[List[Dict[str, Any]]], diff_text: Optional[str]) -> bool:
    if file_kind == "header":
        return True
    if dependencies and len(dependencies) <= 2 and len(diff_text or "") < 600:
        return True
    return False


def should_use_history(file_path: str, historical_findings: Optional[List[Dict[str, Any]]]) -> bool:
    if not historical_findings:
        return False
    if len(historical_findings) <= 3:
        return True
    return False


def build_rewrite_prompt(
    file_path: str,
    file_code: str,
    diff_text: str,
    candidate_bug: Dict[str, Any],
    header_text: str,
    related_cpp_text: str,
    deps_text: str,
    history_text: str,
    file_kind: str,
) -> str:
    candidate_json = json.dumps(candidate_bug, ensure_ascii=False, indent=2)

    return f"""
You are a strict multi-language code review formatter.

You MUST NOT invent new bugs.
You MUST ONLY rewrite the provided candidate bug.
If the candidate looks weak, return {{"bug": null}}.

Return ONLY valid JSON in this exact schema:
{{
  "bug": {{
    "bug": "unsafe-command-execution",
    "cause": "short concrete reason based on visible code",
    "fix": "short concrete fix",
    "severity": "high",
    "line_start": 12,
    "line_end": 12,
    "finding_scope": "local"
  }}
}}

Or:
{{
  "bug": null
}}

Rules:
- Output JSON only
- Do not add markdown
- Do not add prose
- Keep only bug names from allowed list
- Keep original bug name
- Keep original line_start and line_end if present
- Keep original finding_scope if present
- If line_start / line_end / finding_scope / severity are missing, you may omit them
- Do not invent compilation errors
- Do not mention missing methods, missing members, missing includes, deprecated library claims, or git path issues
- reason must directly match visible code
- fix must be concrete and short

Allowed bug names:
{sorted(ALLOWED_BUG_NAMES)}

FILE: {file_path}
FILE_KIND: {file_kind}

DIFF:
{shorten_text(diff_text, 700)}

CODE:
{shorten_text(file_code, 1200)}

PAIRED_HEADER:
{shorten_text(header_text, 250)}

RELATED_CPP:
{shorten_text(related_cpp_text, 250)}

DEPENDENCY_CONTEXT:
{shorten_text(deps_text, 1200)}

HISTORICAL_FINDINGS:
{shorten_text(history_text, 120)}

CANDIDATE_BUG:
{candidate_json}
""".strip()


def parse_rewrite_response(raw_text: Optional[str]) -> Dict[str, Any]:
    if not raw_text:
        return {"parse_error": True}

    if looks_like_refusal_or_garbage(raw_text):
        return {"parse_error": True}

    try:
        data = json.loads(raw_text)
    except Exception:
        return {"parse_error": True}

    if not isinstance(data, dict):
        return {"parse_error": True}

    normalized_bugs = []

    if "bug" in data:
        bug_value = data.get("bug")

        if bug_value is None:
            return {"bug": None}

        if isinstance(bug_value, dict):
            normalized_bugs.append(bug_value)
        elif isinstance(bug_value, str):
            return {"bug": None}
        else:
            return {"parse_error": True}

    elif "bugs" in data:
        bugs_value = data.get("bugs")
        if not isinstance(bugs_value, list):
            return {"parse_error": True}
        normalized_bugs.extend(b for b in bugs_value if isinstance(b, dict))

    elif "bugsReported" in data:
        bugs_value = data.get("bugsReported")
        if not isinstance(bugs_value, list):
            return {"parse_error": True}
        normalized_bugs.extend(b for b in bugs_value if isinstance(b, dict))

    else:
        return {"parse_error": True}

    clean_bugs = []

    for bug in normalized_bugs:
        normalized_bug = {}

        if "bug" in bug:
            normalized_bug["bug"] = bug.get("bug")
        elif "name" in bug:
            normalized_bug["bug"] = bug.get("name")
        else:
            continue

        if "cause" in bug:
            normalized_bug["cause"] = bug.get("cause")
        elif "description" in bug:
            normalized_bug["cause"] = bug.get("description")
        elif "causes" in bug and isinstance(bug.get("causes"), list) and bug["causes"]:
            normalized_bug["cause"] = bug["causes"][0]
        else:
            normalized_bug["cause"] = ""

        if "fix" in bug:
            normalized_bug["fix"] = bug.get("fix")
        elif "fixes" in bug and isinstance(bug.get("fixes"), list) and bug["fixes"]:
            normalized_bug["fix"] = bug["fixes"][0]
        else:
            normalized_bug["fix"] = ""

        normalized_bug["severity"] = bug.get("severity")
        normalized_bug["line_start"] = bug.get("line_start")
        normalized_bug["line_end"] = bug.get("line_end")
        normalized_bug["finding_scope"] = bug.get("finding_scope")

        clean_bugs.append(normalized_bug)

    if not clean_bugs:
        return {"parse_error": True}

    if "bug" in data and len(clean_bugs) == 1:
        return {"bug": clean_bugs[0]}

    return {"bugs": clean_bugs}


def validate_rewritten_bug(
    rewritten_bug: Dict[str, Any],
    original_bug: Dict[str, Any],
    file_code: str,
    diff_text: str,
) -> Optional[Dict[str, Any]]:
    bug_name = normalize_bug_name(rewritten_bug.get("bug", ""))
    if bug_name != original_bug.get("bug"):
        return None

    try:
        line_start = int(rewritten_bug.get("line_start"))
        line_end = int(rewritten_bug.get("line_end"))
    except Exception:
        return None

    if line_start != original_bug.get("line_start") or line_end != original_bug.get("line_end"):
        return None

    finding_scope = normalize_scope(rewritten_bug.get("finding_scope"))
    if finding_scope != original_bug.get("finding_scope"):
        return None

    severity = normalize_severity(rewritten_bug.get("severity"))
    cause = str(rewritten_bug.get("cause", "") or "").strip()
    fix = str(rewritten_bug.get("fix", "") or "").strip()

    if len(cause) < 8 or len(fix) < 8:
        return None

    if not bug_supported_by_code(bug_name, file_code, line_start, line_end):
        return None

    if not reason_matches_bug_type(bug_name, cause, fix):
        return None

    if looks_like_refusal_or_garbage(cause) or looks_like_refusal_or_garbage(fix):
        return None

    changed_lines = extract_changed_lines(diff_text)
    if changed_lines:
        overlap = any(line in changed_lines for line in range(line_start, line_end + 1))
        if not overlap:
            return None

    suspicious_reason_phrases = [
        "not a class or namespace",
        "is not a member",
        "undeclared",
        "not declared",
        "deprecated",
        "full path to git executable",
        "replace 'git'",
        "not recommended for production use",
        "candidate bug type",
        "bug is detected",
        "not used correctly",
        "not correctly configured",
        "short concrete reason based on visible code",
        "short concrete fix",
    ]

    lowered_text = (cause + " " + fix).lower()
    if any(p in lowered_text for p in suspicious_reason_phrases):
        return None

    return {
        "bug": bug_name,
        "cause": cause,
        "fix": fix,
        "severity": severity,
        "line_start": line_start,
        "line_end": line_end,
        "finding_scope": finding_scope,
    }


def try_llm_rewrite(
    file_path: str,
    file_code: str,
    diff_text: str,
    candidate_bugs: List[Dict[str, Any]],
    header_text: str,
    related_cpp_text: str,
    deps_text: str,
    history_text: str,
    file_kind: str,
) -> Dict[str, Any]:
    if not candidate_bugs:
        return {
            "used": False,
            "error": None,
            "bugs": [],
            "llm_candidate_count": 0,
        }

    llm_candidate_bugs = limit_candidate_bugs(candidate_bugs, max_bugs=5)

    valid_bugs = []
    any_success = False
    last_error = None

    for candidate_bug in llm_candidate_bugs:
        prompt = build_rewrite_prompt(
            file_path=file_path,
            file_code=file_code,
            diff_text=diff_text,
            candidate_bug=candidate_bug,
            header_text=header_text,
            related_cpp_text=related_cpp_text,
            deps_text=deps_text,
            history_text=history_text,
            file_kind=file_kind,
        )

        try:
            raw = llm_client.generate(prompt)
            parsed = parse_rewrite_response(raw)

            if parsed.get("parse_error"):
                last_error = "llm_parse_error"
                continue

            if "bug" in parsed:
                bug_item = parsed.get("bug")
                rewritten_bugs = [] if bug_item is None else [bug_item]
            else:
                rewritten_bugs = parsed.get("bugs", [])

            if not rewritten_bugs:
                last_error = "llm_empty_result"
                continue

            validated_any = False

            for rewritten_bug in rewritten_bugs:
                rewritten_bug = dict(rewritten_bug)

                if rewritten_bug.get("line_start") is None:
                    rewritten_bug["line_start"] = candidate_bug["line_start"]

                if rewritten_bug.get("line_end") is None:
                    rewritten_bug["line_end"] = candidate_bug["line_end"]

                if not rewritten_bug.get("finding_scope"):
                    rewritten_bug["finding_scope"] = candidate_bug["finding_scope"]

                if not rewritten_bug.get("severity"):
                    rewritten_bug["severity"] = candidate_bug["severity"]

                validated = validate_rewritten_bug(
                    rewritten_bug=rewritten_bug,
                    original_bug=candidate_bug,
                    file_code=file_code,
                    diff_text=diff_text,
                )

                if validated:
                    valid_bugs.append(validated)
                    validated_any = True

            if validated_any:
                any_success = True
            else:
                last_error = "llm_validation_failed"

        except Exception as e:
            last_error = str(e)

    valid_bugs = deduplicate_bugs(valid_bugs)

    if not any_success:
        return {
            "used": False,
            "error": last_error or "llm_validation_failed",
            "bugs": [],
            "llm_candidate_count": len(llm_candidate_bugs),
        }

    return {
        "used": True,
        "error": None,
        "bugs": valid_bugs,
        "llm_candidate_count": len(llm_candidate_bugs),
    }


def merge_llm_and_fallback(candidate_bugs: List[Dict[str, Any]], llm_bugs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    llm_keys = {
        (bug["bug"], bug["line_start"], bug["line_end"], bug["finding_scope"])
        for bug in llm_bugs
    }

    merged = list(llm_bugs)

    for bug in candidate_bugs:
        key = (bug["bug"], bug["line_start"], bug["line_end"], bug["finding_scope"])
        if key not in llm_keys:
            merged.append(bug)

    return deduplicate_bugs(merged)


def run_subagent(
    file_path: str,
    file_code: str,
    dependencies: Optional[List[Dict[str, Any]]],
    symbols: Optional[Dict[str, Any]],
    diff_text: str,
    paired_header: Optional[Dict[str, Any]] = None,
    related_cpp: Optional[Dict[str, Any]] = None,
    file_kind: str = "cpp",
    historical_findings: Optional[List[Dict[str, Any]]] = None,
    reverse_dependencies: Optional[List[Dict[str, Any]]] = None,
    project_summary: Optional[Dict[str, Any]] = None,
    analysis_mode: str = "full",
) -> Dict[str, Any]:
    use_dependencies = should_use_dependencies(file_kind, dependencies, diff_text)
    use_history = should_use_history(file_path, historical_findings)

    deps_text = build_dependency_block(dependencies) if use_dependencies else "(dependency context omitted)"
    header_text = build_header_block(paired_header)
    related_cpp_text = build_related_cpp_block(related_cpp)
    history_text = build_history_block(historical_findings) if use_history else "(history omitted)"
    reverse_deps_text = build_reverse_dependencies_block(reverse_dependencies)
    project_summary_text = build_project_summary_block(project_summary)
    deps_text = deps_text + "\n\n" + reverse_deps_text + "\n\nPROJECT_SUMMARY:\n" + project_summary_text

    print("HEADER BLOCK USED:", paired_header.get("path") if paired_header else None)
    print("RELATED CPP USED:", related_cpp.get("path") if related_cpp else None)
    print("DEPENDENCIES COUNT:", len(dependencies or []))

    fallback_raw = run_fallback_analysis(
        file_path,
        file_code,
        diff_text,
        paired_header_code=paired_header.get("code", "") if paired_header else "",
        related_cpp_code=related_cpp.get("code", "") if related_cpp else "",
    )

    sanitized = sanitize_fallback_result(file_path, file_code, fallback_raw)
    candidate_bugs = deduplicate_bugs(
        sanitized.get("bugs", [])
    )

    candidate_bugs = enrich_priority_scores(
        candidate_bugs,
        historical_findings=historical_findings,
        reverse_dependencies=reverse_dependencies
    )

    provider = os.getenv("LLM_PROVIDER", "ollama")

    if analysis_mode == "graph_only":
        final_bugs = []

        for bug in candidate_bugs:
            scope = bug.get("finding_scope", "local")

            if (
                    scope == "interfile"
                    or reverse_dependencies
                    or paired_header
                    or related_cpp
            ):
                bug["finding_scope"] = "interfile"

                if bug.get("severity") == "medium":
                    bug["severity"] = "high"

                final_bugs.append(bug)

        return {
            "file": file_path,
            "result": {
                "file": file_path,
                "bugs": final_bugs,
                "fallback_used": True,
                "fallback_reason": "graph_only_mode",
                "llm_rewrite_used": False,
                "llm_rewrite_error": None,
                "candidate_count": len(candidate_bugs),
                "llm_candidate_count": 0,
                "final_bug_count": len(final_bugs),
            },
        }

    if analysis_mode == "fallback_only":
        return {
            "file": file_path,
            "result": {
                "file": file_path,
                "bugs": candidate_bugs,
                "fallback_used": True,
                "fallback_reason": "fallback_only_mode",
                "llm_rewrite_used": False,
                "llm_rewrite_error": None,
                "candidate_count": len(candidate_bugs),
                "llm_candidate_count": 0,
                "final_bug_count": len(candidate_bugs),
            },
        }

    rewrite_result = try_llm_rewrite(
        file_path=file_path,
        file_code=file_code,
        diff_text=diff_text,
        candidate_bugs=candidate_bugs,
        header_text=header_text,
        related_cpp_text=related_cpp_text,
        deps_text=deps_text,
        history_text=history_text,
        file_kind=file_kind,
    )

    if rewrite_result["used"]:
        final_bugs = merge_llm_and_fallback(candidate_bugs, rewrite_result["bugs"])
        llm_rewrite_used = True
        fallback_used = False
        fallback_reason = ""
    else:
        final_bugs = candidate_bugs
        llm_rewrite_used = False
        fallback_used = True
        fallback_reason = rewrite_result["error"] or ""

    return {
        "file": file_path,
        "result": {
            "file": file_path,
            "bugs": final_bugs,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "llm_rewrite_used": llm_rewrite_used,
            "llm_rewrite_error": rewrite_result["error"],
            "candidate_count": len(candidate_bugs),
            "llm_candidate_count": rewrite_result.get("llm_candidate_count", 0),
            "final_bug_count": len(final_bugs),
        },
    }