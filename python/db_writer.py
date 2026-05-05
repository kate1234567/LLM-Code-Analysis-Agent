import uuid
import json
import psycopg2
from config_loader import load_config

config = load_config()

DB_CONFIG = {
    "dbname": config["db_name"],
    "user": config["db_user"],
    "password": config["db_password"],
    "host": config["db_host"],
    "port": config["db_port"]
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def ensure_jsonable(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def get_or_create_project(name, repo_url="", description="", conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM projects
        WHERE name = %s
        LIMIT 1
    """, (name,))
    row = cur.fetchone()

    if row:
        project_id = row[0]
    else:
        project_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO projects (id, name, repo_url, description)
            VALUES (%s, %s, %s, %s)
        """, (project_id, name, repo_url, description))
        conn.commit()

    cur.close()
    if own_conn:
        conn.close()

    return project_id

def load_last_file_hash(project_id, file_path, conn):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT metadata->>'file_hash'
                FROM projectcontext
                WHERE project_id = %s
                  AND context_type = 'file_hash_cache'
                  AND metadata->>'file' = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (str(project_id), file_path))

            row = cur.fetchone()

            if row and row[0]:
                return row[0]

            return None

    except Exception as e:
        print("LOAD HASH ERROR:", str(e))
        return None

def save_file_analysis_cache(project_id, file_path, file_hash, result_data, conn):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analysis_cache (
                    project_id,
                    file_path,
                    cache_type,
                    content,
                    metadata,
                    content_hash
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (
                    project_id,
                    file_path,
                    cache_type,
                    content_hash
                )
                DO UPDATE SET
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """, (
                str(project_id),
                file_path,
                "file_analysis",
                f"Analysis cache for {file_path}",
                json.dumps(result_data),
                file_hash
            ))

        conn.commit()

    except Exception as e:
        print("SAVE ANALYSIS CACHE ERROR:", str(e))
        conn.rollback()

def load_file_analysis_cache(project_id, file_path, file_hash, conn):
    try:
        with conn.cursor() as cur:
            print("CACHE SEARCH:")
            print("PROJECT ID:", project_id)
            print("FILE PATH:", file_path)
            print("FILE HASH:", file_hash)

            cur.execute("""
                SELECT metadata
                FROM analysis_cache
                WHERE project_id = %s
                  AND file_path = %s
                  AND cache_type = %s
                  AND content_hash = %s
                LIMIT 1
            """, (
                str(project_id),
                file_path,
                "file_analysis",
                file_hash
            ))

            row = cur.fetchone()

            print("CACHE ROW:", row)

            if not row:
                return None

            return row[0]

    except Exception as e:
        print("LOAD ANALYSIS CACHE ERROR:", str(e))
        return None

def create_pull_request(project_id, pr_number, author, source_branch, target_branch, status="open", conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM pullrequests
        WHERE project_id = %s
          AND pr_number = %s
          AND source_branch = %s
          AND target_branch = %s
        LIMIT 1
    """, (
        project_id,
        pr_number,
        source_branch,
        target_branch
    ))

    row = cur.fetchone()

    if row:
        pr_id = row[0]
    else:
        pr_id = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO pullrequests (
                id, project_id, pr_number, author, source_branch, target_branch, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            pr_id,
            project_id,
            pr_number,
            author,
            source_branch,
            target_branch,
            status
        ))

        conn.commit()

    cur.close()
    if own_conn:
        conn.close()

    return pr_id


