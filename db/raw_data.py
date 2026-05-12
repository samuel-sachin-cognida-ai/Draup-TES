"""Raw scraped page storage."""
from __future__ import annotations

import hashlib

from db.connection import get_pg_connection


def save_raw_to_db(url: str, text: str, vendor_tag: str = "unknown") -> int | None:
    """
    Persist a scraped page. Returns the row id when the page is new or changed
    (caller should proceed with LLM extraction). Returns None when unchanged.
    """
    raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    conn = get_pg_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT id, raw_hash FROM raw_scraped_data WHERE url = %s;", (url,))
        existing = cur.fetchone()
        if existing:
            existing_id, existing_hash = existing
            if existing_hash == raw_hash:
                print(f"[SKIP] Page unchanged: {url}")
                return None
            cur.execute(
                "UPDATE raw_scraped_data SET text=%s, raw_hash=%s, vendor_tag=%s, scraped_at=NOW() "
                "WHERE url=%s RETURNING id;",
                (text, raw_hash, vendor_tag, url),
            )
            print(f"[UPDATE] Page changed, re-extracting: {url}")
        else:
            cur.execute(
                "INSERT INTO raw_scraped_data (url, vendor_tag, text, raw_hash) "
                "VALUES (%s, %s, %s, %s) RETURNING id;",
                (url, vendor_tag, text, raw_hash),
            )
        row_id = cur.fetchone()[0]
        conn.commit()
        return row_id
    except Exception as e:
        conn.rollback()
        print(f"[DB] Error saving raw data for {url}: {e}")
        return None
    finally:
        cur.close()
        conn.close()
