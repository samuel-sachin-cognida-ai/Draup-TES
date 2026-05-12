"""Sentence-transformer embedding helpers for semantic similarity."""
from __future__ import annotations

from db.connection import get_pg_connection
from db.text_utils import normalize_text

_embedding_model = None


def _get_embedding_model():
    """Lazy-load the embedding model (downloads ~90 MB once, then fully local)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[VECTOR] Embedding model loaded (384 dims)")
    return _embedding_model


def get_offering_embedding(item: dict) -> list[float]:
    """384-dim embedding of vendor + sub_offering + all capabilities."""
    text = (
        f"{normalize_text(item.get('vendor') or '')} "
        f"{normalize_text(item.get('sub_offering') or '')} "
        f"{' '.join(normalize_text(c) for c in (item.get('capabilities') or []))}"
    )
    return _get_embedding_model().encode(text).tolist()


def get_task_embedding(role: str, task: str) -> list[float]:
    """384-dim embedding of role + task, used as a semantic cache key."""
    return _get_embedding_model().encode(
        f"{role.strip().lower()} {task.strip().lower()}"
    ).tolist()


def find_similar_offering(embedding: list[float], threshold: float = 0.08) -> int | None:
    """Return an existing offering id if cosine distance < threshold (~92% similarity)."""
    conn = get_pg_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT id FROM extracted_offerings
               WHERE embedding <=> %s::vector < %s
               ORDER BY embedding <=> %s::vector
               LIMIT 1;""",
            (embedding, threshold, embedding),
        )
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"[VECTOR] Similarity search error: {e}")
        return None
    finally:
        cur.close()
        conn.close()
