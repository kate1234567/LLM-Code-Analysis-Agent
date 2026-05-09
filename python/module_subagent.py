import json
import os
from collections import defaultdict


def get_module_name(file_path):
    parts = file_path.replace("\\", "/").split("/")
    if len(parts) >= 2:
        return parts[-2]
    return "root"


def normalize_severity(severity):
    severity = (severity or "medium").lower()
    return severity if severity in {"low", "medium", "high"} else "medium"


def get_bug_name(bug):
    return (bug.get("bug") or bug.get("finding_type") or "").strip().lower()


def get_bug_scope(bug):
    return (bug.get("finding_scope") or "local").strip().lower()


def detect_language_by_path(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".c": "c",
        ".h": "cpp", ".hpp": "cpp",
        ".py": "python",
        ".js": "javascript", ".ts": "typescript",
        ".java": "java",
        ".cs": "csharp",
        ".go": "go",
        ".php": "php",
        ".rb": "ruby",
        ".kt": "kotlin",
        ".sql": "sql",
    }.get(ext, "unknown")


def calculate_cross_module_risk_score(interfile_count, high_count, reverse_count, files_count, deps_count):
    return (
        interfile_count * 3
        + high_count * 2
        + reverse_count
        + max(0, files_count - 5)
        + max(0, deps_count - 8)
    )


def build_module_summary(module_name, module_results):
    architecture_findings = []

    languages = defaultdict(int)
    source_types = defaultdict(int)

    interfile_bugs = []
    high_severity_count = 0
    reverse_dependencies_count = 0
    dependency_edges_count = 0

    security_files = set()
    memory_files = set()
    command_files = set()
    credential_files = set()
    dynamic_exec_files = set()
    dom_files = set()
    dependency_risk_files = set()

    for item in module_results:
        file_path = item.get("file", "")
        language = detect_language_by_path(file_path)
        languages[language] += 1

        source_type = item.get("source_type", "unknown")
        source_types[source_type] += 1

        reverse_dependencies_count += item.get("reverse_dependencies_count", 0)

        project_summary = item.get("project_summary", {}) or {}
        dependency_edges_count = max(
            dependency_edges_count,
            project_summary.get("dependency_edges", 0)
        )

        parsed = item.get("result", {}) or {}
        bugs = parsed.get("bugs", []) or []

        for bug in bugs:
            bug_name = get_bug_name(bug)
            scope = get_bug_scope(bug)
            severity = normalize_severity(bug.get("severity"))

            if severity == "high":
                high_severity_count += 1

            if scope == "interfile":
                interfile_bugs.append({
                    "file": file_path,
                    "bug": bug_name,
                    "severity": severity,
                    "line_start": bug.get("line_start"),
                    "line_end": bug.get("line_end")
                })

            if any(x in bug_name for x in ["pointer", "allocation", "memory"]):
                memory_files.add(file_path)

            if "command" in bug_name:
                command_files.add(file_path)
                security_files.add(file_path)

            if "credential" in bug_name:
                credential_files.add(file_path)
                security_files.add(file_path)

            if "dynamic-execution" in bug_name:
                dynamic_exec_files.add(file_path)
                security_files.add(file_path)

            if "dom" in bug_name:
                dom_files.add(file_path)
                security_files.add(file_path)

            if "dependency" in bug_name:
                dependency_risk_files.add(file_path)

    if interfile_bugs:
        architecture_findings.append({
            "problem": "Inter-file dependency risk",
            "cause": "Some findings depend on relationships between files, modules or imports.",
            "files": sorted({x["file"] for x in interfile_bugs}),
            "severity": "high"
        })

    if len(security_files) >= 2:
        architecture_findings.append({
            "problem": "Security-sensitive module",
            "cause": "Several files in the module contain security-related findings.",
            "files": sorted(security_files),
            "severity": "high"
        })

    if memory_files:
        architecture_findings.append({
            "problem": "Manual memory or ownership risk",
            "cause": "The module contains pointer, allocation or manual memory management findings.",
            "files": sorted(memory_files),
            "severity": "high"
        })

    if command_files:
        architecture_findings.append({
            "problem": "Unsafe command execution risk",
            "cause": "The module contains code paths that may execute external commands.",
            "files": sorted(command_files),
            "severity": "high"
        })

    if credential_files:
        architecture_findings.append({
            "problem": "Hardcoded secrets risk",
            "cause": "Credentials or tokens are stored directly in source code.",
            "files": sorted(credential_files),
            "severity": "high"
        })

    if dynamic_exec_files:
        architecture_findings.append({
            "problem": "Dynamic code execution risk",
            "cause": "The module uses eval, exec or similar dynamic execution mechanisms.",
            "files": sorted(dynamic_exec_files),
            "severity": "high"
        })

    if dom_files:
        architecture_findings.append({
            "problem": "Unsafe DOM manipulation risk",
            "cause": "The module uses DOM APIs that may introduce XSS risks.",
            "files": sorted(dom_files),
            "severity": "medium"
        })

    if dependency_risk_files:
        architecture_findings.append({
            "problem": "Risky dependency usage",
            "cause": "The module imports dependencies that require additional validation.",
            "files": sorted(dependency_risk_files),
            "severity": "medium"
        })

    if len(module_results) >= 5:
        architecture_findings.append({
            "problem": "Large module",
            "cause": "The module contains many analyzed files and may require decomposition.",
            "files": sorted([x.get("file", "") for x in module_results]),
            "severity": "medium"
        })

    interfile_count = len(interfile_bugs)

    risk_score = calculate_cross_module_risk_score(
        interfile_count,
        high_severity_count,
        reverse_dependencies_count,
        len(module_results),
        dependency_edges_count
    )

    return {
        "module": module_name,
        "files_count": len(module_results),
        "languages": dict(languages),
        "source_types": dict(source_types),
        "interfile_findings_count": interfile_count,
        "high_severity_count": high_severity_count,
        "reverse_dependencies_count": reverse_dependencies_count,
        "dependency_edges_count": dependency_edges_count,
        "cross_module_risk_score": risk_score,
        "architecture_findings": architecture_findings
    }


def run_module_subagents(results):
    modules = defaultdict(list)

    for item in results:
        file_path = item.get("file", "")
        if file_path:
            modules[get_module_name(file_path)].append(item)

    return [
        build_module_summary(module_name, module_results)
        for module_name, module_results in modules.items()
    ]


def save_module_report(project_path, module_reports):
    from datetime import datetime

    report_dir = os.path.join(project_path, "analysis_reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"module_report_{timestamp}.json")

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(module_reports, f, ensure_ascii=False, indent=2)

    return report_path