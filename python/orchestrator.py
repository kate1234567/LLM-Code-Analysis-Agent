import os
import sys
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from context_selector import build_selected_context
from module_subagent import run_module_subagents, save_module_report
from final_report_generator import save_final_report
from project_scanner import scan_project
from project_graph_builder import build_graph
from json_context_loader import load_context_from_json
from html_report_generator import save_html_report
from subagent_runner import run_subagent
from db_writer import (
    get_connection,
    get_or_create_project,
    create_pull_request,
    save_project_context,
    save_finding,
    save_recommendation,
    save_log_metric,
    create_subagent_task,
    update_subagent_task,
    load_recent_findings_for_file
)

JSON_CONTEXT_PATH = r"C:\Users\katew\source\repos\LLM\python\project_context.json"


def normalize_changed_paths(project_path, changed_files, all_cpp_files):
    project_root = os.path.abspath(project_path)
    cpp_abs = {os.path.abspath(p): p for p in all_cpp_files}

    selected = []

    for rel_path in changed_files:
        rel_path = rel_path.strip().strip('"').replace("/", os.sep)
        abs_path = os.path.abspath(os.path.join(project_root, rel_path))

        if abs_path in cpp_abs:
            selected.append(cpp_abs[abs_path])

    return selected


def normalize_changed_headers(project_path, changed_files, all_header_files):
    project_root = os.path.abspath(project_path)
    header_abs = {os.path.abspath(p): p for p in all_header_files}

    selected = []

    for rel_path in changed_files:
        rel_path = rel_path.strip().strip('"').replace("/", os.sep)
        abs_path = os.path.abspath(os.path.join(project_root, rel_path))

        if abs_path in header_abs:
            selected.append(header_abs[abs_path])

    return selected


def find_impacted_cpp_files_by_headers(changed_header_files, graph, all_cpp_files):
    impacted = set()

    changed_header_names = {
        os.path.basename(h).lower().replace("\\", "/")
        for h in changed_header_files
    }

    for cpp_file in all_cpp_files:
        node = graph.get(cpp_file, {})
        includes = node.get("includes", []) if isinstance(node, dict) else []

        for inc in includes:
            inc_name = os.path.basename(inc).lower().replace("\\", "/")
            if inc_name in changed_header_names:
                impacted.add(cpp_file)
                break

    return sorted(impacted)


def build_analysis_file_list(changed_cpp_files, changed_header_files, impacted_cpp_files):
    return sorted(set(changed_cpp_files + changed_header_files + impacted_cpp_files))


