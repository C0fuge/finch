#!/usr/bin/env python3
"""Metabase + generic Flight SQL driver (J0hnG4lt/metabase-flightsql-driver) via the Metabase HTTP API.

    metabase.py <metabase-url> <flight-host:port> <queries-dir> <out-dir>      env: FLIGHT_TOKEN, METABASE_PROBE
Sets Metabase up, adds the database (engine arrow-flight-sql, token auth, plaintext gRPC), syncs metadata, runs each
TPC-H query as a native query (/api/dataset) and a few GUI-style (MBQL) queries; MBQL answers must equal native ones.
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL, FLIGHT, QDIR, OUT = sys.argv[1:5]
SESSION = None


def call(path, body=None, method=None):
    h = {"Content-Type": "application/json"}
    if SESSION:
        h["X-Metabase-Session"] = SESSION
    req = urllib.request.Request(URL + path, data=None if body is None else json.dumps(body).encode(), method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:600]}") from None


def cell(v, base):
    if v is None:
        return "\\N"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, str) and base in ("type/Date", "type/DateTime", "type/Instant", "type/DateTimeWithLocalTZ"):
        try:
            d = datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
            return str(d.date() if d.time() == datetime.time(0) else d)
        except ValueError:
            return v
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15 and base in ("type/Integer", "type/BigInteger"):
        return str(int(v))
    return str(v)


def dataset(query):
    res = call("/api/dataset", query)
    if res.get("error") or res.get("status") == "failed":
        raise RuntimeError(str(res.get("error"))[:600])
    cols = [c.get("base_type") for c in res["data"]["cols"]]
    return [[cell(v, t) for v, t in zip(r, cols)] for r in res["data"]["rows"]]


def native(db, sql):
    return dataset({"database": db, "type": "native", "native": {"query": sql}})


def main():
    global SESSION
    os.makedirs(OUT, exist_ok=True)
    for _ in range(120):
        try:
            if call("/api/health").get("status") == "ok":
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(3)
    props = call("/api/session/properties")
    call("/api/setup", {"token": props["setup-token"], "prefs": {"site_name": "finch", "site_locale": "en", "allow_tracking": False},
                        "user": {"first_name": "a", "last_name": "b", "email": "admin@example.com", "password": "Finch-Test-1234!"}})
    SESSION = call("/api/session", {"username": "admin@example.com", "password": "Finch-Test-1234!"})["id"]
    host, port = FLIGHT.split(":")
    token = os.environ["FLIGHT_TOKEN"]
    last = None
    for details in ({"host": host, "port": int(port), "token": token, "useEncryption": False},
                    {"host": host, "port": int(port), "username": "metabase", "password": token, "useEncryption": False}):
        try:
            db = call("/api/database", {"name": "flight", "engine": "arrow-flight-sql", "details": details,
                                        "is_full_sync": True, "is_on_demand": False, "schedules": {}})
            print("database", db["id"], "details keys", sorted(details))
            break
        except RuntimeError as e:
            last = e
            print("create database failed with", sorted(details), str(e)[:400], flush=True)
    else:
        raise last
    dbid = db["id"]
    call(f"/api/database/{dbid}/sync_schema", {})
    meta = {}
    for _ in range(60):
        meta = call(f"/api/database/{dbid}/metadata")
        if meta.get("tables"):
            time.sleep(5)
            meta = call(f"/api/database/{dbid}/metadata")
            break
        time.sleep(3)
    tables = {(t.get("schema"), t["name"]): t for t in meta.get("tables", [])}
    print("synced tables:", sorted(f"{s}.{n}" for s, n in tables))
    if os.environ.get("METABASE_PROBE"):
        for sql in ["select 1 as i, 'a' as s", "select cast(1.5 as decimal(15,2)) as d", "select date '1998-01-02' as d",
                    "select count(*) from tpch.lineitem", "select l_orderkey, l_shipdate from tpch.lineitem limit 2"]:
            try:
                print("PROBE ok ", sql, native(dbid, sql), flush=True)
            except Exception as e:  # noqa: BLE001
                print("PROBE ERR", sql, str(e)[:300], flush=True)
        return
    for name in sorted(f[:-4] for f in os.listdir(QDIR) if f.endswith(".sql")):
        sql = open(os.path.join(QDIR, name + ".sql"), encoding="utf-8").read().strip().rstrip(";")
        try:
            rows = native(dbid, sql)
            with open(os.path.join(OUT, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(r) + "\n")
        except Exception as e:  # noqa: BLE001
            print(name, "ERROR", " ".join(str(e).split())[:600], flush=True)
            with open(os.path.join(OUT, name + ".err"), "w", encoding="utf-8") as f:
                f.write(" ".join(str(e).split()) + "\n")
    # GUI-style (MBQL) queries must agree with the equivalent native SQL
    li = tables.get(("tpch", "lineitem"))
    if not li:
        print("lineitem not found in synced metadata", flush=True)
        sys.exit(1)
    fields = {f["name"]: f["id"] for f in li["fields"]}
    base = {"source-table": li["id"]}
    checks = [
        ("count", {**base, "aggregation": [["count"]]}, "select count(*) from tpch.lineitem"),
        ("filter_sum", {**base, "aggregation": [["sum", ["field", fields["l_quantity"], None]]],
                        "filter": ["=", ["field", fields["l_returnflag"], None], "R"]},
         "select sum(l_quantity) from tpch.lineitem where l_returnflag = 'R'"),
        ("group_count", {**base, "aggregation": [["count"]], "breakout": [["field", fields["l_linestatus"], None]],
                         "order-by": [["asc", ["field", fields["l_linestatus"], None]]]},
         "select l_linestatus, count(*) from tpch.lineitem group by 1 order by 1"),
    ]
    bad = 0
    for label, q, sql in checks:
        try:
            a = dataset({"database": dbid, "type": "query", "query": q})
            b = native(dbid, sql)
            ok = a == b
        except Exception as e:  # noqa: BLE001
            a, b, ok = str(e)[:300], None, False
        print("MBQL", label, "OK" if ok else "DIFF", a, b, flush=True)
        bad += not ok
    try:  # native query with a field filter (template tag bound to a field)
        tag = {"lf": {"id": "11111111-1111-1111-1111-111111111111", "name": "lf", "display-name": "Flag", "type": "dimension",
                      "dimension": ["field", fields["l_returnflag"], None], "widget-type": "string/="}}
        a = dataset({"database": dbid, "type": "native", "native": {
            "query": "select count(*) from tpch.lineitem l where {{lf}}", "template-tags": tag},
            "parameters": [{"type": "string/=", "target": ["dimension", ["template-tag", "lf"]], "value": ["R"]}]})
        b = native(dbid, "select count(*) from tpch.lineitem where l_returnflag = 'R'")
        print("FIELDFILTER", "OK" if a == b else "DIFF", a, b, flush=True)
        bad += a != b
    except Exception as e:  # noqa: BLE001
        print("FIELDFILTER ERROR", str(e)[:400], flush=True)
        bad += 1
    if bad:
        sys.exit(1)


main()
