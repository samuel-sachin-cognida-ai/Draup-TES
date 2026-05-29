"""PostgreSQL connection helpers."""
from __future__ import annotations

import logging
import os

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("tes.db.connection")

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
            log.info("Auto-created database '%s'.", PG_DBNAME)
    finally:
        cur.close()
        conn.close()


def get_pg_connection():
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            dbname=PG_DBNAME, user=PG_USER, password=PG_PASSWORD,
            connect_timeout=5,
        )
        log.debug(
            "Connection opened to %s:%s/%s as user '%s'.",
            PG_HOST, PG_PORT, PG_DBNAME, PG_USER,
        )
        return conn
    except psycopg2.OperationalError as e:
        if "does not exist" not in str(e):
            log.critical(
                "Cannot connect to PostgreSQL at %s:%s (db='%s', user='%s'). "
                "Check PG_HOST, PG_PORT, PG_DBNAME, PG_USER and PG_PASSWORD env vars.",
                PG_HOST, PG_PORT, PG_DBNAME, PG_USER,
                exc_info=True,
            )
            raise
        log.info(
            "Database '%s' not found – attempting to auto-create it.",
            PG_DBNAME,
        )
        _ensure_database_exists()
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            dbname=PG_DBNAME, user=PG_USER, password=PG_PASSWORD,
        )
        log.info("Successfully connected to newly created database '%s'.", PG_DBNAME)
        log.debug(
            "Connection opened to %s:%s/%s as user '%s'.",
            PG_HOST, PG_PORT, PG_DBNAME, PG_USER,
        )
        return conn