def save_project_context(project_id, context_type, content, metadata=None, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    context_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO projectcontext (
            id, project_id, context_type, content, metadata
        )
        VALUES (%s, %s, %s, %s, %s::jsonb)
    """, (
        context_id,
        project_id,
        context_type,
        content,
        ensure_jsonable(metadata)
    ))

    conn.commit()
    cur.close()
    if own_conn:
        conn.close()

    return context_id


def save_finding(pr_id, file_path, bug_data, source_type="unknown", conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    finding_type = bug_data.get("bug", "unknown")
    description = bug_data.get("description") or bug_data.get("cause", "")
    severity = bug_data.get("severity", "unknown")
    line_start = bug_data.get("line_start")
    line_end = bug_data.get("line_end")
    finding_scope = bug_data.get("finding_scope", "local")

    cur.execute("""
        SELECT id
        FROM findings
        WHERE pr_id = %s
          AND file_path = %s
          AND finding_type = %s
          AND COALESCE(line_start, -1) = COALESCE(%s, -1)
          AND COALESCE(line_end, -1) = COALESCE(%s, -1)
          AND severity = %s
          AND source_type = %s
          AND finding_scope = %s
        LIMIT 1
    """, (
        pr_id,
        file_path,
        finding_type,
        line_start,
        line_end,
        severity,
        source_type,
        finding_scope
    ))

    existing = cur.fetchone()
    if existing:
        finding_id = existing[0]
        cur.close()
        if own_conn:
            conn.close()
        return finding_id

    finding_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO findings (
            id,
            pr_id,
            finding_type,
            file_path,
            line_start,
            line_end,
            description,
            severity,
            status,
            source_type,
            finding_scope
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        finding_id,
        pr_id,
        finding_type,
        file_path,
        line_start,
        line_end,
        description,
        severity,
        "new",
        source_type,
        finding_scope
    ))

    conn.commit()
    cur.close()
    if own_conn:
        conn.close()

    return finding_id


def save_recommendation(finding_id, bug_data, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    recommendation_text = bug_data.get("fix", "")

    cur.execute("""
        SELECT id
        FROM recommendations
        WHERE finding_id = %s
          AND recommendation_text = %s
        LIMIT 1
    """, (
        finding_id,
        recommendation_text
    ))

    existing = cur.fetchone()
    if existing:
        recommendation_id = existing[0]
        cur.close()
        if own_conn:
            conn.close()
        return recommendation_id

    recommendation_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO recommendations (
            id, finding_id, recommendation_text, model_version, relevance_score
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        recommendation_id,
        finding_id,
        recommendation_text,
        "fallback-or-llm",
        None
    ))

    conn.commit()
    cur.close()
    if own_conn:
        conn.close()

    return recommendation_id


def save_log_metric(project_id, pr_id, component, event_type, event_data=None, duration_ms=None, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    log_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO logs_metrics (
            id, project_id, pr_id, component, event_type, event_data, duration_ms
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
    """, (
        log_id,
        project_id,
        pr_id,
        component,
        event_type,
        ensure_jsonable(event_data),
        duration_ms
    ))

    conn.commit()
    cur.close()
    if own_conn:
        conn.close()

    return log_id


def create_subagent_task(pr_id, target_path, status="running", conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    task_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO subagenttask (
            id, pr_id, target_path, status, created_at
        )
        VALUES (%s, %s, %s, %s, NOW())
    """, (
        task_id,
        pr_id,
        target_path,
        status
    ))

    conn.commit()
    cur.close()
    if own_conn:
        conn.close()

    return task_id


def update_subagent_task(task_id, status, completed=False, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    if completed:
        cur.execute("""
            UPDATE subagenttask
            SET status = %s, completed_at = NOW()
            WHERE id = %s
        """, (status, task_id))
    else:
        cur.execute("""
            UPDATE subagenttask
            SET status = %s
            WHERE id = %s
        """, (status, task_id))

    conn.commit()
    cur.close()
    if own_conn:
        conn.close()

def load_recent_findings_for_file(project_id, file_path, limit=10, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT
            f.finding_type,
            f.description,
            f.severity,
            f.source_type,
            f.finding_scope
        FROM findings f
        JOIN pullrequests pr ON f.pr_id = pr.id
        WHERE pr.project_id = %s
          AND f.file_path = %s
        ORDER BY
            f.finding_type,
            f.description,
            f.severity,
            f.source_type,
            f.finding_scope
        LIMIT %s
    """, (project_id, file_path, limit))

    rows = cur.fetchall()
    cur.close()

    if own_conn:
        conn.close()

    result = []
    for row in rows:
        result.append({
            "finding_type": row[0],
            "description": row[1],
            "severity": row[2],
            "source_type": row[3],
            "finding_scope": row[4]
        })

    return result