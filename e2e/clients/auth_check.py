#!/usr/bin/env python3
"""Login rows (ADBC Python): the good credential must run a query, bad ones must be refused.
    auth_check.py <report file>    env: FLIGHT_URI and either FLIGHT_USER/FLIGHT_PASSWORD (+FLIGHT_BAD_PASSWORD)
    or FLIGHT_TOKEN (+FLIGHT_EXPIRED_TOKEN, FLIGHT_BAD_TOKEN); exit 1 on any unexpected result."""
import os
import sys
import adbc_driver_flightsql.dbapi as flight
from adbc_driver_flightsql import DatabaseOptions

E = os.environ
H = DatabaseOptions.AUTHORIZATION_HEADER.value
cases = []  # (name, db kwargs, should_work)
if E.get("FLIGHT_USER"):
    cases += [("login ok", {"username": E["FLIGHT_USER"], "password": E["FLIGHT_PASSWORD"]}, True),
              ("wrong password", {"username": E["FLIGHT_USER"], "password": E["FLIGHT_BAD_PASSWORD"]}, False),
              ("unknown user", {"username": "nobody-" + E["FLIGHT_USER"], "password": E["FLIGHT_PASSWORD"]}, False),
              ("no credentials", {}, False)]
else:
    cases += [("bearer ok", {H: "Bearer " + E["FLIGHT_TOKEN"]}, True),
              ("expired token", {H: "Bearer " + E["FLIGHT_EXPIRED_TOKEN"]}, False),
              ("wrong signing key", {H: "Bearer " + E["FLIGHT_BAD_TOKEN"]}, False),
              ("garbage token", {H: "Bearer not-a-jwt"}, False),
              ("no credentials", {}, False)]


CA = open(E["FLIGHT_TLS_CA"]).read() if E.get("FLIGHT_TLS_CA") else None


def run(kw):
    if CA:
        kw = {**kw, "adbc.flight.sql.client_option.tls_root_certs": CA}
    with flight.connect(E["FLIGHT_URI"], db_kwargs=kw) as conn, conn.cursor() as cur:
        cur.execute("select count(*) from tpch.nation")
        return cur.fetchall()[0][0]


bad = 0
with open(sys.argv[1], "w") as rep:
    for name, kw, ok in cases:
        try:
            got = run(kw)
            res, msg = (got == 25), f"rows={got}"
        except Exception as e:  # noqa: BLE001
            res, msg = (not ok), " ".join(str(e).split())[:160]
            if ok:
                res = False
        res = res if ok else ("rows=" not in msg)
        line = f"{'PASS' if res else 'FAIL'}\t{name}\texpect={'accept' if ok else 'refuse'}\t{msg}"
        print(line)
        rep.write(line + "\n")
        bad += not res
sys.exit(1 if bad else 0)
