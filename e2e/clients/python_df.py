#!/usr/bin/env python3
"""DataFrame-style Python clients over ADBC Flight SQL: pandas, polars, DuckDB (Arrow scan).

    python_df.py <pandas|polars|duckdb> <queries-dir> <out-dir>
    env: FLIGHT_URI, FLIGHT_TOKEN (server needs resultMode=complete for multi-table SQL)
"""
import datetime
import math
import os
import sys
import adbc_driver_flightsql.dbapi as flight
from adbc_driver_flightsql import DatabaseOptions


def cell(v):
    if v is None:
        return "\\N"
    if isinstance(v, float) and math.isnan(v):
        return "\\N"
    if hasattr(v, "to_pydatetime"):  # pandas Timestamp / NaT
        if v != v:
            return "\\N"
        v = v.to_pydatetime()
    if isinstance(v, datetime.datetime) and v.time() == datetime.time(0):
        v = v.date()
    return str(v)


def fetch(kind, conn, sql):
    if kind == "pandas":
        import pandas as pd
        df = pd.read_sql(sql, conn)
        return df.astype(object).where(df.notna(), None).itertuples(index=False, name=None)
    if kind == "polars":
        import polars as pl
        return pl.read_database(sql, connection=conn).rows()
    if kind == "duckdb":
        import duckdb
        with conn.cursor() as cur:
            cur.execute(sql)
            tbl = cur.fetch_arrow_table()  # noqa: F841 (read by DuckDB replacement scan)
        return duckdb.sql("select * from tbl").fetchall()
    raise SystemExit("unknown kind " + kind)


def sqlalchemy_main(qdir, out):
    """Superset route: SQLAlchemy 1.4 + flightsql-dbapi dialect (datafusion+flightsql://), token auth."""
    from sqlalchemy import create_engine, inspect, text
    host, port = os.environ["FLIGHT_URI"].split("//")[1].split(":")
    engine = create_engine(f"datafusion+flightsql://{host}:{port}?insecure=true&token={os.environ['FLIGHT_TOKEN']}")
    with open(os.path.join(out, "reflection.txt"), "w", encoding="utf-8") as f:
        for label, fn in [
            ("schemas", lambda i: i.get_schema_names()),
            ("tables(tpch)", lambda i: i.get_table_names("tpch")),
            ("has_table(tpch.nation)", lambda i: i.has_table("nation", "tpch")),
            ("columns(tpch.nation)", lambda i: [c["name"] + ":" + str(c["type"]) for c in i.get_columns("nation", "tpch")]),
        ]:
            try:
                f.write(f"{label}: {fn(inspect(engine))}\n")
            except Exception as e:  # noqa: BLE001
                f.write(f"{label}: ERROR {' '.join(str(e).split())[:300]}\n")
    with engine.connect() as conn:
        for name in sorted(x[:-4] for x in os.listdir(qdir) if x.endswith(".sql")):
            sql = open(os.path.join(qdir, name + ".sql"), encoding="utf-8").read().replace(":", "\\:")
            try:
                rows = conn.execute(text(sql)).fetchall()
                with open(os.path.join(out, name + ".tsv"), "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write("\t".join(cell(v) for v in r) + "\n")
            except Exception as e:  # noqa: BLE001
                with open(os.path.join(out, name + ".err"), "w", encoding="utf-8") as f:
                    f.write(" ".join(str(e).split()) + "\n")


def main():
    kind, qdir, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    if kind == "sqlalchemy":
        return sqlalchemy_main(qdir, out)
    conn = flight.connect(
        os.environ["FLIGHT_URI"],
        db_kwargs={DatabaseOptions.AUTHORIZATION_HEADER.value: "Bearer " + os.environ["FLIGHT_TOKEN"]},
    )
    for name in sorted(f[:-4] for f in os.listdir(qdir) if f.endswith(".sql")):
        sql = open(os.path.join(qdir, name + ".sql"), encoding="utf-8").read()
        try:
            rows = list(fetch(kind, conn, sql))
            with open(os.path.join(out, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(cell(v) for v in r) + "\n")
        except Exception as e:  # noqa: BLE001
            with open(os.path.join(out, name + ".err"), "w", encoding="utf-8") as f:
                f.write(" ".join(str(e).split()) + "\n")
    conn.close()


if __name__ == "__main__":
    main()
