import os
from datetime import datetime
from html import escape


def get_severity_class(severity):
    severity = (severity or "medium").lower()

    if severity == "high":
        return "severity-high"
    if severity == "low":
        return "severity-low"

    return "severity-medium"


def collect_all_findings(results):
    findings = []

    for item in results:
        file_path = item.get("file", "")
        parsed = item.get("result", {})
        bugs = parsed.get("bugs", [])

        for bug in bugs:
            findings.append({
                "file": file_path,
                "bug": bug.get("bug", ""),
                "severity": bug.get("severity", "medium"),
                "scope": bug.get("finding_scope", "local"),
                "line_start": bug.get("line_start", ""),
                "line_end": bug.get("line_end", ""),
                "cause": bug.get("cause", ""),
                "fix": bug.get("fix", "")
            })

    return findings


def save_html_report(project_path, report_data):
    report_dir = os.path.join(project_path, "analysis_reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"html_report_{timestamp}.html")

    summary = report_data.get("summary", {})
    results = report_data.get("results", [])
    module_reports = report_data.get("module_reports", [])
    comparison = report_data.get("comparison", {})
    findings = collect_all_findings(results)

    high_count = summary.get("high_count", 0)
    interfile_count = summary.get("interfile_findings_count", 0)
    llm_provider = summary.get("llm_provider", "unknown")
    llm_model = summary.get("llm_model", "unknown")
    files_with_reverse_deps = summary.get("files_with_reverse_deps_count", 0)
    graph_nodes = summary.get("graph_nodes", 0)
    dependency_edges = summary.get("dependency_edges", 0)
    files_by_language = summary.get("files_by_language", {})

    language_cards = []

    for language, count in files_by_language.items():
        language_cards.append(f"""
        <div class="card">
            <div class="card-title">{escape(str(language))}</div>
            <div class="card-value">{escape(str(count))}</div>
        </div>
        """)

    if high_count > 0 or interfile_count > 0:
        risk_level = "HIGH"
        risk_class = "risk-high"
    elif summary.get("medium_count", 0) > 0:
        risk_level = "MEDIUM"
        risk_class = "risk-medium"
    else:
        risk_level = "LOW"
        risk_class = "risk-low"

    rows = []
    for finding in findings:
        severity_class = get_severity_class(finding["severity"])

        rows.append(f"""
        <tr>
            <td><span class="{severity_class}">{escape(str(finding["severity"]).upper())}</span></td>
            <td>{escape(str(finding["bug"]))}</td>
            <td>{escape(str(finding["scope"]))}</td>
            <td>{escape(str(finding["file"]))}</td>
            <td>{escape(str(finding["line_start"]))}-{escape(str(finding["line_end"]))}</td>
            <td>{escape(str(finding["cause"]))}</td>
            <td>{escape(str(finding["fix"]))}</td>
        </tr>
        """)

    module_blocks = []
    for module in module_reports:
        module_name = module.get("module", "unknown")
        architecture_findings = module.get("architecture_findings", [])

        if not architecture_findings:
            module_blocks.append(f"""
            <div class="module-card">
                <h3>{escape(module_name)}</h3>
                <p>No architecture findings.</p>
            </div>
            """)
            continue

        items = []
        for finding in architecture_findings:
            files = finding.get("files", [])
            files_text = ", ".join(files)

            items.append(f"""
            <li>
                <b>{escape(str(finding.get("problem", "")))}</b>
                <br>
                Severity: <span class="{get_severity_class(finding.get("severity"))}">
                    {escape(str(finding.get("severity", "medium")).upper())}
                </span>
                <br>
                Cause: {escape(str(finding.get("cause", "")))}
                <br>
                Files: {escape(files_text)}
            </li>
            """)

        module_blocks.append(f"""
        <div class="module-card">
            <h3>{escape(module_name)}</h3>
            <ul>
                {''.join(items)}
            </ul>
        </div>
        """)

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LLM Agent Analysis Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 30px;
            background: #f5f7fb;
            color: #222;
        }}

        h1, h2 {{
            color: #1f2937;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}

        .card {{
            background: white;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .card-title {{
            font-size: 13px;
            color: #666;
        }}

        .card-value {{
            font-size: 28px;
            font-weight: bold;
            margin-top: 8px;
        }}

        .risk-high {{
            color: #b91c1c;
        }}

        .risk-medium {{
            color: #b45309;
        }}

        .risk-low {{
            color: #047857;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        th, td {{
            padding: 10px;
            border-bottom: 1px solid #e5e7eb;
            text-align: left;
            vertical-align: top;
            font-size: 14px;
        }}

        th {{
            background: #111827;
            color: white;
        }}

        .severity-high {{
            color: #b91c1c;
            font-weight: bold;
        }}

        .severity-medium {{
            color: #b45309;
            font-weight: bold;
        }}

        .severity-low {{
            color: #047857;
            font-weight: bold;
        }}

        .module-card {{
            background: white;
            padding: 16px;
            border-radius: 12px;
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .small {{
            color: #666;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <h1>LLM Agent Analysis Report</h1>
    <p class="small">Generated at: {escape(str(report_data.get("generated_at", "")))}</p>
    <p class="small">Project path: {escape(str(report_data.get("project_path", "")))}</p>

    <h2>Project Summary</h2>
<div class="summary-grid">
    <div class="card">
        <div class="card-title">Risk level</div>
        <div class="card-value {risk_class}">{risk_level}</div>
    </div>
    <div class="card">
        <div class="card-title">Files analyzed</div>
        <div class="card-value">{summary.get("results_count", 0)}</div>
    </div>
    <div class="card">
        <div class="card-title">Total findings</div>
        <div class="card-value">{summary.get("total_bugs", 0)}</div>
    </div>
    <div class="card">
        <div class="card-title">Interfile findings</div>
        <div class="card-value">{summary.get("interfile_findings_count", 0)}</div>
    </div>
    <div class="card">
        <div class="card-title">High severity</div>
        <div class="card-value risk-high">{summary.get("high_count", 0)}</div>
    </div>
    <div class="card">
        <div class="card-title">Medium severity</div>
        <div class="card-value risk-medium">{summary.get("medium_count", 0)}</div>
    </div>
    <div class="card">
        <div class="card-title">LLM results</div>
        <div class="card-value">{summary.get("llm_count", 0)}</div>
    </div>
    <div class="card">
        <div class="card-title">Max workers</div>
        <div class="card-value">{summary.get("max_workers", 0)}</div>
    </div>
</div>

<h2>Project-wide Context</h2>
<div class="summary-grid">
    <div class="card">
        <div class="card-title">Graph nodes</div>
        <div class="card-value">{graph_nodes}</div>
    </div>
    <div class="card">
        <div class="card-title">Dependency edges</div>
        <div class="card-value">{dependency_edges}</div>
    </div>
    <div class="card">
        <div class="card-title">Files with reverse dependencies</div>
        <div class="card-value">{files_with_reverse_deps}</div>
    </div>
    <div class="card">
        <div class="card-title">LLM provider</div>
        <div class="card-value">{escape(str(llm_provider))}</div>
    </div>
    <div class="card">
        <div class="card-title">LLM model</div>
        <div class="card-value">{escape(str(llm_model))}</div>
    </div>
    <div class="card">
        <div class="card-title">Analysis mode</div>
        <div class="card-value">{escape(str(summary.get("analysis_mode", "")))}</div>
    </div>
</div>

<h2>Languages</h2>
<div class="summary-grid">
    {''.join(language_cards)}
</div>

<h2>File-level Findings</h2>
    <table>
        <thead>
            <tr>
                <th>Severity</th>
                <th>Bug</th>
                <th>Scope</th>
                <th>File</th>
                <th>Lines</th>
                <th>Cause</th>
                <th>Fix</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>

    <h2>Module Architecture Findings</h2>
    {''.join(module_blocks)}

    <h2>Comparison With Previous Run</h2>
    <div class="card">
        <p>Previous report: {escape(str(comparison.get("previous_report_path", "")))}</p>
        <p>New findings: {comparison.get("new_findings_count", 0)}</p>
        <p>Resolved findings: {comparison.get("resolved_findings_count", 0)}</p>
        <p>Unchanged findings: {comparison.get("unchanged_findings_count", 0)}</p>
    </div>
</body>
</html>
"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    return report_path