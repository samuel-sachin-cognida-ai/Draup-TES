-- ============================================================
-- Healthcare AI Tools Database Schema v2
-- Run once to initialise (or re-run safely – all idempotent).
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. raw_scraped_data
CREATE TABLE IF NOT EXISTS raw_scraped_data (
    id          SERIAL PRIMARY KEY,
    url         TEXT UNIQUE NOT NULL,
    vendor_tag  TEXT NOT NULL DEFAULT 'unknown',
    text        TEXT NOT NULL,
    raw_hash    TEXT,
    scraped_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_raw_vendor_tag ON raw_scraped_data(vendor_tag);

-- 2. extracted_offerings
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
    embedding        vector(384),
    extracted_at     TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_extracted_offerings_content_hash ON extracted_offerings(content_hash);
CREATE INDEX IF NOT EXISTS idx_extracted_vendor ON extracted_offerings(vendor);
CREATE INDEX IF NOT EXISTS idx_extracted_module ON extracted_offerings(module_offering);
CREATE INDEX IF NOT EXISTS idx_offerings_embedding ON extracted_offerings USING hnsw (embedding vector_cosine_ops);

-- 3. capability_records — each capability is a separate row with full source provenance
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
CREATE INDEX IF NOT EXISTS idx_cap_offering_id ON capability_records(offering_id);

-- 4. task_tool_recommendations
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
    task_embedding          vector(384),
    created_at              TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rec_role_task_hash ON task_tool_recommendations(role_task_hash);
CREATE INDEX IF NOT EXISTS idx_rec_role ON task_tool_recommendations(role);
CREATE INDEX IF NOT EXISTS idx_rec_task_embedding ON task_tool_recommendations USING hnsw (task_embedding vector_cosine_ops);

-- 5. capability_matches — per-capability details for each recommendation
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
CREATE INDEX IF NOT EXISTS idx_cap_match_rec_id ON capability_matches(recommendation_id);
