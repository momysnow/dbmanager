#!/usr/bin/env python3
"""Seed sample databases with schema and test data."""

import os
import sys
from pathlib import Path

SEEDS_DIR = Path(__file__).parent


def seed_postgres() -> bool:
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "testdb"),
            user=os.getenv("POSTGRES_USER", "testuser"),
            password=os.getenv("POSTGRES_PASSWORD", "testpassword"),
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            sql = (SEEDS_DIR / "postgres_seed.sql").read_text()
            cur.execute(sql)
        conn.close()
        print("[seed] PostgreSQL seeded successfully")
        return True
    except Exception as e:
        print(f"[seed] PostgreSQL seed failed: {e}", file=sys.stderr)
        return False


def seed_mysql() -> bool:
    try:
        import pymysql

        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "mysql"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "testdb"),
            user=os.getenv("MYSQL_USER", "testuser"),
            password=os.getenv("MYSQL_PASSWORD", "testpassword"),
        )
        with conn.cursor() as cur:
            sql = (SEEDS_DIR / "mysql_seed.sql").read_text()
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
        conn.commit()
        conn.close()
        print("[seed] MySQL seeded successfully")
        return True
    except Exception as e:
        print(f"[seed] MySQL seed failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    ok_pg = seed_postgres()
    ok_my = seed_mysql()
    sys.exit(0 if (ok_pg and ok_my) else 1)
