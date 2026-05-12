"""Database schema creation and migration (idempotent)."""
from __future__ import annotations

from db.connection import get_pg_connection


def init_db() -> None:
    """Create all tables and indexes. Safe to call repeatedly (idempotent)."""
    conn = get_pg_connection()
    cur  = conn.cursor()
    try:
        _create_raw_scraped_data(cur)
        _create_extracted_offerings(cur)
        _create_capability_records(cur)
        _create_task_tool_recommendations(cur)
        _create_capability_matches(cur)
        conn.commit()
        print("[DB] All tables ready.")
    finally:
        cur.close()
        conn.close()


def _create_raw_scraped_data(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS raw_scraped_data (
            id          SERIAL PRIMARY KEY,
            url         TEXT UNIQUE NOT NULL,
            vendor_tag  TEXT NOT NULL DEFAULT 'unknown',
            text        TEXT NOT NULL,
            scraped_at  TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("ALTER TABLE raw_scraped_data ADD COLUMN IF NOT EXISTS vendor_tag TEXT NOT NULL DEFAULT 'unknown';")
    cur.execute("ALTER TABLE raw_scraped_data ADD COLUMN IF NOT EXISTS raw_hash TEXT;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_vendor_tag ON raw_scraped_data(vendor_tag);")


def _create_extracted_offerings(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS extracted_offerings (
            id               SERIAL PRIMARY KEY,
            raw_data_id      INTEGER REFERENCES raw_scraped_data(id) ON DELETE CASCADE,
            url              TEXT NOT NULL,
            vendor           TEXT,
            category         TEXT,
            sub_category     TEXT,
            module_offering  TEXT,
            sub_offering     TEXT,
            capabilities     TEXT[],
            tasks_examples   TEXT[],
            content_hash     TEXT UNIQUE,
            source_evidence  TEXT,
            extracted_at     TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_extracted_offerings_content_hash
        ON extracted_offerings(content_hash);
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_extracted_vendor ON extracted_offerings(vendor);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_extracted_module ON extracted_offerings(module_offering);")
    cur.execute("ALTER TABLE extracted_offerings ADD COLUMN IF NOT EXISTS source_evidence TEXT;")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute("ALTER TABLE extracted_offerings ADD COLUMN IF NOT EXISTS embedding vector(384);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_offerings_embedding ON extracted_offerings USING hnsw (embedding vector_cosine_ops);")


def _create_capability_records(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS capability_records (
            id               SERIAL PRIMARY KEY,
            offering_id      INTEGER NOT NULL REFERENCES extracted_offerings(id) ON DELETE CASCADE,
            capability_text  TEXT NOT NULL,
            source_url       TEXT,
            source_location  TEXT,
            source_date      TIMESTAMP DEFAULT NOW(),
            exact_text       TEXT,
            created_at       TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cap_offering_id ON capability_records(offering_id);")


def _create_task_tool_recommendations(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_tool_recommendations (
            id                      SERIAL PRIMARY KEY,
            role_task_hash          TEXT NOT NULL,
            role                    TEXT NOT NULL,
            task                    TEXT NOT NULL,
            tool_id                 INTEGER REFERENCES extracted_offerings(id) ON DELETE SET NULL,
            vendor                  TEXT,
            module_offering         TEXT,
            sub_offering            TEXT,
            matched_capabilities    TEXT[],
            match_score             INTEGER DEFAULT 0,
            automation_percentage   INTEGER DEFAULT 0,
            helpfulness_score       INTEGER DEFAULT 0,
            rank_position           INTEGER DEFAULT 0,
            reasoning               TEXT,
            limitations             TEXT,
            automation_explanation  TEXT,
            created_at              TIMESTAMP DEFAULT NOW()
        );
    """)
    for col, definition in [
        ("automation_explanation", "TEXT"),
        ("automation_percentage",  "INTEGER DEFAULT 0"),
        ("helpfulness_score",      "INTEGER DEFAULT 0"),
        ("rank_position",          "INTEGER DEFAULT 0"),
        ("reasoning",              "TEXT"),
        ("limitations",            "TEXT"),
        ("match_score",            "INTEGER DEFAULT 0"),
    ]:
        cur.execute(
            f"ALTER TABLE task_tool_recommendations ADD COLUMN IF NOT EXISTS {col} {definition};"
        )
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_rec_role_task_hash
        ON task_tool_recommendations(role_task_hash);
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_role ON task_tool_recommendations(role);")
    cur.execute("ALTER TABLE task_tool_recommendations ADD COLUMN IF NOT EXISTS task_embedding vector(384);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_task_embedding ON task_tool_recommendations USING hnsw (task_embedding vector_cosine_ops);")


def _create_capability_matches(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS capability_matches (
            id                   SERIAL PRIMARY KEY,
            recommendation_id    INTEGER NOT NULL REFERENCES task_tool_recommendations(id) ON DELETE CASCADE,
            capability_record_id INTEGER REFERENCES capability_records(id) ON DELETE SET NULL,
            capability_text      TEXT NOT NULL,
            automatability_score INTEGER DEFAULT 0,
            reason               TEXT,
            limitations          TEXT,
            created_at           TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cap_match_rec_id ON capability_matches(recommendation_id);")
