"""Database schema creation and migration (idempotent)."""
from __future__ import annotations

import logging

from db.connection import get_pg_connection

log = logging.getLogger("tes.db.schema")


def init_db() -> None:
    """Create all tables and indexes. Safe to call repeatedly (idempotent)."""
    conn = get_pg_connection()
    cur  = conn.cursor()
    try:
        log.debug("Running DDL: _create_raw_scraped_data")
        _create_raw_scraped_data(cur)

        log.debug("Running DDL: _create_extracted_offerings")
        _create_extracted_offerings(cur)

        log.debug("Running DDL: _create_capability_records")
        _create_capability_records(cur)

        log.debug("Running DDL: _create_task_tool_recommendations")
        _create_task_tool_recommendations(cur)

        log.debug("Running DDL: _create_capability_matches")
        _create_capability_matches(cur)

        log.debug("Running DDL: _create_offering_pricing")
        _create_offering_pricing(cur)

        conn.commit()
        log.info("All tables and indexes are ready.")
    except Exception:
        log.critical("DDL step failed; database schema may be incomplete.", exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


def _create_raw_scraped_data(cur) -> None:
    log.debug("CREATE TABLE IF NOT EXISTS raw_scraped_data")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS raw_scraped_data (
            id          SERIAL PRIMARY KEY,
            url         TEXT UNIQUE NOT NULL,
            vendor_tag  TEXT NOT NULL DEFAULT 'unknown',
            text        TEXT NOT NULL,
            scraped_at  TIMESTAMP DEFAULT NOW()
        );
    """)
    log.debug("ALTER TABLE raw_scraped_data ADD COLUMN IF NOT EXISTS vendor_tag")
    cur.execute("ALTER TABLE raw_scraped_data ADD COLUMN IF NOT EXISTS vendor_tag TEXT NOT NULL DEFAULT 'unknown';")
    log.debug("ALTER TABLE raw_scraped_data ADD COLUMN IF NOT EXISTS raw_hash")
    cur.execute("ALTER TABLE raw_scraped_data ADD COLUMN IF NOT EXISTS raw_hash TEXT;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_vendor_tag ON raw_scraped_data(vendor_tag);")


def _create_extracted_offerings(cur) -> None:
    log.debug("CREATE TABLE IF NOT EXISTS extracted_offerings")
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
    log.debug("ALTER TABLE extracted_offerings – adding optional columns and vector extension")
    cur.execute("ALTER TABLE extracted_offerings ADD COLUMN IF NOT EXISTS source_evidence TEXT;")
    cur.execute("ALTER TABLE extracted_offerings ADD COLUMN IF NOT EXISTS industry TEXT DEFAULT 'general';")
    cur.execute("ALTER TABLE extracted_offerings ADD COLUMN IF NOT EXISTS evidence_grade CHAR(1) DEFAULT 'C';")
    cur.execute("ALTER TABLE extracted_offerings ADD COLUMN IF NOT EXISTS evidence_weight FLOAT DEFAULT 0.50;")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute("ALTER TABLE extracted_offerings ADD COLUMN IF NOT EXISTS embedding vector(384);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_offerings_embedding ON extracted_offerings USING hnsw (embedding vector_cosine_ops);")


def _create_capability_records(cur) -> None:
    log.debug("CREATE TABLE IF NOT EXISTS capability_records")
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
    log.debug("CREATE TABLE IF NOT EXISTS task_tool_recommendations")
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
    log.debug("ALTER TABLE task_tool_recommendations – backfilling optional columns")
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
    cur.execute("ALTER TABLE task_tool_recommendations ADD COLUMN IF NOT EXISTS task_coverage_pct FLOAT;")
    cur.execute("ALTER TABLE task_tool_recommendations ADD COLUMN IF NOT EXISTS tes_score FLOAT;")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_rec_role_task_hash
        ON task_tool_recommendations(role_task_hash);
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_role ON task_tool_recommendations(role);")
    log.debug("ALTER TABLE task_tool_recommendations ADD COLUMN IF NOT EXISTS task_embedding")
    cur.execute("ALTER TABLE task_tool_recommendations ADD COLUMN IF NOT EXISTS task_embedding vector(384);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rec_task_embedding ON task_tool_recommendations USING hnsw (task_embedding vector_cosine_ops);")


def _create_capability_matches(cur) -> None:
    log.debug("CREATE TABLE IF NOT EXISTS capability_matches")
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


def _create_offering_pricing(cur) -> None:
    """
    Pricing data linked to extracted_offerings.
    pricing_source : 'crawled'      — extracted from a real scraped pricing page
                     'llm_inferred' — estimated by LLM at query time (no page)
    confidence_score: 0.90 for crawled, 0.30 for llm_inferred
    exact_text      : verbatim excerpt from the page proving the price (crawled only)
    """
    log.debug("CREATE TABLE IF NOT EXISTS offering_pricing")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS offering_pricing (
            id               SERIAL PRIMARY KEY,
            offering_id      INTEGER NOT NULL
                             REFERENCES extracted_offerings(id) ON DELETE CASCADE,
            vendor           TEXT NOT NULL,
            sub_offering     TEXT NOT NULL,
            pricing_model    TEXT,
            pricing_summary  TEXT,
            input_cost       TEXT,
            output_cost      TEXT,
            tiers            JSONB,
            notes            TEXT,
            exact_text       TEXT,
            source_url       TEXT,
            pricing_source   TEXT NOT NULL DEFAULT 'llm_inferred',
            confidence_score FLOAT NOT NULL DEFAULT 0.30,
            fetched_at       TIMESTAMP DEFAULT NOW(),
            UNIQUE (offering_id)
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_op_offering_id ON offering_pricing(offering_id);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_op_vendor ON offering_pricing(vendor);"
    )
    log.debug("offering_pricing table and indexes ensured.")
