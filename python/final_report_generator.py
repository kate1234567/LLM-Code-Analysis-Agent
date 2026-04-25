import os
from datetime import datetime


def safe_get(data, key, default=None):
    if not isinstance(data, dict):
        return default
    return data.get(key, default)


def collect_all_bugs(results):
    bugs = []

    for item in results:
        file_path = item.get("file", "unknown")
        parsed = item.get("result", {})
        file_bugs = parsed.get("bugs", [])

        for bug in file_bugs:
            bugs.append({
                "file": file_path,
                "bug": bug.get("bug", "unknown"),
                "cause": bug.get("cause", ""),
                "fix": bug.get("fix", ""),
                "severity": bug.get("severity", "medium"),
                "line_start": bug.get("line_start"),
                "line_end": bug.get("line_end"),
                "finding_scope": bug.get("finding_scope", "local"),
            })

    return bugs


def build_risk_summary(bugs, module_reports):
    high = sum(1 for b in bugs if b.get("severity") == "high")
    medium = sum(1 for b in bugs if b.get("severity") == "medium")
    low = sum(1 for b in bugs if b.get("severity") == "low")
    interfile = sum(1 for b in bugs if b.get("finding_scope") == "interfile")

    architecture_count = 0
    for module in module_reports:
        architecture_count += len(module.get("architecture_findings", []))

    if high >= 5 or interfile >= 2 or architecture_count > 0:
        risk_level = "HIGH"
    elif high > 0 or medium >= 3:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_level": risk_level,
        "high": high,
        "medium": medium,
        "low": low,
        "interfile": interfile,
        "architecture_findings": architecture_count,
    }


def generate_final_report(report_data):
    project_path = report_data.get("project_path", "")
    changed_files = report_data.get("changed_files", [])
    summary = report_data.get("summary", {})
    results = report_data.get("results", [])
    module_reports = report_data.get("module_reports", [])
    comparison = report_data.get("comparison", {})

    bugs = collect_all_bugs(results)
    risk = build_risk_summary(bugs, module_reports)

    lines = []

    lines.append("FINAL PROJECT REVIEW REPORT")
    lines.append("=" * 60)
    lines.append(f"Generated at: {datetime.now().isoformat()}")
    lines.append(f"Project path: {project_path}")
    lines.append("")

    # 1. PROJECT-WIDE CONTEXT
    lines.append("1. PROJECT-WIDE CONTEXT")
    lines.append("-" * 60)
    lines.append(f"Graph nodes: {summary.get('graph_nodes', 'unknown')}")
    lines.append(f"Dependency edges: {summary.get('dependency_edges', 'unknown')}")
    lines.append(f"Files with reverse dependencies: {summary.get('files_with_reverse_deps_count', 0)}")
    lines.append(f"Interfile findings: {summary.get('interfile_findings_count', 0)}")
    lines.append(f"LLM provider: {summary.get('llm_provider', 'unknown')}")
    lines.append(f"LLM model: {summary.get('llm_model', 'unknown')}")
    lines.append("")

    # 2. PROJECT SUMMARY
    lines.append("2. PROJECT SUMMARY")
    lines.append("-" * 60)
    lines.append(f"Files analyzed: {summary.get('results_count', 0)}")
    lines.append(f"Total findings: {summary.get('total_bugs', 0)}")
    lines.append(f"Local findings: {summary.get('local_findings_count', 0)}")
    lines.append(f"Interfile findings: {summary.get('interfile_findings_count', 0)}")
    lines.append(f"LLM results: {summary.get('llm_count', 0)}")
    lines.append(f"Fallback results: {summary.get('fallback_count', 0)}")
    lines.append(f"Analysis mode: {summary.get('analysis_mode', '')}")
    lines.append(f"Max workers: {summary.get('max_workers', 0)}")
    lines.append("")

    lines.append("3. CHANGED FILES")
    lines.append("-" * 60)

    if changed_files:
        for file_path in changed_files:
            lines.append(f"- {file_path}")
    else:
        lines.append("- no changed files were passed")

    lines.append("")

    lines.append("4. FILE-LEVEL FINDINGS")
    lines.append("-" * 60)

    if not bugs:
        lines.append("No findings detected.")
    else:
        for index, bug in enumerate(bugs, start=1):
            lines.append(f"{index}. [{bug['severity'].upper()}] {bug['bug']}")
            lines.append(f"   File: {bug['file']}")
            lines.append(f"   Lines: {bug['line_start']}-{bug['line_end']}")
            lines.append(f"   Scope: {bug['finding_scope']}")
            lines.append(f"   Cause: {bug['cause']}")
            lines.append(f"   Fix: {bug['fix']}")
            lines.append("")

    lines.append("5. INTERFILE FINDINGS")
    lines.append("-" * 60)

    interfile_bugs = [b for b in bugs if b.get("finding_scope") == "interfile"]

    if not interfile_bugs:
        lines.append("No interfile findings detected.")
    else:
        for index, bug in enumerate(interfile_bugs, start=1):
            lines.append(f"{index}. [{bug['severity'].upper()}] {bug['bug']}")
            lines.append(f"   File: {bug['file']}")
            lines.append(f"   Lines: {bug['line_start']}-{bug['line_end']}")
            lines.append(f"   Cause: {bug['cause']}")
            lines.append(f"   Fix: {bug['fix']}")
            lines.append("")

    lines.append("6. MODULE ARCHITECTURE FINDINGS")
    lines.append("-" * 60)

    if not module_reports:
        lines.append("No module reports generated.")
    else:
        has_architecture_findings = False

        for module in module_reports:
            module_name = module.get("module", "unknown")
            architecture_findings = module.get("architecture_findings", [])

            if not architecture_findings:
                continue

            has_architecture_findings = True
            lines.append(f"Module: {module_name}")

            for finding in architecture_findings:
                lines.append(f"  - [{finding.get('severity', 'medium').upper()}] {finding.get('problem', '')}")
                lines.append(f"    Cause: {finding.get('cause', '')}")
                lines.append(f"    Files: {', '.join(finding.get('files', []))}")

            lines.append("")

        if not has_architecture_findings:
            lines.append("No architecture-level findings detected.")

    lines.append("")
    lines.append("7. COMPARISON WITH PREVIOUS RUN")
    lines.append("-" * 60)
    lines.append(f"Previous report: {comparison.get('previous_report_path')}")
    lines.append(f"New findings: {comparison.get('new_findings_count', 0)}")
    lines.append(f"Resolved findings: {comparison.get('resolved_findings_count', 0)}")
    lines.append(f"Unchanged findings: {comparison.get('unchanged_findings_count', 0)}")
    lines.append("")

    lines.append("8. CONCLUSION")
    lines.append("-" * 60)

    if risk["risk_level"] == "HIGH":
        lines.append("The project contains high-risk findings. Manual review is recommended before merging.")
    elif risk["risk_level"] == "MEDIUM":
        lines.append("The project contains moderate risks. The detected findings should be reviewed and fixed.")
    else:
        lines.append("The project has low detected risk based on the current analysis.")

    return "\n".join(lines)


def save_final_report(project_path, report_data):
    report_dir = os.path.join(project_path, "analysis_reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"final_report_{timestamp}.txt")

    content = generate_final_report(report_data)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)

    return report_path