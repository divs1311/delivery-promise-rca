"""Build the DuckDB warehouse and run every SQL analysis.

    python src/run_analysis.py

1. sql/00_load.sql and sql/01_build_fact.sql run as scripts (tables + views).
2. Every other sql/NN_*.sql file holds one or more queries, each introduced by a
   `-- name: <query_name>` line. Each query's result is written to
   outputs/tables/<query_name>.csv.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
OUT = ROOT / "outputs" / "tables"
DB_PATH = ROOT / "outputs" / "olist.duckdb"
SCRIPTS = ("00_load.sql", "01_build_fact.sql")


def named_queries(sql: str) -> list[tuple[str, str]]:
    """Split a file into (name, query) pairs on '-- name: x' markers."""
    parts = re.split(r"^--\s*name:\s*(\w+)\s*$", sql, flags=re.M)
    # parts = [preamble, name1, body1, name2, body2, ...]
    return [(parts[i], parts[i + 1].strip().rstrip(";")) for i in range(1, len(parts), 2)]


def connect(rebuild: bool = False) -> duckdb.DuckDBPyConnection:
    if rebuild and DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"SET file_search_path = '{ROOT}'")
    return con


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect(rebuild=True)
    t0 = time.time()
    for script in SCRIPTS:
        con.execute((SQL_DIR / script).read_text())
        print(f"✓ {script}")
    n = 0
    for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        if path.name in SCRIPTS:
            continue
        for name, query in named_queries(path.read_text()):
            df = con.execute(query).fetchdf()
            df.to_csv(OUT / f"{name}.csv", index=False)
            n += 1
            print(f"✓ {path.name} → {name}.csv ({len(df)} rows)")
    con.close()
    print(f"\n{n} result tables written to {OUT.relative_to(ROOT)} in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
