# Metabase (generic Flight SQL driver)

Driver: [J0hnG4lt/metabase-flightsql-driver](https://github.com/J0hnG4lt/metabase-flightsql-driver) (Apache-2.0), one jar
`arrow-flight-sql.metabase-driver.jar` (bundles the Arrow Flight SQL JDBC driver). Tested with `metabase/metabase:v0.64.2.9`.
CI: `e2e.yml`, client `metabase` (`e2e/clients/metabase.py`); server in `resultMode=complete`.

## Setup

1. Put the jar into the Metabase plugins directory. In the container `/plugins` must be **writable for the container
   user** (otherwise: "Metabase does not have permissions to write to plugins directory" and the driver is silently
   not loaded: `engine: value must be a valid database engine`).
2. JDK 25 images need `JAVA_OPTS="--add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED
   --sun-misc-unsafe-memory-access=allow --enable-native-access=ALL-UNNAMED -Dio.netty.tryReflectionSetAccessible=true"`.
3. Add the database (UI "Arrow Flight SQL", or `POST /api/database`):
   `{"engine":"arrow-flight-sql","details":{"host":"flight-server","port":32010,"token":"<FLIGHT_AUTH_TOKEN>","useEncryption":false}}`
   (`useEncryption=true` for TLS).

## What works (CI)

- Connection, metadata sync (schemas `tpch`, `main`, `types`; tables and columns), field classification.
- Native SQL: TPC-H 22/22 identical to the reference (DECIMAL, DATE, BIGINT/HUGEINT come back correctly).
- GUI-style (MBQL) questions on `tpch.lineitem`: count, filter + sum, group-by + count equal the equivalent native SQL.
- Native query with a field filter (template tag bound to a field): see the result in `docs/STATUS.md` Log.

## Known gaps / notes

- `/api/dataset` returns at most 2000 rows (Metabase limit, not the server); the test client uses the CSV export for
  larger results (q16: 18314 rows).
- Metabase qualifies columns in field filters (`"tpch"."lineitem"."col"`), so a field-filter query must not alias the table.
- No fork of the driver (DuckDB dialect) was needed for the tested features.
