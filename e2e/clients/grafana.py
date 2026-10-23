#!/usr/bin/env python3
"""Grafana Flight SQL datasource (influxdata-flightsql-datasource) via the Grafana HTTP API.

    grafana.py <grafana-url> <flight-host:port> <queries-dir> <out-dir>      env: FLIGHT_TOKEN
Provisions the datasource (token auth, plaintext gRPC), runs each TPC-H query through /api/ds/query.
"""
import base64
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL, FLIGHT, QDIR, OUT = sys.argv[1:5]
AUTH = "Basic " + base64.b64encode(b"admin:admin").decode()


def call(path, body=None, method=None):
    req = urllib.request.Request(URL + path, data=None if body is None else json.dumps(body).encode(), method=method,
                                 headers={"Authorization": AUTH, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:500]}") from None


def cell(v, typ):
    if v is None:
        return "\\N"
    if typ == "time":
        d = datetime.datetime.fromtimestamp(v / 1000, datetime.timezone.utc).replace(tzinfo=None)
        return str(d.date() if d.time() == datetime.time(0) else d)
    if isinstance(v, bool):
        return str(v).lower()
    return str(v)


def run(ds, sql):
    res = call("/api/ds/query", {"from": "now-1h", "to": "now", "queries": [
        {"refId": "A", "datasource": {"uid": ds["uid"], "type": ds["type"]}, "queryText": sql, "rawSql": sql, "rawQuery": True,
         "format": "table", "maxDataPoints": 1000000}]})["results"]["A"]
    if res.get("error"):
        raise RuntimeError(res["error"])
    rows = []
    for fr in res.get("frames", []):
        types = [f["type"] for f in fr["schema"]["fields"]]
        cols = fr["data"]["values"]
        rows += [[cell(c[i], t) for c, t in zip(cols, types)] for i in range(len(cols[0]) if cols else 0)]
    return rows


def wrap(ds, sql):
    """The plugin returns empty columns for DECIMAL and DATE/TIMESTAMP (Arrow decimal128/date32 are not mapped):
    cast those to DOUBLE / VARCHAR on the server side, using DESCRIBE to find them."""
    exprs = []
    for name, typ in [(r[0], r[1]) for r in run(ds, "describe " + sql)]:
        q = '"' + name.replace('"', '""') + '"'
        if typ.startswith("DECIMAL"):
            exprs.append(f"cast({q} as double) as {q}")
        elif typ.startswith(("DATE", "TIMESTAMP", "TIME")):
            exprs.append(f"cast({q} as varchar) as {q}")
        else:
            exprs.append(q)
    return "select " + ", ".join(exprs) + " from (" + sql + ") t"


def main():
    os.makedirs(OUT, exist_ok=True)
    for _ in range(60):
        try:
            call("/api/health")
            break
        except Exception:  # noqa: BLE001
            time.sleep(2)
    print("plugins:", [p["id"] for p in call("/api/plugins?type=datasource") if "flight" in p["id"]])
    ds = call("/api/datasources", {
        "name": "flight", "type": "influxdata-flightsql-datasource", "access": "proxy",
        "jsonData": {"host": FLIGHT, "secure": False, "selectedAuthType": "token", "metadata": []},
        "secureJsonData": {"token": os.environ["FLIGHT_TOKEN"]},
    })["datasource"]
    print("datasource uid", ds["uid"])
    print("health:", call(f"/api/datasources/uid/{ds['uid']}/health"))
    if os.environ.get("GRAFANA_PROBE"):
        for sql in ["select 1 as i, 'a' as s", "select cast(1.5 as double) as d", "select cast(1.5 as decimal(15,2)) as d",
                    "select cast(1.5 as decimal(38,2)) as d", "select date '1998-01-02' as d",
                    "select count(*) from tpch.lineitem", "select sum(l_quantity) from tpch.lineitem",
                    "select l_orderkey, l_shipdate from tpch.lineitem limit 2"]:
            try:
                r = call("/api/ds/query", {"from": "now-1h", "to": "now", "queries": [
                    {"refId": "A", "datasource": {"uid": ds["uid"], "type": ds["type"]}, "queryText": sql, "rawQuery": True,
                     "format": "table"}]})["results"]["A"]
                print("PROBE ok ", sql, json.dumps(r.get("frames", r))[:300], flush=True)
            except Exception as e:  # noqa: BLE001
                print("PROBE ERR", sql, str(e)[:200], flush=True)
        return
    for name in sorted(f[:-4] for f in os.listdir(QDIR) if f.endswith(".sql")):
        sql = open(os.path.join(QDIR, name + ".sql"), encoding="utf-8").read().strip().rstrip(";")
        try:
            rows = run(ds, wrap(ds, sql) if os.environ.get("GRAFANA_RAW") is None else sql)
            with open(os.path.join(OUT, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(r) + "\n")
        except Exception as e:  # noqa: BLE001
            print(name, "ERROR", " ".join(str(e).split())[:600], flush=True)
            with open(os.path.join(OUT, name + ".err"), "w", encoding="utf-8") as f:
                f.write(" ".join(str(e).split()) + "\n")


main()
