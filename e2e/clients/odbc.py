#!/usr/bin/env python3
"""ODBC route (Tableau / Power BI / Excel): Dremio Arrow Flight SQL ODBC driver (Linux RPM) via unixODBC + pyodbc.

    odbc.py <queries-dir> <out-dir>
    env: FLIGHT_URI (grpc://host:port), FLIGHT_TOKEN, ODBC_DRIVER (name in odbcinst.ini), ODBC_PROBE (non-empty: metadata only)
"""
import datetime
import decimal
import os
import sys
import pyodbc


def cell(v):
    if v is None:
        return "\\N"
    if isinstance(v, datetime.datetime) and v.time() == datetime.time(0):
        v = v.date()
    return str(v)


def main():
    qdir, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    host, port = os.environ["FLIGHT_URI"].split("//")[1].split(":")
    cs = (f"Driver={{{os.environ.get('ODBC_DRIVER', 'Arrow Flight SQL ODBC Driver')}}};Host={host};Port={port};"
          f"useEncryption=false;Token={os.environ['FLIGHT_TOKEN']}")
    print("drivers:", pyodbc.drivers())
    conn = pyodbc.connect(cs, autocommit=True)
    print("connected:", conn.getinfo(pyodbc.SQL_DBMS_NAME), conn.getinfo(pyodbc.SQL_DBMS_VER))
    cur = conn.cursor()
    for label, fn in [("tables", lambda: [tuple(r)[:4] for r in cur.tables()][:40]),
                      ("columns(nation)", lambda: [tuple(r)[3:6] for r in cur.columns(table="nation")][:20])]:
        try:
            print(label, fn())
        except Exception as e:  # noqa: BLE001
            print(label, "ERROR", " ".join(str(e).split())[:300])
    if os.environ.get("ODBC_PROBE"):
        return
    for name in sorted(f[:-4] for f in os.listdir(qdir) if f.endswith(".sql")):
        sql = open(os.path.join(qdir, name + ".sql"), encoding="utf-8").read()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            with open(os.path.join(out, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(cell(v) for v in r) + "\n")
        except Exception as e:  # noqa: BLE001
            with open(os.path.join(out, name + ".err"), "w", encoding="utf-8") as f:
                f.write(" ".join(str(e).split()) + "\n")


if __name__ == "__main__":
    main()
