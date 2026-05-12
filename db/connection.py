"""PostgreSQL connection helpers."""
from __future__ import annotations

import os

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

PG_HOST     = os.getenv("PG_HOST", "localhost")
PG_PORT     = os.getenv("PG_PORT", "5432")
PG_DBNAME   = os.getenv("PG_DBNAME", "healthcare_crawler")
PG_USER     = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")


def _ensure_database_exists() -> None:
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        dbname="postgres", user=PG_USER, password=PG_PASSWORD,
        connect_timeout=5,
    )
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (PG_DBNAME,))
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(PG_DBNAME)))
            print(f"[DB] Created database '{PG_DBNAME}'.")
    finally:
        cur.close()
        conn.close()


def get_pg_connection():
    try:
        return psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            dbname=PG_DBNAME, user=PG_USER, password=PG_PASSWORD,
            connect_timeout=5,
        )
    except psycopg2.OperationalError as e:
        if "does not exist" not in str(e):
            raise
        print(f"[DB] Database '{PG_DBNAME}' not found – creating it…")
        _ensure_database_exists()
        return psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            dbname=PG_DBNAME, user=PG_USER, password=PG_PASSWORD,
        )