def load_raw_json_text(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return f.read()


def deduplicate_bugs(bugs):
    best_by_slot = {}

    def scope_rank(scope):
        return 2 if scope == "interfile" else 1

    def severity_rank(sev):
        return {"low": 1, "medium": 2, "high": 3}.get((sev or "").lower(), 0)

    for bug in bugs:
        slot = (
            bug.get("line_start"),
            bug.get("line_end")
        )

        current = best_by_slot.get(slot)

        if current is None:
            best_by_slot[slot] = bug
            continue

        current_scope_rank = scope_rank(current.get("finding_scope"))
        new_scope_rank = scope_rank(bug.get("finding_scope"))

        if new_scope_rank > current_scope_rank:
            best_by_slot[slot] = bug
            continue

        if new_scope_rank == current_scope_rank:
            current_sev_rank = severity_rank(current.get("severity"))
            new_sev_rank = severity_rank(bug.get("severity"))

            if new_sev_rank > current_sev_rank:
                best_by_slot[slot] = bug

    return list(best_by_slot.values())


def classify_source_type(parsed):
    llm_rewrite_used = bool(parsed.get("llm_rewrite_used"))
    fallback_used = bool(parsed.get("fallback_used"))

    if llm_rewrite_used and fallback_used:
        return "fallback+llm"
    if llm_rewrite_used:
        return "llm"
    return "fallback"


def process_cpp_file(project_id, pr_id, target_file, context_map, graph):
    conn = get_connection()
    task_id = None
    has_paired_header = False
    has_related_cpp = False

    try:
        print("ANALYZING:", target_file)

        task_id = create_subagent_task(pr_id, target_file, status="running", conn=conn)
        print("CREATED SUBAGENT TASK:", task_id)

        save_log_metric(project_id, pr_id, "subagent_task", "task_created", {
            "task_id": task_id,
            "file": target_file
        }, conn=conn)

        selected_context = build_selected_context(
            target_file=target_file,
            context_map=context_map,
            graph=graph
        )

        file_code = selected_context.get("file_code", "")
        diff_text = selected_context.get("diff", "")
        symbols = selected_context.get("symbols", {})
        dependencies = selected_context.get("direct_dependencies", [])
        paired_header = selected_context.get("paired_header", {})
        related_cpp = selected_context.get("related_cpp", {})
        reverse_dependencies = selected_context.get("reverse_dependencies", [])
        project_summary = selected_context.get("project_summary", {})
        print("REVERSE DEPENDENCIES COUNT:", len(reverse_dependencies))
        print("PROJECT SUMMARY:", project_summary)

        has_paired_header = bool(paired_header and paired_header.get("path"))
        has_related_cpp = bool(related_cpp and related_cpp.get("path"))

        historical_findings = load_recent_findings_for_file(
            project_id,
            target_file,
            limit=10,
            conn=conn
        )

        print("HISTORICAL FINDINGS COUNT:", len(historical_findings))

        file_kind = "header" if target_file.lower().endswith((".h", ".hpp")) else "cpp"

        print("PAIRED HEADER:", paired_header.get("path"))
        print("RELATED CPP:", related_cpp.get("path"))

        subagent_start = time.time()
        result = run_subagent(
            target_file,
            file_code,
            dependencies,
            symbols,
            diff_text,
            paired_header,
            related_cpp,
            file_kind,
            historical_findings,
            reverse_dependencies,
            project_summary
        )
        subagent_duration = int((time.time() - subagent_start) * 1000)

        print("SUBAGENT RAW RESULT:", result)

        if "error" in result:
            update_subagent_task(task_id, "failed", completed=True, conn=conn)

            save_log_metric(project_id, pr_id, "subagent", "error", {
                "file": target_file,
                "task_id": task_id,
                "error": result["error"]
            }, subagent_duration, conn=conn)

            return {
                "file": target_file,
                "task_id": task_id,
                "error": result["error"],
                "source_type": "error",
                "has_paired_header": has_paired_header,
                "has_related_cpp": has_related_cpp
            }

        update_subagent_task(task_id, "completed", completed=True, conn=conn)

        save_log_metric(project_id, pr_id, "subagent", "finish", {
            "file": target_file,
            "dependencies_count": len(dependencies),
            "task_id": task_id
        }, subagent_duration, conn=conn)

        parsed = result.get("result", {})
        bugs = deduplicate_bugs(parsed.get("bugs", []))
        parsed["bugs"] = bugs

        source_type = classify_source_type(parsed)

        saved_findings = []
        saved_recommendations = []

        for bug in bugs:
            finding_id = save_finding(pr_id, target_file, bug, source_type=source_type, conn=conn)
            print("SAVED FINDING:", finding_id)

            save_log_metric(project_id, pr_id, "finding_writer", "finding_saved", {
                "finding_id": finding_id,
                "file": target_file,
                "bug": bug.get("bug", "unknown"),
                "task_id": task_id,
                "source_type": source_type
            }, conn=conn)

            recommendation_id = save_recommendation(finding_id, bug, conn=conn)
            print("SAVED RECOMMENDATION:", recommendation_id)

            save_log_metric(project_id, pr_id, "recommendation_writer", "recommendation_saved", {
                "recommendation_id": recommendation_id,
                "finding_id": finding_id,
                "task_id": task_id
            }, conn=conn)

            saved_findings.append(finding_id)
            saved_recommendations.append(recommendation_id)

        return {
            "file": target_file,
            "task_id": task_id,
            "result": parsed,
            "finding_ids": saved_findings,
            "recommendation_ids": saved_recommendations,
            "source_type": source_type,
            "has_paired_header": has_paired_header,
            "has_related_cpp": has_related_cpp,
            "reverse_dependencies_count": len(reverse_dependencies),
            "project_summary": project_summary
        }

    except Exception as e:
        try:
            if task_id is not None:
                update_subagent_task(task_id, "failed", completed=True, conn=conn)
        except Exception:
            pass

        try:
            save_log_metric(project_id, pr_id, "subagent_task", "task_failed", {
                "file": target_file,
                "error": str(e)
            }, conn=conn)
        except Exception:
            pass

        print("SUBAGENT TASK FAILED:", e)

        return {
            "file": target_file,
            "error": str(e),
            "source_type": "error",
            "has_paired_header": has_paired_header,
            "has_related_cpp": has_related_cpp
        }

    finally:
        conn.close()


def save_run_report(project_path, report_data):
    report_dir = os.path.join(project_path, "analysis_reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"run_report_{timestamp}.json")

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    return report_path


def make_bug_signature(file_path, bug):
    return (
        os.path.normcase(file_path),
        (bug.get("bug") or "").strip().lower(),
        bug.get("line_start"),
        bug.get("line_end"),
        (bug.get("finding_scope") or "local").strip().lower()
    )


def load_previous_report(project_path, current_report_path=None):
    report_dir = os.path.join(project_path, "analysis_reports")
    if not os.path.isdir(report_dir):
        return None

    files = [
        os.path.join(report_dir, name)
        for name in os.listdir(report_dir)
        if name.startswith("run_report_") and name.endswith(".json")
    ]

    files.sort()

    if current_report_path:
        current_abs = os.path.abspath(current_report_path)
        files = [f for f in files if os.path.abspath(f) != current_abs]

    if not files:
        return None

    previous_report_path = files[-1]

    with open(previous_report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    report_data["_report_path"] = previous_report_path
    return report_data


def is_comparable_bug(bug):
    if not bug:
        return False

    bug_name = (bug.get("bug") or "").strip().lower()
    line_start = bug.get("line_start")
    line_end = bug.get("line_end")

    if not bug_name:
        return False

    if line_start is None or line_end is None:
        return False

    return True


def compare_reports(previous_report, current_report):
    if not previous_report:
        return {
            "previous_report_path": None,
            "new_findings_count": 0,
            "resolved_findings_count": 0,
            "unchanged_findings_count": 0,
            "new_findings": [],
            "resolved_findings": [],
            "unchanged_findings": []
        }

    prev_map = {}
    curr_map = {}

    for item in previous_report.get("results", []):
        file_path = item.get("file")
        bugs = item.get("result", {}).get("bugs", [])

        for bug in bugs:
            if not is_comparable_bug(bug):
                continue

            sig = make_bug_signature(file_path, bug)
            prev_map[sig] = {
                "file": file_path,
                "bug": bug.get("bug"),
                "severity": bug.get("severity"),
                "line_start": bug.get("line_start"),
                "line_end": bug.get("line_end"),
                "finding_scope": bug.get("finding_scope")
            }

    for item in current_report.get("results", []):
        file_path = item.get("file")
        bugs = item.get("result", {}).get("bugs", [])

        for bug in bugs:
            if not is_comparable_bug(bug):
                continue

            sig = make_bug_signature(file_path, bug)
            curr_map[sig] = {
                "file": file_path,
                "bug": bug.get("bug"),
                "severity": bug.get("severity"),
                "line_start": bug.get("line_start"),
                "line_end": bug.get("line_end"),
                "finding_scope": bug.get("finding_scope")
            }

    prev_keys = set(prev_map.keys())
    curr_keys = set(curr_map.keys())

    new_keys = sorted(curr_keys - prev_keys)
    resolved_keys = sorted(prev_keys - curr_keys)
    unchanged_keys = sorted(curr_keys & prev_keys)

    return {
        "previous_report_path": previous_report.get("_report_path"),
        "new_findings_count": len(new_keys),
        "resolved_findings_count": len(resolved_keys),
        "unchanged_findings_count": len(unchanged_keys),
        "new_findings": [curr_map[k] for k in new_keys],
        "resolved_findings": [prev_map[k] for k in resolved_keys],
        "unchanged_findings": [curr_map[k] for k in unchanged_keys]
    }


def save_run_summary_txt(project_path, report_data):
    report_dir = os.path.join(project_path, "analysis_reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"run_summary_{timestamp}.txt")

    summary = report_data.get("summary", {})
    results = report_data.get("results", [])
    comparison = report_data.get("comparison", {})

    lines = []
    lines.append("LLM AGENT ANALYSIS SUMMARY")
    lines.append("=" * 40)
    lines.append(f"Project path: {report_data.get('project_path')}")
    lines.append(f"Generated at: {report_data.get('generated_at')}")
    lines.append("")

    lines.append("SUMMARY")
    lines.append("-" * 20)
    lines.append(f"Files analyzed: {summary.get('results_count', 0)}")
    lines.append(f"Total bugs: {summary.get('total_bugs', 0)}")
    lines.append(f"Local findings: {summary.get('local_findings_count', 0)}")
    lines.append(f"Interfile findings: {summary.get('interfile_findings_count', 0)}")
    lines.append(f"High severity: {summary.get('high_count', 0)}")
    lines.append(f"Medium severity: {summary.get('medium_count', 0)}")
    lines.append(f"Low severity: {summary.get('low_count', 0)}")
    lines.append(f"LLM results: {summary.get('llm_count', 0)}")
    lines.append(f"Fallback results: {summary.get('fallback_count', 0)}")
    lines.append(f"Fallback timeouts: {summary.get('fallback_timeout_count', 0)}")
    lines.append(f"LLM other rewrite errors: {summary.get('llm_other_error_count', 0)}")
    lines.append(f"LLM parse errors: {summary.get('llm_parse_error_count', 0)}")
    lines.append(f"Analysis mode: {summary.get('analysis_mode', '')}")
    lines.append(f"Max workers: {summary.get('max_workers', 0)}")
    lines.append("")

    lines.append("COMPARISON")
    lines.append("-" * 20)
    lines.append(f"Previous report: {comparison.get('previous_report_path')}")
    lines.append(f"New findings: {comparison.get('new_findings_count', 0)}")
    lines.append(f"Resolved findings: {comparison.get('resolved_findings_count', 0)}")
    lines.append(f"Unchanged findings: {comparison.get('unchanged_findings_count', 0)}")
    lines.append("")

    lines.append("FILES")
    lines.append("-" * 20)

    for item in results:
        file_path = item.get("file", "unknown")
        source_type = item.get("source_type", "unknown")
        parsed = item.get("result", {})
        bugs = parsed.get("bugs", [])

        lines.append(f"File: {file_path}")
        lines.append(f"Source type: {source_type}")
        lines.append(f"Bugs: {len(bugs)}")

        if not bugs:
            lines.append("  - no bugs")
        else:
            for bug in bugs:
                lines.append(
                    f"  - {bug.get('bug')} | severity={bug.get('severity')} | "
                    f"lines={bug.get('line_start')}-{bug.get('line_end')} | "
                    f"scope={bug.get('finding_scope', 'local')}"
                )

        lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path


def run_project(project_path, changed_files=None):
    total_start = time.time()
    conn = get_connection()

    try:
        project_name = os.path.basename(project_path.rstrip("\\/"))

        print("\n[0] CREATING PROJECT / PR...")
        project_id = get_or_create_project(
            name=project_name,
            repo_url=project_path,
            description="Local static analysis project",
            conn=conn
        )
        pr_id = create_pull_request(
            project_id=project_id,
            pr_number=1,
            author="local-user",
            source_branch="feature-test",
            target_branch="master",
            status="open",
            conn=conn
        )

        print("PROJECT ID:", project_id)
        print("PR ID:", pr_id)

        save_log_metric(project_id, pr_id, "orchestrator", "start", {
            "project_path": project_path,
            "changed_files": changed_files or []
        }, conn=conn)

        print("\n[1] SCANNING PROJECT...")
        scan_start = time.time()
        data = scan_project(project_path)
        scan_duration = int((time.time() - scan_start) * 1000)

        save_log_metric(project_id, pr_id, "scanner", "finish", {
            "cpp_count": len(data["cpp_files"]),
            "header_count": len(data["header_files"]),
            "file_count": len(data["files"])
        }, scan_duration, conn=conn)

        print("\n[2] BUILDING GRAPH...")
        graph_start = time.time()
        graph = build_graph(project_path)
        graph_duration = int((time.time() - graph_start) * 1000)

        save_project_context(
            project_id=project_id,
            context_type="dependency_graph",
            content="Project dependency graph",
            metadata=graph,
            conn=conn
        )

        save_log_metric(project_id, pr_id, "graph_builder", "finish", {
            "graph_nodes": len(graph)
        }, graph_duration, conn=conn)

        print("\n[3] LOADING PROJECT CONTEXT FROM JSON...")
        context_start = time.time()

        raw_json_text = load_raw_json_text(JSON_CONTEXT_PATH)
        raw_json_data = json.loads(raw_json_text)
        context_map = load_context_from_json(JSON_CONTEXT_PATH)

        context_duration = int((time.time() - context_start) * 1000)

        save_project_context(
            project_id=project_id,
            context_type="cpp_exported_context",
            content="C++ exported project context",
            metadata=raw_json_data,
            conn=conn
        )

        for file_entry in raw_json_data.get("files", []):
            diff_text = file_entry.get("diff", "")
            relative_path = file_entry.get("relative_path", "")
            file_path = file_entry.get("path", "")

            if diff_text.strip():
                save_project_context(
                    project_id=project_id,
                    context_type="git_diff_context",
                    content=f"Diff for {relative_path or file_path}",
                    metadata={
                        "file": file_path,
                        "relative_path": relative_path,
                        "diff": diff_text
                    },
                    conn=conn
                )

        save_log_metric(project_id, pr_id, "context_loader", "finish", {
            "context_nodes": len(context_map),
            "json_path": JSON_CONTEXT_PATH
        }, context_duration, conn=conn)

        analysis_files = data["cpp_files"]

        if changed_files:
            changed_cpp_files = normalize_changed_paths(project_path, changed_files, data["cpp_files"])
            changed_header_files = normalize_changed_headers(project_path, changed_files, data["header_files"])
            impacted_cpp_files = find_impacted_cpp_files_by_headers(
                changed_header_files,
                graph,
                data["cpp_files"]
            )

            analysis_files = build_analysis_file_list(
                changed_cpp_files,
                changed_header_files,
                impacted_cpp_files
            )

            print("\nCHANGED CPP FILES FOR ANALYSIS:")
            for f in changed_cpp_files:
                print(" -", f)

            print("\nCHANGED HEADER FILES:")
            for h in changed_header_files:
                print(" -", h)

            print("\nIMPACTED CPP FILES FROM HEADER CHANGES:")
            for f in impacted_cpp_files:
                print(" -", f)

            print("\nFINAL ANALYSIS FILES:")
            for f in analysis_files:
                print(" -", f)

        print("\n[4] RUNNING SUBAGENTS IN PARALLEL...\n")

        if not analysis_files:
            print("NO CPP FILES FOUND FOR ANALYSIS")
            save_log_metric(project_id, pr_id, "orchestrator", "finish", {
                "status": "no_cpp_files_for_analysis"
            }, int((time.time() - total_start) * 1000), conn=conn)
            return []

        results = []
        max_workers = min(2, len(analysis_files))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(process_cpp_file, project_id, pr_id, target_file, context_map, graph)
                for target_file in analysis_files
            ]

            for future in as_completed(futures):
                results.append(future.result())

        module_reports = run_module_subagents(results)
        module_report_path = save_module_report(project_path, module_reports)

        llm_count = 0
        fallback_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        total_bugs = 0

        local_findings_count = 0
        interfile_findings_count = 0

        paired_header_count = 0
        no_paired_header_count = 0
        related_cpp_count = 0
        no_related_cpp_count = 0
        fallback_timeout_count = 0
        llm_other_error_count = 0
        llm_parse_error_count = 0
        files_with_reverse_deps_count = 0

        for r in results:
            if r.get("reverse_dependencies_count", 0) > 0:
                files_with_reverse_deps_count += 1
            if r.get("has_paired_header"):
                paired_header_count += 1
            else:
                no_paired_header_count += 1

            if r.get("has_related_cpp"):
                related_cpp_count += 1
            else:
                no_related_cpp_count += 1

            parsed = r.get("result", {})
            bugs = parsed.get("bugs", [])

            total_bugs += len(bugs)

            llm_rewrite_used = bool(parsed.get("llm_rewrite_used"))
            fallback_used = bool(parsed.get("fallback_used"))
            fallback_reason = parsed.get("fallback_reason") or ""

            if llm_rewrite_used:
                llm_count += 1

            if fallback_used:
                fallback_count += 1

                lowered_reason = fallback_reason.lower()

                if "timed out" in lowered_reason:
                    fallback_timeout_count += 1
                elif fallback_reason == "llm_parse_error":
                    llm_parse_error_count += 1
                elif fallback_reason:
                    llm_other_error_count += 1

            for bug in bugs:
                scope = (bug.get("finding_scope") or "local").lower()
                sev = (bug.get("severity") or "unknown").lower()

                if scope == "interfile":
                    interfile_findings_count += 1
                else:
                    local_findings_count += 1

                if sev == "high":
                    high_count += 1
                elif sev == "medium":
                    medium_count += 1
                elif sev == "low":
                    low_count += 1

        total_duration = int((time.time() - total_start) * 1000)

        summary_payload = {
            "status": "success",
            "results_count": len(results),
            "total_bugs": total_bugs,
            "local_findings_count": local_findings_count,
            "interfile_findings_count": interfile_findings_count,
            "llm_count": llm_count,
            "fallback_count": fallback_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "paired_header_count": paired_header_count,
            "no_paired_header_count": no_paired_header_count,
            "related_cpp_count": related_cpp_count,
            "no_related_cpp_count": no_related_cpp_count,
            "fallback_timeout_count": fallback_timeout_count,
            "llm_other_error_count": llm_other_error_count,
            "llm_parse_error_count": llm_parse_error_count,
            "analysis_mode": "parallel" if max_workers > 1 else "sequential",
            "max_workers": max_workers,
            "graph_nodes": len(graph),
            "dependency_edges": sum(
                len(node.get("includes", []))
                for node in graph.values()
                if isinstance(node, dict)
            ),
            "files_with_reverse_deps_count": files_with_reverse_deps_count,
            "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
            "llm_model": os.getenv("LLM_MODEL", "deepseek-coder")
        }

        report_data = {
            "project_id": str(project_id),
            "pr_id": str(pr_id),
            "project_path": project_path,
            "generated_at": datetime.now().isoformat(),
            "changed_files": changed_files or [],
            "summary": summary_payload,
            "results": results,
            "module_reports": module_reports
        }

        previous_report = load_previous_report(project_path)
        comparison = compare_reports(previous_report, report_data)
        report_data["comparison"] = comparison
        final_report_path = save_final_report(project_path, report_data)

        report_path = save_run_report(project_path, report_data)
        summary_txt_path = save_run_summary_txt(project_path, report_data)
        html_report_path = save_html_report(project_path, report_data)

        save_log_metric(
            project_id,
            pr_id,
            "orchestrator",
            "finish",
            summary_payload,
            total_duration,
            conn=conn
        )

        save_project_context(
            project_id=project_id,
            context_type="run_summary",
            content="Run summary for project analysis",
            metadata=summary_payload,
            conn=conn
        )

        print("\n===== FINAL REPORT =====\n")
        for r in results:
            print(r)

        print("\n===== RUN SUMMARY =====\n")
        print("Files analyzed:", len(results))
        print("Total bugs:", total_bugs)
        print("Local findings:", local_findings_count)
        print("Interfile findings:", interfile_findings_count)
        print("LLM results:", llm_count)
        print("Fallback results:", fallback_count)
        print("High severity:", high_count)
        print("Medium severity:", medium_count)
        print("Low severity:", low_count)
        print("Files with paired header:", paired_header_count)
        print("Files without paired header:", no_paired_header_count)
        print("Files with related cpp:", related_cpp_count)
        print("Files without related cpp:", no_related_cpp_count)
        print("Fallback timeouts:", fallback_timeout_count)
        print("LLM other rewrite errors:", llm_other_error_count)
        print("LLM parse errors:", llm_parse_error_count)
        print("Run report saved to:", report_path)
        print("Run text summary saved to:", summary_txt_path)
        print("Module report saved to:", module_report_path)
        print("Final report saved to:", final_report_path)
        print("HTML report saved to:", html_report_path)
        print("New findings:", comparison["new_findings_count"])
        print("Resolved findings:", comparison["resolved_findings_count"])
        print("Unchanged findings:", comparison["unchanged_findings_count"])
        print("Analysis mode:", summary_payload["analysis_mode"])
        print("Max workers:", summary_payload["max_workers"])

        return results

    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
        changed = sys.argv[2:]
    else:
        path = input("Project path: ")
        changed = []

    run_project(path, changed)