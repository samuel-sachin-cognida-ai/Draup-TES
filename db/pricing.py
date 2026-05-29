"""Offering pricing storage and retrieval."""
from __future__ import annotations

import json
import logging

import psycopg2.extras

from db.connection import get_pg_connection

log = logging.getLogger("tes.db.pricing")

# Canonical confidence scores — use these constants everywhere
CONFIDENCE_CRAWLED       = 0.90   # price extracted from a real scraped page
CONFIDENCE_LLM_INFERRED  = 0.30   # price inferred from LLM training knowledge


def save_offering_pricing(row: dict) -> None:
    """
    Upsert one pricing row into offering_pricing.

    Conflict key: offering_id (one pricing record per sub-offering).
    On conflict: all pricing fields + fetched_at are refreshed.

    Required keys in row:
        offering_id (int), vendor (str), sub_offering (str),
        pricing_source (str), confidence_score (float)
    Optional keys:
        pricing_model, pricing_summary, input_cost, output_cost,
        tiers (list), notes, exact_text, source_url
    """
    conn = get_pg_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO offering_pricing
                (offering_id, vendor, sub_offering,
                 pricing_model, pricing_summary,
                 input_cost, output_cost, tiers, notes,
                 exact_text, source_url,
                 pricing_source, confidence_score)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (offering_id) DO UPDATE SET
                pricing_model    = EXCLUDED.pricing_model,
                pricing_summary  = EXCLUDED.pricing_summary,
                input_cost       = EXCLUDED.input_cost,
                output_cost      = EXCLUDED.output_cost,
                tiers            = EXCLUDED.tiers,
                notes            = EXCLUDED.notes,
                exact_text       = EXCLUDED.exact_text,
                source_url       = EXCLUDED.source_url,
                pricing_source   = EXCLUDED.pricing_source,
                confidence_score = EXCLUDED.confidence_score,
                fetched_at       = NOW();
            """,
            (
                row.get("offering_id"),
                row.get("vendor"),
                row.get("sub_offering"),
                row.get("pricing_model"),
                row.get("pricing_summary"),
                row.get("input_cost"),
                row.get("output_cost"),
                json.dumps(row["tiers"]) if row.get("tiers") else None,
                row.get("notes"),
                row.get("exact_text"),
                row.get("source_url"),
                row.get("pricing_source", "llm_inferred"),
                row.get("confidence_score", CONFIDENCE_LLM_INFERRED),
            ),
        )
        conn.commit()
        log.debug(
            "Pricing upserted: offering_id=%s  vendor=%r  sub_offering=%r  "
            "source=%s  confidence=%.2f",
            row.get("offering_id"),
            row.get("vendor"),
            row.get("sub_offering"),
            row.get("pricing_source"),
            row.get("confidence_score", CONFIDENCE_LLM_INFERRED),
        )
    except Exception as e:
        conn.rollback()
        log.error(
            "Failed to upsert pricing for offering_id=%s sub_offering=%r: %s",
            row.get("offering_id"), row.get("sub_offering"), e,
            exc_info=True,
        )
    finally:
        cur.close()
        conn.close()


def fetch_pricing_for_offering(offering_id: int) -> dict | None:
    """Return the pricing dict for a single offering_id, or None if not found."""
    conn = get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """SELECT pricing_model, pricing_summary, input_cost, output_cost,
                      tiers, notes, exact_text, source_url,
                      pricing_source, confidence_score, fetched_at
               FROM offering_pricing
               WHERE offering_id = %s;""",
            (offering_id,),
        )
        row = cur.fetchone()
        if row:
            d = dict(row)
            if d.get("fetched_at"):
                d["fetched_at"] = d["fetched_at"].isoformat()
            log.debug(
                "Pricing fetched: offering_id=%s  source=%s  model=%s",
                offering_id, d.get("pricing_source"), d.get("pricing_model"),
            )
            return d
        log.debug("No pricing found for offering_id=%s", offering_id)
        return None
    except Exception as e:
        log.error(
            "Failed to fetch pricing for offering_id=%s: %s", offering_id, e,
            exc_info=True,
        )
        return None
    finally:
        cur.close()
        conn.close()


def fetch_pricing_for_offerings(offering_ids: list[int]) -> dict[int, dict]:
    """
    Batch fetch pricing for multiple offering_ids.
    Returns {offering_id: pricing_dict} — missing IDs are simply absent.
    """
    if not offering_ids:
        return {}
    conn = get_pg_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """SELECT offering_id,
                      pricing_model, pricing_summary, input_cost, output_cost,
                      tiers, notes, exact_text, source_url,
                      pricing_source, confidence_score, fetched_at
               FROM offering_pricing
               WHERE offering_id = ANY(%s);""",
            (offering_ids,),
        )
        result: dict[int, dict] = {}
        for row in cur.fetchall():
            d   = dict(row)
            oid = d.pop("offering_id")
            if d.get("fetched_at"):
                d["fetched_at"] = d["fetched_at"].isoformat()
            result[oid] = d
        log.debug(
            "Batch pricing fetched: requested=%d  found=%d",
            len(offering_ids), len(result),
        )
        return result
    except Exception as e:
        log.error("Batch pricing fetch failed: %s", e, exc_info=True)
        return {}
    finally:
        cur.close()
        conn.close()
