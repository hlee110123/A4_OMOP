#!/usr/bin/env python3
"""Load the A4/LEARN OMOP CSVs into an existing PostgreSQL schema.

Headless equivalent of step 9 of load_omop_to_postgres.ipynb. Assumes the target
schema already exists (clone it with the notebook first). Reads connection settings
from .env.

Loading is BY COLUMN NAME, not position: several exported tables do not follow CDM
column order, so a positional COPY would put values in the wrong columns and still
succeed. Each table is truncated first, so this is safe to re-run.
"""
import io
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

HOST = os.getenv("PGHOST")
PORT = int(os.getenv("PGPORT", "5432"))
USER = os.getenv("PGUSER")
PW = os.getenv("PGPASSWORD")
DB = os.getenv("PGTARGET_DB", "a4")
SCHEMA = os.getenv("PGLOAD_SCHEMA", "dbo")
CSV_DIR = Path(__file__).parent / "OMOP_Output"

TABLES = ["person", "observation_period", "visit_occurrence", "condition_occurrence",
          "drug_exposure", "measurement", "observation", "procedure_occurrence",
          "cdm_source", "image_occurrence", "image_feature"]


def connect():
    return psycopg2.connect(host=HOST, port=PORT, dbname=DB, user=USER, password=PW,
                            sslmode="require", connect_timeout=30)


def csv_path(t):
    p = CSV_DIR / f"{t}.csv"
    return p if p.exists() else CSV_DIR / "mi_cdm" / f"{t}.csv"


def load_table(conn, table, chunksize=200_000):
    path = csv_path(table)
    if not path.exists():
        print(f"  {table:24s} SKIPPED (no csv)", flush=True)
        return 0

    with conn.cursor() as cur:
        cur.execute("""select column_name, is_nullable from information_schema.columns
                       where table_schema=%s and table_name=%s order by ordinal_position""",
                    (SCHEMA, table))
        meta = cur.fetchall()
    if not meta:
        print(f"  {table:24s} SKIPPED (no such table in {SCHEMA})", flush=True)
        return 0

    db_cols = [r[0] for r in meta]
    notnull = {r[0].lower() for r in meta if r[1] == "NO"}
    db_lower = {c.lower(): c for c in db_cols}

    header = pd.read_csv(path, nrows=0).columns.tolist()
    load_cols = [c for c in header if c.lower() in db_lower]
    unmatched = [c for c in header if c.lower() not in db_lower]
    absent = [c for c in db_cols if c.lower() not in {h.lower() for h in header}]
    int_cols = {c for c in load_cols
                if c.lower().endswith("_id") or c.lower().endswith("_concept_id")}
    required = [c for c in load_cols if c.lower() in notnull]

    collist = ",".join(f'"{db_lower[c.lower()]}"' for c in load_cols)
    sql = f'copy "{SCHEMA}"."{table}" ({collist}) from stdin with (format csv, null \'\')'

    t0, n, dropped = time.time(), 0, 0
    with conn.cursor() as cur:
        cur.execute(f'truncate table "{SCHEMA}"."{table}"')
        for chunk in pd.read_csv(path, chunksize=chunksize, low_memory=False):
            chunk = chunk[load_cols].copy()
            for c in int_cols:
                chunk[c] = pd.to_numeric(chunk[c], errors="coerce").astype("Int64")
            if required:
                before = len(chunk)
                chunk = chunk.dropna(subset=required)
                dropped += before - len(chunk)
            if not len(chunk):
                continue
            buf = io.StringIO()
            chunk.to_csv(buf, index=False, header=False, na_rep="")
            buf.seek(0)
            cur.copy_expert(sql, buf)
            n += len(chunk)
    conn.commit()

    note = ""
    if unmatched:
        note += f"  [csv cols dropped: {unmatched}]"
    if absent:
        note += f"  [left NULL: {len(absent)} cols]"
    print(f"  {table:24s} {n:12,} rows  {time.time()-t0:7.1f}s{note}", flush=True)
    if dropped:
        print(f"  {'':24s} {dropped:12,} DROPPED (NOT NULL violation)", flush=True)
    return n


def main():
    print(f"loading {CSV_DIR} -> {DB}.{SCHEMA} on {HOST}")
    print("each table is truncated first, so this is safe to re-run\n", flush=True)
    total = 0
    with connect() as conn:
        for t in TABLES:
            total += load_table(conn, t)
    print(f"\nloaded {total:,} rows")

    print("\nverification: database vs csv\n")
    ok = True
    with connect() as conn, conn.cursor() as cur:
        for t in TABLES:
            p = csv_path(t)
            if not p.exists():
                continue
            with open(p, "rb") as fh:
                csv_n = sum(1 for _ in fh) - 1
            cur.execute(f'select count(*) from "{SCHEMA}"."{t}"')
            db_n = cur.fetchone()[0]
            ok &= db_n == csv_n
            flag = "ok" if db_n == csv_n else f"MISMATCH ({csv_n - db_n:+,})"
            print(f"  {t:24s} db={db_n:11,}  csv={csv_n:11,}  {flag}")
    print("\nall rows accounted for" if ok else "\nMISMATCH - investigate")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
