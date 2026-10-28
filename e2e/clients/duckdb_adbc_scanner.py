#!/usr/bin/env python3
"""DuckDB as a client via the community extension `adbc_scanner` (adbc_connect + adbc_scan) and our Flight SQL server.

    duckdb_adbc_scanner.py <queries-dir> <out-dir>
    env: FLIGHT_URI, FLIGHT_TOKEN (server needs resultMode=complete for multi-table SQL)
The ADBC Flight SQL driver library is taken from the pip package adbc-driver-flightsql.
"""
import datetime
import os
import sys
import duckdb
import adbc_driver_flightsql


def cell(v):
    if v is None:
        return "\\N"
    if isinstance(v, datetime.datetime) and v.time() == datetime.time(0):
        v = v.date()
    return str(v)


def main():
    qdir, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    lib = os.path.join(os.path.dirname(adbc_driver_flightsql.__file__), "libadbc_driver_flightsql.so")
    print("driver lib:", lib, os.path.exists(lib))
    con = duckdb.connect()
    for s in ("INSTALL adbc_scanner FROM community", "LOAD adbc_scanner"):
        con.execute(s)
    opts = "{'driver': '%s', 'uri': '%s', 'adbc.flight.sql.authorization_header': 'Bearer %s'}" % (
        lib, os.environ["FLIGHT_URI"], os.environ["FLIGHT_TOKEN"])
    con.execute("SET VARIABLE conn = (SELECT adbc_connect(%s))" % opts)
    for name in sorted(f[:-4] for f in os.listdir(qdir) if f.endswith(".sql")):
        sql = open(os.path.join(qdir, name + ".sql"), encoding="utf-8").read().strip().rstrip(";")
        try:
            lit = "'" + sql.replace("'", "''") + "'"
            rows = con.execute("SELECT * FROM adbc_scan(getvariable('conn'), %s)" % lit).fetchall()
            with open(os.path.join(out, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(cell(v) for v in r) + "\n")
        except Exception as e:  # noqa: BLE001
            msg = " ".join(str(e).split())
            if name.endswith("01"):
                print("q01 error:", msg[:500])
            with open(os.path.join(out, name + ".err"), "w", encoding="utf-8") as f:
                f.write(msg + "\n")


if __name__ == "__main__":
    main()
