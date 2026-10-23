import os, adbc_driver_flightsql.dbapi as flight
from adbc_driver_flightsql import DatabaseOptions
hdr = {DatabaseOptions.AUTHORIZATION_HEADER.value: "Bearer " + os.environ["FLIGHT_TOKEN"]}
def run(label, sql, setup=None):
    conn = flight.connect(os.environ["FLIGHT_URI"], db_kwargs=hdr)
    try:
        if setup: setup(conn)
        with conn.cursor() as c:
            c.execute(sql); print("OK  ", label, c.fetchall()[:2])
    except Exception as e:
        print("FAIL", label, " ".join(str(e).split())[:300])
    conn.close()
q4 = open("e2e/queries/q04.sql").read()
run("tpch.lineitem", "select count(*) from tpch.lineitem")
run("bare", "select count(*) from lineitem")
run("USE tpch", "select count(*) from lineitem", lambda c: c.cursor().execute("USE tpch"))
run("schema option", "select count(*) from lineitem", lambda c: c.adbc_connection.set_options(**{"adbc.connection.db.schema": "tpch"}))
run("catalog option", "select count(*) from lineitem", lambda c: c.adbc_connection.set_options(**{"adbc.connection.catalog": "tpch"}))
run("q04 qualified", q4.replace("orders", "tpch.orders").replace("lineitem", "tpch.lineitem"))
run("q04 bare+schema", q4, lambda c: c.adbc_connection.set_options(**{"adbc.connection.db.schema": "tpch"}))
run("exists simple", "select count(*) from tpch.orders o where exists (select 1 from tpch.lineitem l where l.l_orderkey=o.o_orderkey)")
run("from subq", "select count(*) from (select * from tpch.orders) t")
with flight.connect(os.environ["FLIGHT_URI"], db_kwargs=hdr) as c:
    print("objects", str(c.adbc_get_objects(depth="tables").read_all().to_pylist())[:600])
