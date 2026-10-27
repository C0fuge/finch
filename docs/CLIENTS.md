# Clients

All results are compared to `e2e/reference/sf1` (TPC-H SF1, decimals rounded to 4 places, rows sorted unless
ORDER BY). CI: workflow `e2e.yml`, input `clients`; server build `4eaab052deaf`.

Common to all clients: server port 32010; auth `FLIGHT_AUTH_PROVIDER=token FLIGHT_AUTH_TOKEN=<t>` (Bearer `<t>` or
Basic user:`<t>`) or `FLIGHT_ALLOW_INSECURE=true`; plaintext gRPC in CI (no TLS).

**Result mode.** Default `partial` accepts only single-table `schema.table` SELECTs (no joins). Generic clients
that send arbitrary SQL need `-DresultMode=complete` (full DuckDB SQL, bare table names allowed). All CI runs
below use `complete`.

| Client | Install | Connection | Auth | CI (TPC-H) | Notes |
|---|---|---|---|---|---|
| Python ADBC | `pip install adbc-driver-flightsql pyarrow` | `grpc://host:32010` | header `authorization: Bearer <t>` | 22/22 | `e2e/clients/python_adbc.py` |
| pandas | + `pandas` | `read_sql` over ADBC DBAPI | as ADBC | 22/22 | `e2e/clients/python_df.py` |
| polars | + `polars` | `read_database` over ADBC | as ADBC | 22/22 | same script |
| DuckDB | + `duckdb<2` | ADBC Arrow table scanned by DuckDB | as ADBC | 22/22 | `airport` extension does NOT work (needs its own Flight actions) |
| SQLAlchemy / Superset | `pip install flightsql-dbapi "sqlalchemy<2"` | `datafusion+flightsql://host:32010?insecure=true&token=<t>` | `token=` in URI | 22/22 + reflection | `import flightsql.sqlalchemy`; Superset itself not run in CI |
| Superset (ADBC dialect) | `superset-sqlalchemy-gizmosql-adbc-dialect` in `apache/superset:6.0.0` | `gizmosql://user:<t>@host:32010` | basic auth (token as password) | 22/22 + dataset/chart | needs dialect patch for 2 server behaviours, see docs/SUPERSET.md |
| Grafana | plugin `influxdata-flightsql-datasource` (11.3.0) | host:32010, token auth | token | 22/22 | DECIMAL/DATE/HUGEINT arrive empty: cast in the query; see `GRAFANA.md` |
| ODBC | Dremio Arrow Flight SQL ODBC (RPM) + unixODBC | DSN, `useEncryption=false` | token | 22/22 | see `ODBC.md` |
| Metabase | driver jar `arrow-flight-sql.metabase-driver.jar` (J0hnG4lt/metabase-flightsql-driver) in `metabase/metabase:v0.64.2.9` | engine `arrow-flight-sql`, host/port, `useEncryption=false` | `token` field | 22/22 + MBQL | see `METABASE.md` |
| JDBC, Trino, StarRocks | Arrow Flight SQL JDBC 27/2; Trino plugin; StarRocks connector | — | — | proven in the server's own suite | not in this repo's CI |
| ClickHouse | — | `arrowFlight()` | — | not usable | plain Flight datasets only, no SQL; does not send Bearer |

S3 backends (server data dir): rclone S3 (default), Ceph RGW (`s3_backend=ceph`), LocalStack
(`localstack`), AWS (`aws`, needs repo secrets — see `STATUS.md`).
