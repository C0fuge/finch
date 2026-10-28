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
    print("duckdb", duckdb.__version__)
    for r in con.execute("SELECT function_type, function_name, parameters FROM duckdb_functions() WHERE function_name ILIKE '%adbc%'").fetchall():
        print("fn:", r)
    for r in con.execute("SELECT extension_name, extension_version, install_path FROM duckdb_extensions() WHERE extension_name='adbc_scanner'").fetchall():
        print("ext:", r)
    drv, uri = lib, os.environ["FLIGHT_URI"]
    if os.environ.get("FLIGHT_USER"):  # ldap mode: login with user/password over TLS (throwaway cert)
        ca = open(os.environ["FLIGHT_TLS_CA"]).read().replace("'", "''")
        base = "(TYPE adbc, driver '%s', username '%%s', password '%%s', \"adbc.flight.sql.client_option.tls_root_certs\" '%s')" % (drv, ca)
        for label, u, pw, ok in (("bad", os.environ["FLIGHT_BAD_USER"], os.environ["FLIGHT_BAD_PASSWORD"], False),
                                 ("good", os.environ["FLIGHT_USER"], os.environ["FLIGHT_PASSWORD"], True)):
            try:
                con.execute("ATTACH '%s' AS fl %s" % (uri, base % (u, pw)))
                con.execute("SELECT * FROM adbc_scan('fl', 'SELECT 1 AS x')").fetchall()
                got = True
            except Exception as e:  # noqa: BLE001
                got = False
                print("login %s refused: %s" % (label, " ".join(str(e).split()).replace(pw, "***")[:200]))
            if got != ok:
                print("AUTH FAIL: %s credentials %s" % (label, "accepted" if got else "refused"))
                sys.exit(1)
            if not ok:
                try:
                    con.execute("DETACH fl")
                except Exception:  # noqa: BLE001
                    pass
        print("login ok; wrong password refused")
        db = True
    else:
        db = None
            auth = "Bearer " + os.environ["FLIGHT_TOKEN"]
            key = "adbc.flight.sql.authorization_header"
            forms = [
                "(TYPE adbc, driver '%s', \"%s\" '%s')" % (drv, key, auth),
                "(TYPE adbc, driver '%s', headers '%s')" % (drv, auth),
                "(TYPE adbc, driver '%s', authorization_header '%s')" % (drv, auth),
                "(TYPE adbc, driver '%s', token '%s')" % (drv, os.environ["FLIGHT_TOKEN"]),
                "(TYPE adbc, driver '%s', username 'u', password '%s')" % (drv, os.environ["FLIGHT_TOKEN"]),
            ]
            for f in forms:
                try:
                    con.execute("ATTACH '%s' AS fl %s" % (uri, f))
                    r = con.execute("SELECT * FROM adbc_scan('fl', 'SELECT 1 AS x')").fetchall()
                    print("FORM OK:", f.replace(auth, "***").replace(os.environ["FLIGHT_TOKEN"], "***")[:120], r)
                    db = f
                    break
                except Exception as e:  # noqa: BLE001
                    m = " ".join(str(e).split()).replace(auth, "***").replace(os.environ["FLIGHT_TOKEN"], "***")
                    print("FORM FAIL:", f.replace(auth, "***").replace(os.environ["FLIGHT_TOKEN"], "***")[-60:], "->", m[:350])
                    try:
                        con.execute("DETACH fl")
                    except Exception:  # noqa: BLE001
                        pass
    if db is None:
        sys.exit(1)
    for name in sorted(f[:-4] for f in os.listdir(qdir) if f.endswith(".sql")):
        sql = open(os.path.join(qdir, name + ".sql"), encoding="utf-8").read().strip().rstrip(";")
        try:
            lit = "'" + sql.replace("'", "''") + "'"
            rows = con.execute("SELECT * FROM adbc_scan('fl', %s)" % lit).fetchall()
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
