import json
from collections import defaultdict


def get_module_name(file_path):
    parts = file_path.replace("\\", "/").split("/")

    if len(parts) >= 2:
        return parts[-2]

    return "root"


def normalize_severity(severity):
    severity = (severity or "medium").lower()

    if severity not in {"low", "medium", "high"}:
        return "medium"

    return severity


def build_module_summary(module_name, module_results):
    architecture_findings = []

    interfile_bugs = []
    raw_pointer_files = set()
    command_execution_files = set()
    credential_files = set()

    for item in module_results:
        file_path = item.get("file", "")
        parsed = item.get("result", {})
        bugs = parsed.get("bugs", [])

        for bug in bugs:
            bug_name = bug.get("bug", "")
            scope = bug.get("finding_scope", "local")
            severity = normalize_severity(bug.get("severity"))

            if scope == "interfile":
                interfile_bugs.append({
                    "file": file_path,
                    "bug": bug_name,
                    "severity": severity,
                    "line_start": bug.get("line_start"),
                    "line_end": bug.get("line_end")
                })

            if "pointer" in bug_name or "allocation" in bug_name or "memory" in bug_name:
                raw_pointer_files.add(file_path)

            if bug_name == "unsafe-command-execution":
                command_execution_files.add(file_path)

            if bug_name == "hardcoded-credentials":
                credential_files.add(file_path)

    if interfile_bugs:
        architecture_findings.append({
            "problem": "Inter-file ownership/lifetime issue",
            "cause": "Several findings depend on relations between header and implementation files.",
            "files": sorted({x["file"] for x in interfile_bugs}),
            "severity": "high"
        })

    if len(raw_pointer_files) >= 2:
        architecture_findings.append({
            "problem": "Unsafe raw pointer design across module",
            "cause": "Raw pointers or manual memory management appear in several module files.",
            "files": sorted(raw_pointer_files),
            "severity": "high"
        })

    if len(command_execution_files) >= 1:
        architecture_findings.append({
            "problem": "Unsafe external command execution",
            "cause": "The module executes shell/system commands, which may create command injection risks.",
            "files": sorted(command_execution_files),
            "severity": "high"
        })

    if len(credential_files) >= 1:
        architecture_findings.append({
            "problem": "Secrets are stored directly in code",
            "cause": "Credentials or tokens are detected in source files.",
            "files": sorted(credential_files),
            "severity": "high"
        })

    return {
        "module": module_name,
        "files_count": len(module_results),
        "architecture_findings": architecture_findings
    }


def run_module_subagents(results):
    modules = defaultdict(list)

    for item in results:
        file_path = item.get("file", "")
        if not file_path:
            continue

        module_name = get_module_name(file_path)
        modules[module_name].append(item)

    module_reports = []

    for module_name, module_results in modules.items():
        module_reports.append(
            build_module_summary(module_name, module_results)
        )

    return module_reports


def save_module_report(project_path, module_reports):
    import os
    from datetime import datetime

    report_dir = os.path.join(project_path, "analysis_reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"module_report_{timestamp}.json")

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(module_reports, f, ensure_ascii=False, indent=2)

    return report_path