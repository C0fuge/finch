#!/usr/bin/env python3
"""Plain pyarrow.flight client speaking Flight SQL by hand (CommandStatementQuery), TSV answers for e2e/compare.py.

    python_pyarrow_flight.py <queries-dir> <out-dir>      env: FLIGHT_URI, FLIGHT_TOKEN, TABLE_PREFIX (default 'tpch.'),
    FLIGHT_USER/FLIGHT_PASSWORD (Flight handshake login instead of the bearer FLIGHT_TOKEN, e.g. LDAP; FLIGHT_TLS_CA = PEM file of the
    server cert), FLIGHT_COMPRESSION (optional: zstd|lz4 -> call header 'arrow-compression')
Reads every endpoint of the FlightInfo (partial mode may return several).
"""
import os
import re
import sys
import pyarrow.flight as fl

TABLES = "lineitem orders customer part partsupp supplier nation region".split()
TYPE_URL = b"type.googleapis.com/arrow.flight.protocol.sql.CommandStatementQuery"


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def field(num, payload):  # length-delimited protobuf field
    return varint(num << 3 | 2) + varint(len(payload)) + payload


def command(sql):
    return field(1, TYPE_URL) + field(2, field(1, sql.encode("utf-8")))  # Any{type_url, CommandStatementQuery{query}}


def cell(v):
    return "\\N" if v is None else str(v)


def main():
    qdir, out = sys.argv[1:3]
    prefix = os.environ.get("TABLE_PREFIX", "tpch.")
    os.makedirs(out, exist_ok=True)
    tls = {}
    if os.environ.get("FLIGHT_TLS_CA"):
        tls["tls_root_certs"] = open(os.environ["FLIGHT_TLS_CA"], "rb").read()
    client = fl.connect(os.environ["FLIGHT_URI"], **tls)
    if os.environ.get("FLIGHT_USER"):
        k, v = client.authenticate_basic_token(os.environ["FLIGHT_USER"], os.environ["FLIGHT_PASSWORD"])
        headers = [(k, v)]
    else:
        headers = [(b"authorization", ("Bearer " + os.environ["FLIGHT_TOKEN"]).encode())]
    if os.environ.get("FLIGHT_COMPRESSION"):
        headers.append((b"arrow-compression", os.environ["FLIGHT_COMPRESSION"].encode()))
    opts = fl.FlightCallOptions(headers=headers)
    for name in sorted(f[:-4] for f in os.listdir(qdir) if f.endswith(".sql")):
        sql = open(os.path.join(qdir, name + ".sql"), encoding="utf-8").read()
        sql = re.sub(r"\b(from|join)\s+(" + "|".join(TABLES) + r")\b", lambda m: f"{m[1]} {prefix}{m[2]}", sql, flags=re.I)
        sql = re.sub(r",\s*(" + "|".join(TABLES) + r")\b", lambda m: f", {prefix}{m[1]}", sql, flags=re.I)
        try:
            info = client.get_flight_info(fl.FlightDescriptor.for_command(command(sql)), opts)
            rows = []
            for ep in info.endpoints:
                t = client.do_get(ep.ticket, opts).read_all()
                cols = [c.to_pylist() for c in t.columns]
                rows.extend(zip(*cols) if cols else [])
            with open(os.path.join(out, name + ".tsv"), "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("\t".join(cell(v) for v in r) + "\n")
        except Exception as e:  # noqa: BLE001
            with open(os.path.join(out, name + ".err"), "w", encoding="utf-8") as f:
                f.write(" ".join(str(e).split()) + "\n")
    client.close()


if __name__ == "__main__":
    main()
