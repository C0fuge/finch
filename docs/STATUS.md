# Status

## Context

- Server: release `e2e-assets` → `arrow-flight-server-1.0.0-int6b.jar` (DuckDB 1.4.5; plugins s3/lakefs/iceberg/hive
  in `int6b-plugins.tar.zst` with **START-NOTES.txt — how to start it**), `flight-server-libs.tar.zst` (`libs/` on the
  classpath), `test-data-sf1-types.tar.zst` (`sf1/tpch/<table>/*.parquet`, `types/<table>/*.parquet`).
- Proven CI recipe for the server (copy it): copy of the Trino repo CI script in `e2e/from-trino-repo/` (run-e2e.sh, compare.py) — reuse it — S3 via
  `rclone serve s3` (MinIO images/binaries are no longer anonymously available), JDK 21, `LANG=C.UTF-8`, writable cwd
  (DuckDB temp dir), `-cp "<jar>:libs/*" pro.surpin.data.arrowflight.server.HadoopArrowFlightServer --localhost <h>
  --hosts <h>`, `-DdataDir=s3://lake/parquet -Ds3Endpoint=http://<s3>:9000 -Darrowflight.plugins.dir=<dir>/plugins`,
  httpfs v1.4.5 (`http://extensions.duckdb.org/v1.4.5/linux_amd64/httpfs.duckdb_extension.gz`, keep the file name
  `httpfs.duckdb_extension`, or `-Darrowflight.duckdb.extensionDir`), S3 creds via `FLIGHT_S3_ACCESS_KEY` /
  `FLIGHT_S3_SECRET_KEY`, auth `FLIGHT_AUTH_PROVIDER=token FLIGHT_AUTH_TOKEN=<t>` (Bearer `<t>` or Basic user:`<t>`)
  or `FLIGHT_ALLOW_INSECURE=true`, port 32010, `-DresultMode=partial|complete` (default partial: one endpoint per
  node; most generic Flight SQL clients just read all endpoints — check that they do!).
- Already proven elsewhere: JDBC (Arrow Flight SQL JDBC driver; stock driver 27/2 in our suite), Trino plugin,
  StarRocks connector, Python ADBC.

## Next steps (one per session; small and finished)

1. **Superset / SQLAlchemy**: dialect route (`flightsql-dbapi` or an ADBC-based dialect): `SELECT` +
   `has_table`/`get_columns` reflection; document a Superset connection string. Token auth, `resultMode=complete`.
2. **DuckDB as a client**: community extension `airport` (Arrow Flight client for DuckDB): can it query a Flight SQL
   server like ours (it targets "airport" servers — check)? If yes: e2e + docs; if not: record why in STATUS and
   close.
3. **Grafana**: the Flight SQL datasource plugin (`influxdata-flightsql-datasource`) against our server in CI
   (Grafana container, provisioned datasource, query via the HTTP API `/api/ds/query`): results equal the reference
   for a few queries, token auth; docs.
4. **ODBC** (Tableau / Power BI / Excel route): Apache Arrow Flight SQL ODBC driver (Dremio's / Arrow's) on Linux
   with unixODBC + `isql`/pyodbc: connect, metadata, TPC-H subset; docs (DSN example). If no Linux build is
   obtainable, record it and close.
5. **ClickHouse**: recent ClickHouse has an Arrow Flight table function/engine — check whether it speaks Flight SQL
   to an arbitrary server (ticket/command flow); if yes e2e + docs, else record and close.
6. **Ceph RGW as the S3 backend**: run Ceph RGW in CI (e.g. `quay.io/ceph/demo` or a single-node `cephadm`-free
   setup), load SF1, point the server's S3 plugin at it (path-style, region), TPC-H 22/22 via one client (JDBC or
   ADBC), check the server's S3 checksum/requireChecksums behaviour, list differences from MinIO.
7. **AWS S3 as the S3 backend**: prepare a workflow that runs only when the maintainer adds secrets
   (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_TEST_BUCKET`): upload SF1 to a prefix, run the
   server against real S3 (virtual-hosted style, region, no custom endpoint), TPC-H 22/22, measure, delete the prefix.
   Until secrets exist: test the same code path against LocalStack and write the instructions in Open questions.
8. **Docs**: `docs/CLIENTS.md` — one section per client: install, connection string / config, auth, result-mode
   notes, known limits, CI status.

## Open questions

- (answered) Table names: partial mode needs `schema.table` and accepts only single-table SELECTs (joins/most FROM-subqueries rejected: "Can only select from ONE table"); complete mode runs full DuckDB SQL, bare names allowed, but `tpch.` prefix also works. Joins in partial mode are expected to be done by the client engine (Trino). Maintainer: confirm that generic clients are meant to use `resultMode=complete` for arbitrary SQL.
- (old) Which table-name form does the server expect from generic clients (`tpch.lineitem`, or a session schema)? The
  maintainer's Trino plugin uses schema `tpch`; ADBC with prefix `tpch.` failed on 20/22 queries.

## Log

- 2026-10-23 (maintainer's local session): repo created; reference data and backlog added; assets uploaded.
- 2026-10-23 (cloud session): CI skeleton added (workflow `e2e.yml`, `e2e/server.sh`, `e2e/compare.py`, ADBC client).
  Run 39949263918 (~2 min): assets download, rclone S3, server with token auth and ADBC bearer auth all work;
  2/22 OK (q01, q06 identical to the reference); others fail in Prepare (table-name / FROM-subquery restrictions).
  Note: `gh api .../logs` is blocked by the proxy; use the MCP `get_job_logs` tool.
- 2026-10-23 (cloud session 2): ADBC 22/22 identical to reference with `result_mode=complete` (run 39951878169, ~2 min). Partial mode (run 39951727707): only q01/q06 (+simple subquery) work; server rejects multi-table queries by design. Probe script `e2e/clients/probe.py` kept (not in workflow).
- 2026-10-23 (cloud session 3): pandas (`read_sql`), polars (`read_database`) and DuckDB (ADBC Arrow table scanned by DuckDB) via
  `e2e/clients/python_df.py`: 22/22 identical to reference in complete mode (run 39976693143, all three, ~3 min).
  Partial mode for these clients is not applicable: the server rejects multi-table SQL by design (see Open questions);
  default push run 39976694757 (partial) fails accordingly — consider making the workflow default `complete`.
