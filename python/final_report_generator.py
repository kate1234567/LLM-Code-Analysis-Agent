import os
from datetime import datetime
from evaluation_metrics import calculate_metrics
import json

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

def build_bug_signature(bug):
    return (
        bug.get("file", ""),
        bug.get("bug", ""),
        bug.get("line_start", 0),
        bug.get("line_end", 0),
        bug.get("severity", ""),
        bug.get("finding_scope", "")
    )

def compare_with_previous_run(current_results, previous_results):
    current_signatures = set()
    previous_signatures = set()

    for item in current_results:
        result = item.get("result", {})
        file_path = item.get("file", "")

        for bug in result.get("bugs", []):
            bug["file"] = file_path
            current_signatures.add(build_bug_signature(bug))

    for item in previous_results:
        result = item.get("result", {})
        file_path = item.get("file", "")

        for bug in result.get("bugs", []):
            bug["file"] = file_path
            previous_signatures.add(build_bug_signature(bug))

    new_findings = current_signatures - previous_signatures
    resolved_findings = previous_signatures - current_signatures
    unchanged_findings = current_signatures & previous_signatures

    return {
        "new_findings_count": len(new_findings),
        "resolved_findings_count": len(resolved_findings),
        "unchanged_findings_count": len(unchanged_findings)
    }

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
    ground_truth = [
        ("main.cpp", "Raw pointer ownership"),
        ("db.cpp", "Unsafe system call"),
        ("user.h", "Missing virtual destructor"),
    ]

    metrics = calculate_metrics(
        ground_truth,
        bugs
    )

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

    lines.append("")
    lines.append("8. EVALUATION METRICS")
    lines.append("-" * 60)
    lines.append(f"Ground truth bugs: {metrics['ground_truth']}")
    lines.append(f"Detected by agent: {metrics['detected']}")
    lines.append(f"True positive: {metrics['true_positive']}")
    lines.append(f"False positive: {metrics['false_positive']}")
    lines.append(f"False negative: {metrics['false_negative']}")
    lines.append(f"Precision: {metrics['precision']}%")
    lines.append(f"Recall: {metrics['recall']}%")
    lines.append(f"F1-score: {metrics['f1_score']}%")
    lines.append("")

    lines.append("9. CONCLUSION")
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

def save_sarif_report(project_path, report_data):
    report_dir = os.path.join(project_path, "analysis_reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(
        report_dir,
        f"report_{timestamp}.sarif"
    )

    results = []

    for item in report_data.get("results", []):
        file_path = item.get("file", "")
        parsed = item.get("result", {})
        bugs = parsed.get("bugs", [])

        for bug in bugs:
            severity = bug.get("severity", "medium")
            message = bug.get("bug", "")
            line_start = bug.get("line_start", 1)
            line_end = bug.get("line_end", line_start)

            level = "warning"

            if severity == "high":
                level = "error"
            elif severity == "low":
                level = "note"

            results.append({
                "ruleId": map_rule_id(message),
                "level": level,
                "message": {
                    "text": message
                },
                "properties": {
                    "cause": bug.get("cause", ""),
                    "fix": bug.get("fix", ""),
                    "scope": bug.get("finding_scope", "local"),
                    "confidence_score": bug.get("confidence_score", 0),
                    "validation_status": bug.get("validation_status", "unknown"),
                    "priority_score": bug.get("priority_score", 0)
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": file_path
                            },
                            "region": {
                                "startLine": line_start,
                                "endLine": line_end
                            }
                        }
                    }
                ]
            })

    sarif_data = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
    {
        "tool": {
            "driver": {
                "name": "LLM Agent Code Analyzer",
                "version": "1.0",
                "rules": [
                    {
                        "id": "RawPointerOwnership",
                        "name": "Raw Pointer Ownership Risk",
                        "shortDescription": {
                            "text": "Unsafe raw pointer ownership detected"
                        },
                        "fullDescription": {
                            "text": "Manual ownership management may cause leaks, double free, or invalid memory access."
                        },
                        "help": {
                            "text": "Use RAII and smart pointers like std::unique_ptr or std::shared_ptr."
                        }
                    },
                    {
                        "id": "UnsafeSystemCall",
                        "name": "Unsafe System Command Execution",
                        "shortDescription": {
                            "text": "Unsafe system() or _popen() usage detected"
                        },
                        "fullDescription": {
                            "text": "Direct shell execution may introduce security risks and command injection vulnerabilities."
                        },
                        "help": {
                            "text": "Use safer process APIs and validate all external inputs."
                        }
                    },
                    {
                        "id": "ManualMemoryManagement",
                        "name": "Manual Memory Management Risk",
                        "shortDescription": {
                            "text": "Manual allocation patterns detected"
                        },
                        "fullDescription": {
                            "text": "Manual memory allocation increases the probability of memory leaks and invalid access."
                        },
                        "help": {
                            "text": "Prefer STL containers and RAII over malloc/new/delete patterns."
                        }
                    },
                    {
                        "id": "GeneralCodeRisk",
                        "name": "General Code Quality Risk",
                        "shortDescription": {
                            "text": "General code quality issue detected"
                        },
                        "fullDescription": {
                            "text": "Potential maintainability, reliability, or architectural issue detected by analysis."
                        },
                        "help": {
                            "text": "Review the issue manually and apply project-specific best practices."
                        }
                    }
                ]
            }
        },
        "results": results
    }
]
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            sarif_data,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(f"SARIF REPORT SAVED: {report_path}")

    return report_path

def map_rule_id(bug_name):
    if "pointer" in bug_name.lower():
        return "RawPointerOwnership"
    if "system" in bug_name.lower() or "_popen" in bug_name.lower():
        return "UnsafeSystemCall"
    if "memory" in bug_name.lower():
        return "ManualMemoryManagement"

    return "GeneralCodeRisk"