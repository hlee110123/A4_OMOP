#!/usr/bin/env python3
"""Copy the OMOP vocabulary tables from one database to another.

postgres_fdw and dblink are not allow-listed on Azure Flexible Server, so a
server-side copy is unavailable. This streams each table with binary COPY piped
directly between the two connections - no pandas, no intermediate files.

Binary format is safe here because both databases are the same PostgreSQL major
version; it is faster than text and preserves types exactly.

Tables are copied smallest first so useful data lands early. Each is truncated
before loading, so the script is safe to re-run.
"""
import os
import sys
import threading
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

H = os.getenv("PGHOST")
P = int(os.getenv("PGPORT", "5432"))
U = os.getenv("PGUSER")
PW = os.getenv("PGPASSWORD")
SRC_DB = os.getenv("PGSOURCE_DB", "adni")
DST_DB = os.getenv("PGTARGET_DB", "a4")
SCHEMA = os.getenv("PGLOAD_SCHEMA", "dbo")

# smallest first; concept_ancestor last (72M rows / 4 GB)
TABLES = ["domain", "concept_class", "relationship", "vocabulary",
          "concept_relationship", "concept_synonym", "drug_strength",
          "concept", "concept_ancestor"]


def connect(db):
    return psycopg2.connect(host=H, port=P, dbname=db, user=U, password=PW,
                            sslmode="require", connect_timeout=30,
                            keepalives=1, keepalives_idle=30,
                            keepalives_interval=10, keepalives_count=5)


def copy_table(table):
    src, dst = connect(SRC_DB), connect(DST_DB)
    try:
        with src.cursor() as c:
            c.execute(f'select count(*) from "{SCHEMA}"."{table}"')
            expected = c.fetchone()[0]
        if expected == 0:
            print(f"  {table:24s} 0 rows in source - skipped", flush=True)
            return 0

        with dst.cursor() as c:
            c.execute(f'truncate table "{SCHEMA}"."{table}"')
        dst.commit()

        r_fd, w_fd = os.pipe()
        err = {}

        def produce():
            try:
                with src.cursor() as c, os.fdopen(w_fd, "wb") as w:
                    c.copy_expert(f'copy "{SCHEMA}"."{table}" to stdout (format binary)', w)
            except Exception as e:                      # noqa: BLE001
                err["produce"] = e
                try:
                    os.close(w_fd)
                except OSError:
                    pass

        t0 = time.time()
        th = threading.Thread(target=produce, daemon=True)
        th.start()
        with dst.cursor() as c, os.fdopen(r_fd, "rb") as r:
            c.copy_expert(f'copy "{SCHEMA}"."{table}" from stdin (format binary)', r)
        dst.commit()
        th.join()
        if "produce" in err:
            raise err["produce"]

        with dst.cursor() as c:
            c.execute(f'select count(*) from "{SCHEMA}"."{table}"')
            got = c.fetchone()[0]
        dt = time.time() - t0
        flag = "ok" if got == expected else f"MISMATCH (expected {expected:,})"
        print(f"  {table:24s} {got:>11,} rows  {dt:7.1f}s  {got/max(dt,0.01):>9,.0f} rows/s  {flag}",
              flush=True)
        return got
    finally:
        src.close()
        dst.close()


def main():
    print(f"copying vocabulary {SRC_DB}.{SCHEMA} -> {DST_DB}.{SCHEMA} on {H}")
    print("binary COPY piped between connections; each table truncated first\n", flush=True)
    total = 0
    for t in TABLES:
        try:
            total += copy_table(t)
        except Exception as e:                          # noqa: BLE001
            print(f"  {t:24s} FAILED: {type(e).__name__}: "
                  f"{str(e).strip().splitlines()[0][:90]}", flush=True)
    print(f"\ncopied {total:,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
