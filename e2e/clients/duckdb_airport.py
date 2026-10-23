"""Probe: can DuckDB's community extension `airport` attach our Flight SQL server? Prints the outcome; never fails."""
import os, sys, duckdb

loc = os.environ.get('FLIGHT_URI', 'grpc://localhost:32010')
tok = os.environ.get('FLIGHT_TOKEN', '')
con = duckdb.connect()
steps = [
    "INSTALL airport FROM community",
    "LOAD airport",
    f"CREATE SECRET s (TYPE airport, auth_token '{tok}', scope '{loc}')",
    f"ATTACH 'tpch' (TYPE AIRPORT, LOCATION '{loc}')",
    "SHOW ALL TABLES",
    "SELECT count(*) FROM tpch.tpch.lineitem",
]
for s in steps:
    try:
        r = con.execute(s).fetchall()
        print("OK  ", s.split("'")[0][:60], str(r)[:200])
    except Exception as e:
        print("FAIL", s.split("'")[0][:60], "->", str(e)[:400])
        break
