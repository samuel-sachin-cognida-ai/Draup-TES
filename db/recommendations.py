"""Task tool recommendation storage and retrieval."""
from __future__ import annotations

import uuid

import psycopg2.extras

from db.connection import get_pg_connection


def fetch_cached_by_embedding(
    task_embedding: list[float],
    threshold: float = 0.12,
) -> list[dict] | None:
    """Fuzzy cache lookup by embedding similarity. Returns cached results or None."""
    conn = get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """SELECT role, task, MIN(task_embedding <=> %s::vector) AS distance
               FROM task_tool_recommendations
               WHERE task_embedding IS NOT NULL
               GROUP BY role, task
               ORDER BY distance ASC
               LIMIT 1;""",
            (task_embedding,),
        )
        row = cur.fetchone()
        if not row or row["distance"] >= threshold:
            return None

        print(
            f"[VECTOR] Semantic cache hit (distance={row['distance']:.4f}, "
            f"role={row['role']!r}, task={row['task']!r})"
        )
        cur.execute(
            """SELECT r.*, eo.source_evidence, eo.url as offering_url
               FROM task_tool_recommendations r
               LEFT JOIN extracted_offerings eo ON eo.id = r.tool_id
               WHERE r.role = %s AND r.task = %s
               ORDER BY r.rank_position ASC, r.id ASC;""",
            (row["role"], row["task"]),
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return None

        real_rows = [r for r in rows if r.get("vendor") is not None]
        rec_ids   = [r["id"] for r in real_rows]
        cap_matches = _fetch_capability_matches_batch(cur, rec_ids)
        for r in real_rows:
            r["capability_details"] = cap_matches.get(r["id"], [])
        return real_rows

    except Exception as e:
        print(f"[VECTOR] Embedding cache lookup error: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def _fetch_capability_matches_batch(cur, recommendation_ids: list[int]) -> dict[int, list[dict]]:
    if not recommendation_ids:
        return {}
    cur.execute(
        """SELECT cm.recommendation_id, cm.capability_record_id, cm.capability_text,
                  cm.automatability_score, cm.reason, cm.limitations,
                  cr.source_url, cr.source_location, cr.source_date, cr.exact_text
           FROM capability_matches cm
           LEFT JOIN capability_records cr ON cr.id = cm.capability_record_id
           WHERE cm.recommendation_id = ANY(%s)
           ORDER BY cm.recommendation_id, cm.id;""",
        (recommendation_ids,),
    )
    result: dict[int, list[dict]] = {}
    for row in cur.fetchall():
        d   = dict(row)
        rid = d.pop("recommendation_id")
        result.setdefault(rid, []).append(d)
    return result


def save_task_recommendations(
    role: str,
    task: str,
    tools: list[dict],
    task_embedding: list[float] | None = None,
) -> None:
    conn = get_pg_connection()
    cur  = conn.cursor()
    try:
        raw_ids = {t.get("tool_id") for t in tools if t.get("tool_id") is not None}
        valid_tool_ids: set = set()
        if raw_ids:
            cur.execute(
                "SELECT id FROM extracted_offerings WHERE id = ANY(%s);",
                (list(raw_ids),),
            )
            valid_tool_ids = {row[0] for row in cur.fetchall()}
            bad_ids = raw_ids - valid_tool_ids
            if bad_ids:
                print(
                    f"[DB] WARNING – {len(bad_ids)} tool_id(s) not found in "
                    f"extracted_offerings and will be stored as NULL: {bad_ids}"
                )

        rows_to_insert = tools if tools else [{}]

        for t in rows_to_insert:
            caps = t.get("matched_capabilities") or []
            if not isinstance(caps, list):
                caps = list(caps) if caps else []
            caps = [str(c) for c in caps if c is not None]

            raw_tool_id  = t.get("tool_id")
            safe_tool_id = raw_tool_id if raw_tool_id in valid_tool_ids else None

            cur.execute(
                """INSERT INTO task_tool_recommendations
                       (role_task_hash, role, task, tool_id,
                        vendor, module_offering, sub_offering,
                        matched_capabilities,
                        automation_percentage, rank_position,
                        reasoning, limitations, automation_explanation,
                        task_embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id;""",
                (
                    str(uuid.uuid4()), role, task,
                    safe_tool_id,
                    t.get("vendor"),
                    t.get("module_offering"),
                    t.get("sub_offering"),
                    caps,
                    t.get("automation_percentage", 0),
                    t.get("rank_position", 0),
                    t.get("reasoning"),
                    t.get("limitations"),
                    t.get("automation_explanation"),
                    task_embedding,
                ),
            )
            rec_row = cur.fetchone()
            if rec_row is None:
                continue
            rec_id = rec_row[0]

            for cd in (t.get("capability_details") or []):
                if not isinstance(cd, dict):
                    continue
                cap_text = (cd.get("capability_text") or cd.get("text") or "").strip()
                if not cap_text:
                    continue

                cap_record_id = cd.get("capability_record_id") or None
                if cap_record_id is None and safe_tool_id:
                    cur.execute(
                        """SELECT id FROM capability_records
                           WHERE offering_id = %s AND capability_text = %s
                           LIMIT 1;""",
                        (safe_tool_id, cap_text),
                    )
                    cr_row = cur.fetchone()
                    if cr_row:
                        cap_record_id = cr_row[0]

                cur.execute(
                    """INSERT INTO capability_matches
                           (recommendation_id, capability_record_id, capability_text,
                            automatability_score, reason, limitations)
                       VALUES (%s, %s, %s, %s, %s, %s);""",
                    (
                        rec_id,
                        cap_record_id,
                        cap_text,
                        cd.get("automatability_score", 0),
                        cd.get("reason"),
                        cd.get("limitations"),
                    ),
                )

        conn.commit()
        print(f"[DB] Saved {len(rows_to_insert)} recommendation(s) for role={role!r} task={task!r}")
    except Exception as e:
        conn.rollback()
        print(f"[DB] Error saving recommendations: {e}")
        raise
    finally:
        cur.close()
        conn.close()
