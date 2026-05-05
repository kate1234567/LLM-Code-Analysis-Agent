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

def get_top_priority_findings(results, limit=5):
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
                "priority_score": bug.get("priority_score", 0),
                "line_start": bug.get("line_start", ""),
                "line_end": bug.get("line_end", "")
            })

    findings.sort(
        key=lambda x: x.get("priority_score", 0),
        reverse=True
    )

    return findings[:limit]

def get_top_interfile_findings(results, limit=5):
    findings = []

    for item in results:
        file_path = item.get("file", "")
        parsed = item.get("result", {})
        bugs = parsed.get("bugs", [])

        for bug in bugs:
            scope = bug.get("finding_scope", "local")

            if scope != "interfile":
                continue

            findings.append({
                "file": file_path,
                "bug": bug.get("bug", ""),
                "severity": bug.get("severity", "medium"),
                "priority_score": bug.get("priority_score", 0),
                "impact_radius": bug.get("impact_radius", 0),
                "line_start": bug.get("line_start", ""),
                "line_end": bug.get("line_end", ""),
                "cause": bug.get("cause", ""),
                "fix": bug.get("fix", "")
            })

    findings.sort(
        key=lambda x: x.get("priority_score", 0),
        reverse=True
    )

    return findings[:limit]

def save_html_report(project_path, report_data):
    report_dir = os.path.join(project_path, "analysis_reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"html_report_{timestamp}.html")

    summary = report_data.get("summary", {})
    results = report_data.get("results", [])
    module_reports = report_data.get("module_reports", [])
    module_reports = sorted(
        module_reports,
        key=lambda x: x.get("cross_module_risk_score", 0),
        reverse=True
    )

    top_module_blocks = []

    for module in module_reports[:5]:
        module_name = module.get("module", "unknown")
        risk_score = module.get("cross_module_risk_score", 0)
        interfile_count = module.get("interfile_findings_count", 0)
        high_count = module.get("high_severity_count", 0)
        reverse_count = module.get("reverse_dependencies_count", 0)

        top_module_blocks.append(f"""
        <div class="module-card">
            <h3>{escape(str(module_name))}</h3>

            <p>
                <b>Risk Score:</b>
                <span class="risk-high">{risk_score}</span>
            </p>

            <p>
                Interfile findings: {interfile_count}<br>
                High severity findings: {high_count}<br>
                Reverse dependencies: {reverse_count}
            </p>
        </div>
        """)
    comparison = report_data.get("comparison", {})
    class_reports = report_data.get("class_reports", [])
    dependency_graph_svg = report_data.get("dependency_graph_svg", "")
    findings = collect_all_findings(results)
    top_findings = get_top_priority_findings(results)
    top_interfile_findings = get_top_interfile_findings(results)

    high_count = summary.get("high_count", 0)
    interfile_count = summary.get("interfile_findings_count", 0)
    llm_provider = summary.get("llm_provider", "unknown")
    llm_model = summary.get("llm_model", "unknown")
    files_with_reverse_deps = summary.get("files_with_reverse_deps_count", 0)
    graph_nodes = summary.get("graph_nodes", 0)
    dependency_edges = summary.get("dependency_edges", 0)
    files_by_language = summary.get("files_by_language", {})
    supported_languages = summary.get("supported_languages", [])
    function_graph_nodes = summary.get("function_graph_nodes", 0)
    function_graph_edges = summary.get("function_graph_edges", 0)
    structural_graph_nodes = summary.get("structural_graph_nodes", 0)
    structural_graph_edges = summary.get("structural_graph_edges", 0)
    structural_graph_types = summary.get("structural_graph_types", [])

    clang_ast_report = report_data.get("clang_ast_report", {})

    clang_ast_files = summary.get("clang_ast_files", 0)
    clang_ast_classes = summary.get("clang_ast_classes", 0)
    clang_ast_functions = summary.get("clang_ast_functions", 0)
    clang_ast_raw_pointer_fields = summary.get(
        "clang_ast_raw_pointer_fields",
        0
    )

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
        cross_module_risk_score = module.get("cross_module_risk_score", 0)
        interfile_findings_count = module.get("interfile_findings_count", 0)
        high_severity_count = module.get("high_severity_count", 0)
        reverse_dependencies_count = module.get("reverse_dependencies_count", 0)

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
                Severity:
                <span class="{get_severity_class(finding.get("severity"))}">
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

            <p>
                <b>Module Risk Score:</b>
                <span class="risk-high">{cross_module_risk_score}</span>
            </p>

            <p>
                Interfile findings: {interfile_findings_count}<br>
                High severity findings: {high_severity_count}<br>
                Reverse dependencies: {reverse_dependencies_count}
            </p>

            <ul>
                {''.join(items)}
            </ul>
        </div>
        """)

    class_blocks = []

    for class_item in class_reports:
        class_name = class_item.get("class_name", "unknown")
        class_risk_score = class_item.get("class_risk_score", 0)
        high_findings_count = class_item.get("high_findings_count", 0)
        interfile_findings_count = class_item.get(
            "interfile_findings_count",
            0
        )
        class_findings = class_item.get("findings", [])

        items = []

        for finding in class_findings:
            items.append(f"""
            <li>
                <b>{escape(str(finding.get("problem", "")))}</b>
                <br>
                Severity:
                <span class="{get_severity_class(finding.get("severity"))}">
                    {escape(str(finding.get("severity", "medium")).upper())}
                </span>
                <br>
                Cause: {escape(str(finding.get("cause", "")))}
            </li>
            """)

        class_blocks.append(f"""
        <div class="module-card">
            <h3>Class: {escape(class_name)}</h3>

            <p>
                <b>Class Risk Score:</b>
                <span class="risk-high">{class_risk_score}</span>
            </p>

            <p>
                High findings: {high_findings_count}<br>
                Interfile findings: {interfile_findings_count}
            </p>

            <ul>
                {''.join(items)}
            </ul>
        </div>
        """)

    ast_blocks = []

    for file_path, ast_data in clang_ast_report.items():
        classes_count = ast_data.get("classes_count", 0)
        functions_count = ast_data.get("functions_count", 0)
        raw_pointer_fields_count = ast_data.get(
            "raw_pointer_fields_count",
            0
        )

        classes = ast_data.get("classes", [])

        class_items = []

        for cls in classes:
            class_name = cls.get("name", "unknown")
            fields_count = cls.get("fields_count", 0)
            methods_count = cls.get("methods_count", 0)

            class_items.append(f"""
            <li>
                <b>{escape(str(class_name))}</b><br>
                Fields: {fields_count}<br>
                Methods: {methods_count}
            </li>
            """)

        ast_blocks.append(f"""
        <div class="module-card">
            <h3>{escape(str(file_path))}</h3>

            <p>
                <b>Classes:</b> {classes_count}<br>
                <b>Functions:</b> {functions_count}<br>
                <b>Raw pointer fields:</b>
                <span class="risk-high">
                    {raw_pointer_fields_count}
                </span>
            </p>

            <ul>
                {''.join(class_items)}
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
    <div class="card-title">Function graph nodes</div>
    <div class="card-value">{function_graph_nodes}</div>
    </div>

    <div class="card">
    <div class="card-title">Function graph edges</div>
    <div class="card-value">{function_graph_edges}</div>
    </div>

    <div class="card">
    <div class="card-title">Supported languages</div>
    <div class="card-value">{escape(", ".join(supported_languages))}</div>
</div>
</div>

<h2>Dependency Graph Visualization</h2>
<div class="module-card">
    {dependency_graph_svg}
</div>

<div class="summary-grid">
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
<h2>Clang AST Structural Analysis</h2>

<div class="summary-grid">
    <div class="card">
        <div class="card-title">AST files</div>
        <div class="card-value">{clang_ast_files}</div>
    </div>

    <div class="card">
        <div class="card-title">Classes detected</div>
        <div class="card-value">{clang_ast_classes}</div>
    </div>

    <div class="card">
        <div class="card-title">Functions detected</div>
        <div class="card-value">{clang_ast_functions}</div>
    </div>

    <div class="card">
        <div class="card-title">Raw pointer fields</div>
        <div class="card-value risk-high">
            {clang_ast_raw_pointer_fields}
        </div>
    </div>
</div>

{''.join(ast_blocks)}

<h2>Languages</h2>
<div class="summary-grid">
    {''.join(language_cards)}
</div>
<h2>Top Critical Interfile Risks</h2>

<div class="module-card">
    <h3>Why Interfile Risks Matter</h3>

    <p>
        Interfile findings represent issues that cannot be detected
        by isolated single-file analysis.
    </p>

    <p>
        These problems appear only when analyzing relationships
        between headers, source files, ownership models,
        and reverse dependencies across the whole project.
    </p>

    <p>
        This is the key advantage of the proposed LLM-agent approach.
    </p>
</div>

<div class="card">
    <table>
        <thead>
            <tr>
                <th>Priority</th>
                <th>Impact Radius</th>
                <th>Bug</th>
                <th>Severity</th>
                <th>File</th>
                <th>Lines</th>
                <th>Cause</th>
                <th>Recommendation</th>
            </tr>
        </thead>
        <tbody>
            {
                ''.join([
                    f'''
                    <tr>
                        <td><b>{item.get("priority_score", 0)}</b></td>
                        <td><b>{item.get("impact_radius", 0)}</b></td>
                        <td>{escape(str(item.get("bug", "")))}</td>
                        <td>
                            <span class="{get_severity_class(item.get("severity"))}">
                                {escape(str(item.get("severity", "")).upper())}
                            </span>
                        </td>
                        <td>{escape(str(item.get("file", "")))}</td>
                        <td>{item.get("line_start", "")}-{item.get("line_end", "")}</td>
                        <td>{escape(str(item.get("cause", "")))}</td>
                        <td>{escape(str(item.get("fix", "")))}</td>
                    </tr>
                    '''
                    for item in top_interfile_findings
                ])
            }
        </tbody>
    </table>
</div>

<h2>Top Priority Findings</h2>

<div class="module-card">
    <h3>Priority Score Logic</h3>

    <p>
        Priority score is calculated using several factors:
    </p>

    <ul>
        <li><b>Severity:</b> high > medium > low</li>
        <li><b>Finding scope:</b> interfile issues receive higher weight</li>
        <li><b>Changed file bonus:</b> modified files are prioritized</li>
        <li><b>Historical findings:</b> repeated issues increase priority</li>
        <li><b>Reverse dependencies:</b> files affecting many others receive higher priority</li>
    </ul>

    <p>
        This allows the system to rank findings by real project impact,
        not only by isolated local severity.
    </p>
</div>
<div class="card">
    <table>
        <thead>
            <tr>
                <th>Priority</th>
                <th>Bug</th>
                <th>Severity</th>
                <th>Risk Trend</th>
                <th>Scope</th>
                <th>File</th>
                <th>Lines</th>
            </tr>
        </thead>
        <tbody>
            {
                ''.join([
                    f'''
                    <tr>
                        <td><b>{item.get("priority_score", 0)}</b></td>
                        <td>{escape(str(item.get("bug", "")))}</td>
                        <td>
                            <span class="{get_severity_class(item.get("severity"))}">
                                {escape(str(item.get("severity", "")).upper())}
                            </span>
                        </td>
                        <td>
                                <b>{escape(str(item.get("risk_trend", "STABLE")))}</b>
                        </td>
                        <td>{escape(str(item.get("scope", "")))}</td>
                        <td>{escape(str(item.get("file", "")))}</td>
                        <td>{item.get("line_start", "")}-{item.get("line_end", "")}</td>
                    </tr>
                    '''
                    for item in top_findings
                ])
            }
        </tbody>
    </table>
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
<h2>Top Risk Modules</h2>

{''.join(top_module_blocks)}
    <h2>Module Architecture Findings</h2>
    {''.join(module_blocks)}
    <h2>Class-level Findings</h2>
    {''.join(class_blocks)}

    <h2>Comparison With Previous Run</h2>
    <div class="card">
        <p>Previous report: {escape(str(comparison.get("previous_report_path", "")))}</p>
        <p>New findings: {comparison.get("new_findings_count", 0)}</p>
        <p>Resolved findings: {comparison.get("resolved_findings_count", 0)}</p>
        <p>Unchanged findings: {comparison.get("unchanged_findings_count", 0)}</p>
    </div>
    <h2>Unchanged Findings Evolution</h2>

<div class="card">
    <table>
        <thead>
            <tr>
                <th>File</th>
                <th>Bug</th>
                <th>Lines</th>
                <th>Scope</th>
                <th>Severity</th>
                <th>Changes</th>
            </tr>
        </thead>
        <tbody>
            {
                ''.join([
                    f'''
                    <tr>
                        <td>{escape(str(item.get("file", "")))}</td>
                        <td>{escape(str(item.get("bug", "")))}</td>
                        <td>{item.get("line_start", "")}-{item.get("line_end", "")}</td>
                        <td>{escape(str(item.get("finding_scope", item.get("scope", ""))))}</td>
                        <td>
                            <span class="{get_severity_class(item.get("severity"))}">
                                {escape(str(item.get("severity", "")).upper())}
                            </span>
                        </td>
                        <td>
                            {"; ".join(item.get("changes", [])) if item.get("changes") else "none"}
                        </td>
                    </tr>
                    '''
                    for item in comparison.get("unchanged_findings", [])
                ])
            }
        </tbody>
    </table>
</div>
</body>
</html>
"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    return report_path