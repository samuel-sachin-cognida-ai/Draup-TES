"""FastAPI route handlers."""
from __future__ import annotations

import psycopg2.extras
from fastapi import HTTPException, Query

import db
from api.app import app
from api.models import RecommendRequest
from api.processing import process_single_task, rows_to_tool_list
from api.roles_data import ROLES_AND_TASKS


@app.post("/recommend-tools")
def recommend_tools(req: RecommendRequest):
    """
    Accept a role + list of tasks (+ optional vendor filter).

    Each task is evaluated independently:
      1. Check cache → return if found
      2. Call LLM to match that task against extracted_offerings
      3. Store result for future cache hits
      4. Move to next task
    """
    role   = req.role.strip()
    tasks  = [t.strip() for t in req.tasks if t.strip()]
    vendor = req.vendor.strip() if req.vendor else None

    if not tasks:
        raise HTTPException(status_code=400, detail="At least one non-empty task is required.")

    print(f"\n{'=' * 60}")
    print(f"[API] role={role!r}  tasks={len(tasks)}  vendor={vendor!r}")
    print(f"{'=' * 60}")

    all_recommendations: list[dict] = []
    cached_count = llm_count = 0

    for i, task in enumerate(tasks, 1):
        print(f"\n--- Task {i}/{len(tasks)} ---")
        try:
            result = process_single_task(role, task, vendor)
        except Exception as e:
            print(f"[API] Error processing task {i}: {e}")
            result = {"task": task, "cached": False, "recommended_tools": [], "error": str(e)}

        if result.get("cached"):
            cached_count += 1
        else:
            llm_count += 1

        all_recommendations.append(result)

    print(f"\n{'=' * 60}")
    print(f"[API] Done. cached={cached_count}  llm_calls={llm_count}")
    print(f"{'=' * 60}\n")

    return {
        "role":             role,
        "vendor_filter":    vendor,
        "total_tasks":      len(tasks),
        "tasks_from_cache": cached_count,
        "tasks_from_llm":   llm_count,
        "tasks":            all_recommendations,
    }


@app.get("/health")
def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/stats")
def get_stats():
    """Return total capability_records count and distinct cached (role, task) count."""
    conn = db.get_pg_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM capability_records;")
        capabilities = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT role || '||' || task) FROM task_tool_recommendations;")
        cached = cur.fetchone()[0]
        return {"capabilities": capabilities, "cached": cached}
    finally:
        cur.close()
        conn.close()


@app.get("/roles")
def list_roles():
    """Return all available roles from the static reference list."""
    static_roles = sorted(ROLES_AND_TASKS.keys())
    return {"total": len(static_roles), "roles": static_roles}


@app.get("/tasks-for-role")
def tasks_for_role(role: str = Query(..., description="Role name")):
    """Return the list of tasks for a given role."""
    tasks = ROLES_AND_TASKS.get(role)

    if tasks is None:
        role_lower = role.lower()
        for key, value in ROLES_AND_TASKS.items():
            if key.lower() == role_lower:
                tasks = value
                break

    if tasks is None:
        try:
            conn = db.get_pg_connection()
            cur  = conn.cursor()
            try:
                cur.execute(
                    """SELECT DISTINCT task FROM task_tool_recommendations
                       WHERE role ILIKE %s ORDER BY task;""",
                    (role,),
                )
                tasks = [r[0] for r in cur.fetchall()]
            finally:
                cur.close()
                conn.close()
        except Exception as _e:
            print(f"[TASKS] DB fetch skipped (role not in static data): {_e}")
            tasks = []

    if not tasks:
        raise HTTPException(status_code=404, detail=f"No tasks found for role: {role!r}")

    return {"role": role, "total": len(tasks), "tasks": tasks}


@app.get("/offerings")
def list_offerings(
    vendor: str | None = Query(None, description="Filter by vendor: 'Anthropic' or 'OpenAI'"),
    module: str | None = Query(None, description="Filter by module_offering"),
):
    """List all extracted offerings. Optionally filter by vendor or module_offering."""
    conn = db.get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        conditions, params = [], []
        if vendor:
            conditions.append("vendor ILIKE %s")
            params.append(vendor)
        if module:
            conditions.append("module_offering ILIKE %s")
            params.append(module)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(
            f"""SELECT id, vendor, category, sub_category, module_offering,
                       sub_offering, capabilities, tasks_examples, url, extracted_at,
                       source_evidence
               FROM extracted_offerings
               {where}
               ORDER BY vendor, module_offering, sub_offering;""",
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]
        return {"total": len(rows), "offerings": rows}
    finally:
        cur.close()
        conn.close()


@app.get("/cached-recommendations")
def list_cached_recommendations(
    role: str | None = Query(None, description="Filter by role"),
):
    """Return all cached (role, task) recommendations, optionally filtered by role."""
    conn = db.get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if role:
            cur.execute(
                """SELECT DISTINCT role, task, created_at
                   FROM task_tool_recommendations
                   WHERE role ILIKE %s
                   ORDER BY role, task;""",
                (f"%{role}%",),
            )
        else:
            cur.execute(
                """SELECT DISTINCT role, task, created_at
                   FROM task_tool_recommendations
                   ORDER BY role, task;"""
            )
        rows = [dict(r) for r in cur.fetchall()]
        return {"total": len(rows), "cached_pairs": rows}
    finally:
        cur.close()
        conn.close()
