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
    for name in sorted(f[:-4] for f in os.listdir(QDIR) if f.endswith(".sql")):
        sql = open(os.path.join(QDIR, name + ".sql"), encoding="utf-8").read().strip().rstrip(";")
        try:
            res = call("/api/ds/query", {"from": "now-1h", "to": "now", "queries": [
                {"refId": "A", "datasource": {"uid": ds["uid"], "type": ds["type"]}, "rawSql": sql, "format": "table",
                 "maxDataPoints": 1000000}]})["results"]["A"]
            if res.get("error"):
                raise RuntimeError(res["error"])
            rows = []
            for fr in res.get("frames", []):
                types = [f["type"] for f in fr["schema"]["fields"]]
                cols = fr["data"]["values"]
                rows += [[cell(c[i], t) for c, t in zip(cols, types)] for i in range(len(cols[0]) if cols else 0)]
            with open(os.path.join(OUT, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(r) + "\n")
        except Exception as e:  # noqa: BLE001
            print(name, "ERROR", " ".join(str(e).split())[:600], flush=True)
            with open(os.path.join(OUT, name + ".err"), "w", encoding="utf-8") as f:
                f.write(" ".join(str(e).split()) + "\n")


main()
