"""Raw scraped page storage."""
from __future__ import annotations

import hashlib
import logging

from db.connection import get_pg_connection

log = logging.getLogger("tes.db.raw")


def save_raw_to_db(url: str, text: str, vendor_tag: str = "unknown") -> int | None:
    """
    Persist a scraped page. Returns the row id when the page is new or changed
    (caller should proceed with LLM extraction). Returns None when unchanged.
    """
    raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    log.debug("Computed SHA-256 hash %s for URL: %s", raw_hash[:12], url)
    conn = get_pg_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT id, raw_hash FROM raw_scraped_data WHERE url = %s;", (url,))
        existing = cur.fetchone()
        if existing:
            existing_id, existing_hash = existing
            log.debug(
                "URL already in DB (id=%s). Comparing hashes: stored=%s… incoming=%s…",
                existing_id, existing_hash[:12], raw_hash[:12],
            )
            if existing_hash == raw_hash:
                log.debug("Page unchanged, skipping re-extraction: %s", url)
                return None
            cur.execute(
                "UPDATE raw_scraped_data SET text=%s, raw_hash=%s, vendor_tag=%s, scraped_at=NOW() "
                "WHERE url=%s RETURNING id;",
                (text, raw_hash, vendor_tag, url),
            )
            log.info("Page content changed, updated row and queued re-extraction: %s", url)
        else:
            cur.execute(
                "INSERT INTO raw_scraped_data (url, vendor_tag, text, raw_hash) "
                "VALUES (%s, %s, %s, %s) RETURNING id;",
                (url, vendor_tag, text, raw_hash),
            )
            log.debug("Inserted new raw_scraped_data row for URL: %s", url)
        row_id = cur.fetchone()[0]
        conn.commit()
        log.debug("Committed raw data row id=%s for URL: %s", row_id, url)
        return row_id
    except Exception as e:
        conn.rollback()
        log.error(
            "Failed to save raw data for %s; transaction rolled back.",
            url,
            exc_info=True,
        )
        return None
    finally:
        cur.close()
        conn.close()
