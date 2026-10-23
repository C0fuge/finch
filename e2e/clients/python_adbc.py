#!/usr/bin/env python3
"""ADBC Flight SQL client: run the TPC-H queries, write TSV answers for e2e/compare.py.

    python_adbc.py <queries-dir> <out-dir>      env: FLIGHT_URI, FLIGHT_TOKEN, TABLE_PREFIX (default 'tpch.')
"""
import os
import re
import sys
import adbc_driver_flightsql.dbapi as flight
from adbc_driver_flightsql import DatabaseOptions

TABLES = "lineitem orders customer part partsupp supplier nation region".split()


def cell(v):
    return "\\N" if v is None else str(v)


def main():
    qdir, out = sys.argv[1:3]
    prefix = os.environ.get("TABLE_PREFIX", "tpch.")
    os.makedirs(out, exist_ok=True)
    conn = flight.connect(
        os.environ["FLIGHT_URI"],
        db_kwargs={DatabaseOptions.AUTHORIZATION_HEADER.value: "Bearer " + os.environ["FLIGHT_TOKEN"]},
    )
    for name in sorted(f[:-4] for f in os.listdir(qdir) if f.endswith(".sql")):
        sql = open(os.path.join(qdir, name + ".sql"), encoding="utf-8").read()
        sql = re.sub(r"\b(from|join)\s+(" + "|".join(TABLES) + r")\b", lambda m: f"{m[1]} {prefix}{m[2]}", sql, flags=re.I)
        sql = re.sub(r",\s*(" + "|".join(TABLES) + r")\b", lambda m: f", {prefix}{m[1]}", sql, flags=re.I)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
            with open(os.path.join(out, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(cell(v) for v in r) + "\n")
        except Exception as e:  # noqa: BLE001
            with open(os.path.join(out, name + ".err"), "w", encoding="utf-8") as f:
                f.write(str(e) + "\n")
    conn.close()


if __name__ == "__main__":
    main()
