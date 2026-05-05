import json
from collections import defaultdict


def normalize_severity(severity):
    severity = (severity or "medium").lower()

    if severity not in {"low", "medium", "high"}:
        return "medium"

    return severity


def extract_classes_from_symbols(symbols):
    if not symbols:
        return []

    classes = symbols.get("classes", [])

    result = []

    for cls in classes:
        if isinstance(cls, str):
            result.append(cls)

    return result


def detect_class_risks(class_name, file_path, bugs):
    findings = []

    high_count = 0
    interfile_count = 0
    pointer_related = 0
    command_related = 0

    for bug in bugs:
        bug_name = (bug.get("bug") or "").lower()
        severity = normalize_severity(
            bug.get("severity")
        )
        scope = (
            bug.get("finding_scope") or "local"
        ).lower()

        if severity == "high":
            high_count += 1

        if scope == "interfile":
            interfile_count += 1

        if (
            "pointer" in bug_name
            or "allocation" in bug_name
            or "memory" in bug_name
        ):
            pointer_related += 1

        if "command" in bug_name:
            command_related += 1

    class_risk_score = (
        high_count * 3
        + interfile_count * 4
        + pointer_related * 2
        + command_related * 2
    )

    if interfile_count > 0:
        findings.append({
            "problem": "Inter-file ownership issue",
            "severity": "high",
            "cause": "Class may have ownership/lifetime problems across header and implementation files."
        })

    if pointer_related > 0:
        findings.append({
            "problem": "Raw pointer design risk",
            "severity": "high",
            "cause": "Manual memory handling detected around class-related logic."
        })

    if command_related > 0:
        findings.append({
            "problem": "Unsafe command execution",
            "severity": "medium",
            "cause": "Class may trigger unsafe shell/system execution."
        })

    if high_count == 0 and not findings:
        findings.append({
            "problem": "No critical class-level risks detected",
            "severity": "low",
            "cause": "No major ownership or security risks were detected for this class."
        })

    return {
        "class_name": class_name,
        "file": file_path,
        "class_risk_score": class_risk_score,
        "high_findings_count": high_count,
        "interfile_findings_count": interfile_count,
        "findings": findings
    }


def run_class_subagents(results):
    class_reports = []

    for item in results:
        file_path = item.get("file", "")
        parsed = item.get("result", {})
        bugs = parsed.get("bugs", [])

        symbols = item.get("symbols", {})
        classes = extract_classes_from_symbols(symbols)

        if not classes:
            continue

        for class_name in classes:
            class_report = detect_class_risks(
                class_name,
                file_path,
                bugs
            )

            class_reports.append(class_report)

    return class_reports


def save_class_report(project_path, class_reports):
    import os
    from datetime import datetime

    report_dir = os.path.join(
        project_path,
        "analysis_reports"
    )
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    report_path = os.path.join(
        report_dir,
        f"class_report_{timestamp}.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            class_reports,
            f,
            ensure_ascii=False,
            indent=2
        )

    return report_path