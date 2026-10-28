#!/usr/bin/env python3
"""Apache Superset + ADBC GizmoSQL dialect (superset-sqlalchemy-gizmosql-adbc-dialect) via the Superset REST API.

    superset.py <superset-url> <flight-host:port> <queries-dir> <out-dir>      env: FLIGHT_TOKEN, SUPERSET_PROBE
Adds the database (gizmosql://user:<token>@host:port, ADBC basic auth), runs each TPC-H query in SQL Lab (sync),
then creates a dataset + chart and reads it through /api/v1/chart/data; the chart answer must equal native SQL.
"""
import datetime
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL, FLIGHT, QDIR, OUT = sys.argv[1:5]
TOKEN = None
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(path, body=None, method=None):
    h = {"Content-Type": "application/json"}
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(URL + path, data=None if body is None else json.dumps(body).encode(), method=method, headers=h)
    try:
        with OPENER.open(req, timeout=900) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:800]}") from None


def cell(v, typ=""):
    if v is None:
        return "\\N"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float)) and "DATE" in typ.upper() and not isinstance(v, bool):
        d = datetime.datetime.fromtimestamp(v / 1000, datetime.timezone.utc).replace(tzinfo=None)
        return str(d.date() if d.time() == datetime.time(0) else d)
    if isinstance(v, str) and len(v) >= 10 and v[4] == "-" and v[7] == "-" and v[:4].isdigit():
        try:
            d = datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
            return str(d.date() if d.time() == datetime.time(0) else d)
        except ValueError:
            return v
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15 and not typ.upper().startswith(("DOUBLE", "FLOAT", "DECIMAL", "NUMERIC")):
        return str(int(v))
    return str(v)


def sqllab(dbid, sql):
    res = call("/api/v1/sqllab/execute/", {"database_id": dbid, "sql": sql, "runAsync": False, "queryLimit": 1000000,
                                           "schema": None, "select_as_cta": False, "expand_data": True})
    if res.get("status") not in (None, "success") or res.get("errors"):
        raise RuntimeError(str(res)[:600])
    names = [c["column_name"] if "column_name" in c else c["name"] for c in res["columns"]]
    types = [c.get("type") or "" for c in res["columns"]]
    return [[cell(r.get(n), t) for n, t in zip(names, types)] for r in res["data"]]


def main():
    global TOKEN
    os.makedirs(OUT, exist_ok=True)
    for _ in range(200):
        try:
            with urllib.request.urlopen(URL + "/health", timeout=5):
                break
        except Exception:  # noqa: BLE001
            time.sleep(3)
    TOKEN = call("/api/v1/security/login", {"username": "admin", "password": "admin", "provider": "db", "refresh": True})["access_token"]
    host, port = FLIGHT.split(":")
    if os.environ.get("FLIGHT_USER"):  # LDAP login over TLS (the container trusts the throwaway cert via SSL_CERT_FILE)
        bad_uri = f"gizmosql://{os.environ['FLIGHT_BAD_USER']}:{os.environ['FLIGHT_BAD_PASSWORD']}@{host}:{port}?useEncryption=true"
        try:
            call("/api/v1/database/test_connection/", {"database_name": "flight-bad", "sqlalchemy_uri": bad_uri})
            print("LOGIN wrong password: ACCEPTED (unexpected)", flush=True)
            sys.exit(1)
        except RuntimeError as e:
            print("LOGIN wrong password refused:", " ".join(str(e).split())[:300], flush=True)
        uri = f"gizmosql://{os.environ['FLIGHT_USER']}:{os.environ['FLIGHT_PASSWORD']}@{host}:{port}?useEncryption=true"
    else:
        uri = f"gizmosql://superset:{os.environ['FLIGHT_TOKEN']}@{host}:{port}"
    db = call("/api/v1/database/", {"database_name": "flight", "sqlalchemy_uri": uri, "expose_in_sqllab": True})
    dbid = db["id"]
    print("database", dbid, flush=True)
    try:
        print("test connection:", call("/api/v1/database/test_connection/", {"database_name": "flight", "sqlalchemy_uri": uri}), flush=True)
    except RuntimeError as e:
        print("test connection ERROR", str(e)[:400], flush=True)
    for what in ("schemas", "tables"):
        try:
            print(what, str(call(f"/api/v1/database/{dbid}/{what}/" + ("" if what == "schemas" else "?q=(schema_name:tpch)")))[:400], flush=True)
        except RuntimeError as e:
            print(what, "ERROR", str(e)[:300], flush=True)
    if os.environ.get("SUPERSET_PROBE"):
        for sql in ["select 1 as i, 'a' as s", "select cast(1.5 as decimal(15,2)) as d", "select date '1998-01-02' as d",
                    "select count(*) from tpch.lineitem", "select l_orderkey, l_shipdate from tpch.lineitem limit 2"]:
            try:
                print("PROBE ok ", sql, sqllab(dbid, sql), flush=True)
            except Exception as e:  # noqa: BLE001
                print("PROBE ERR", sql, str(e)[:400], flush=True)
        return
    for name in sorted(f[:-4] for f in os.listdir(QDIR) if f.endswith(".sql")):
        sql = open(os.path.join(QDIR, name + ".sql"), encoding="utf-8").read().strip().rstrip(";")
        try:
            rows = sqllab(dbid, sql)
            with open(os.path.join(OUT, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(r) + "\n")
        except Exception as e:  # noqa: BLE001
            print(name, "ERROR", " ".join(str(e).split())[:600], flush=True)
            with open(os.path.join(OUT, name + ".err"), "w", encoding="utf-8") as f:
                f.write(" ".join(str(e).split()) + "\n")
    # dataset + chart through the chart-data API
    bad = 0
    try:
        ds = call("/api/v1/dataset/", {"database": dbid, "schema": "tpch", "table_name": "lineitem"})["id"]
        qc = {"datasource": {"id": ds, "type": "table"}, "force": True, "queries": [{
            "columns": ["l_linestatus"], "metrics": [{"expressionType": "SQL", "sqlExpression": "COUNT(*)", "label": "n"}],
            "orderby": [["n", False]], "row_limit": 100}], "result_format": "json", "result_type": "full"}
        res = call("/api/v1/chart/data", qc)["result"][0]
        a = sorted((str(r["l_linestatus"]), int(r["n"])) for r in res["data"])
        b = sorted((r[0], int(r[1])) for r in sqllab(dbid, "select l_linestatus, count(*) from tpch.lineitem group by 1"))
        print("CHART", "OK" if a == b else "DIFF", a, b, flush=True)
        bad += a != b
        ch = call("/api/v1/chart/", {"slice_name": "n by status", "viz_type": "table", "datasource_id": ds, "datasource_type": "table",
                                      "params": json.dumps({"viz_type": "table", "metrics": ["count"], "groupby": ["l_linestatus"]})})
        print("chart saved", ch.get("id"), flush=True)
    except Exception as e:  # noqa: BLE001
        print("CHART ERROR", str(e)[:600], flush=True)
        bad += 1
    if bad:
        sys.exit(1)


main()
