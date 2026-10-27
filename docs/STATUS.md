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

CI uses server build **45fc0a9e6e02** (= 775100bf923f + per-query overhead cuts: describe once per views snapshot, parse check once per node, partial-mode sample-file cache, async executionPath log; DuckDB 1.5.6; verified 2026-10-27); 775100bf923f (= 27f583adccd7 + complete mode describes a query once per catalog-views snapshot; 27f583adccd7 = DuckDB 1.5.6 + Kerberos ticket cache; needs DuckDB 1.5.6 extensions — `e2e/server.sh` downloads official httpfs/iceberg/avro v1.5.6; verified 2026-10-27; 57d252b1437f (DuckDB 1.4.5) = 4d707e2aedfc + one outbound byte budget shared by all Flight streams; 4d707e2aedfc = 7fbe2d75827c + S3 connect retry ~6 s; 7fbe2d75827c = 60e888bc26ec + planning with a node down + s3a/s3n roots; default in `e2e/server.sh` and `e2e.yml`; verified 2026-10-26; 4d707e2aedfc, 60e888bc26ec, 20b887839edf, c3b276054cc3, 4eaab052deaf and int7 stay selectable via `server_build`; includes Iceberg time travel `FOR VERSION/TIMESTAMP AS OF`). Open follow-up (additive, no approval needed): forward Iceberg time travel (`FOR VERSION/TIMESTAMP AS OF`) from the Trino connector / StarRocks to the server.

1. **AWS S3 with real credentials**: code is ready (`S3_BACKEND=aws`, workflow input `s3_backend=aws`); waits for the
   maintainer's secrets (see Open questions). Once they exist: dispatch `e2e.yml` with `s3_backend=aws`, check TPC-H
   22/22 and timing, record in the Log.

## Open questions

- AWS S3 test: please add repo secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_TEST_BUCKET`
  (an IAM user limited to that bucket: s3:ListBucket/GetObject/PutObject/DeleteObject). The run uploads SF1 to prefix
  `finch-ci-<run id>/parquet`, uses virtual-hosted style without endpoint, and purges the prefix at the end.
  Untested assumption: the server's `-Ds3UrlStyle=vhost` with no `-Ds3Endpoint` selects AWS endpoint resolution.

- Grafana plugin cannot read DECIMAL/DATE/HUGEINT columns (see docs/GRAFANA.md); the fix would be server-side
  (e.g. an option to send decimals as double / dates as string) or a plugin change. Maintainer: worth a server option?

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
- 2026-10-23 (cloud session 4): CI switched to server int7. Superset route = SQLAlchemy 1.4 + `flightsql-dbapi` dialect
  (`datafusion+flightsql://host:32010?insecure=true&token=<token>`; `import flightsql.sqlalchemy` registers it;
  needs `sqlalchemy<2`): TPC-H 22/22 identical to reference, reflection works (schemas, tables, has_table, get_columns)
  in complete mode (run 39983975369; full 5-client run 39983000136: polars/duckdb 22/22 on int7, sqlalchemy fixed after).
  Superset: SQLAlchemy URI `datafusion+flightsql://<host>:32010?insecure=true&token=<token>` (use `pip install flightsql-dbapi "sqlalchemy<2"`
  in the Superset image; Superset itself not run in CI — it only uses the dialect). `insecure=true` = plaintext gRPC (no TLS).
- 2026-10-23 (cloud session 5): DuckDB `airport` extension — CLOSED, not usable. Probe `e2e/clients/duckdb_airport.py`
  (workflow client `duckdb_airport`; run 40001980109): INSTALL/LOAD/CREATE SECRET/ATTACH succeed, but the first catalog
  call fails: `list_schemas: Unrecognized request` — airport needs servers implementing its own Flight actions
  (list_schemas etc.), not Flight SQL. Needs duckdb<2 (2.0 pulls airport from Query.Farm repo, run 40001545017).
  DuckDB-as-client via ADBC (python_duckdb) remains the supported route.
- 2026-10-23 (cloud session 6): Grafana done — `influxdata-flightsql-datasource` on Grafana 11.3.0, token auth: 22/22 identical
  to reference (run 40027308243, ~3 min; workflow client `grafana`, `e2e/clients/grafana.py`, docs/GRAFANA.md). Plugin quirks:
  query field is `queryText`; DECIMAL/DATE/HUGEINT columns arrive empty -> client casts via DESCRIBE (runs 40025836660 8/22 raw,
  40026980329 21/22 before HUGEINT cast). Probe mode: workflow input `probe`.
- 2026-10-24 (cloud session 7): ODBC item started, not finished. Sandbox cannot reach dremio.com (proxy 403), so driver
  availability must be probed from CI. Added `.github/workflows/odbc-probe.yml` (dispatch only; looks for a Linux
  Arrow Flight SQL ODBC driver: Dremio RPM `/opt/arrow-flight-sql-odbc-driver/lib64/libarrow-odbc.so*`, RedHat-only, v0.9.7;
  `useEncryption=false` needed for plaintext). Run 40043746927 failed in 3 s with no steps and no logs (job 120720560632) —
  looks like an Actions-side problem (minutes/billing exhausted?), not the YAML. Next session: re-dispatch the probe once;
  if it runs, read its output and continue ODBC (rpm2cpio + unixODBC + pyodbc, DSN example in docs).
- 2026-10-24 (cloud session 8): re-dispatched odbc-probe: run 40057271491 failed again in 2 s, 0 steps (job 120762904425). Actions appears blocked repo-wide (billing/minutes?). No progress possible until maintainer fixes it; ODBC stays Next step 1.
- 2026-10-24 (cloud session 9): odbc-probe re-dispatched once more: run 40069230804 failed in 2 s, 0 steps (job 120798864842). Actions still blocked repo-wide; no work possible. Maintainer action needed (see Open questions).
- 2026-10-24 (cloud session 10): odbc-probe dispatched again: run 40080956299 failed instantly (0 steps). Actions still blocked repo-wide; stopped. Maintainer action needed. Suggest not re-dispatching until the maintainer confirms the fix.
- 2026-10-24 (cloud session 11): Actions works again (public repo). ODBC DONE: Dremio Arrow Flight SQL ODBC RPM + unixODBC + pyodbc, metadata OK, TPC-H 22/22 identical (complete mode), run 40121536029 (probe 40121216354); client `odbc` in e2e.yml, docs/ODBC.md. Note: dispatched e2e runs queue behind the push run (concurrency group).
- 2026-10-25 (cloud session 12): ClickHouse — CLOSED, not usable as a client. Probe `clickhouse_probe` in e2e.yml (ClickHouse 26.10.2, `arrowFlight(host:port, dataset[, user, password])`; runs 40145771326, 40145923406, 40146081497). Without credentials: `ARROWFLIGHT_FETCH_SCHEMA_ERROR ... Unauthenticated` (it does not send a Bearer token; only user/password); with `user` + token as password it authenticates but the server answers `Internal` on its schema fetch. The function addresses a plain Flight dataset (descriptor/ticket by name), no SQL statements, so Flight SQL commands are never issued — the server's Flight SQL path does not apply (descriptor type is inferred from this, not captured). ClickHouse as a *server* is out of scope. Probe kept (dispatch only).
- 2026-10-25 (cloud session 13): Ceph RGW DONE as S3 backend: `S3_BACKEND=ceph` in `e2e/server.sh` (workflow input `s3_backend`; `quay.io/ceph/demo:latest-squid`, fixed net 172.30.0.0/24, RGW :8080, user/bucket created via CEPH_DEMO_* env, SF1 loaded with rclone provider=Ceph; server uses path-style, region us-east-1, no config changes). ADBC TPC-H 22/22 identical to reference (run 40157283045; Ceph start+load ~75 s, whole job ~2 min). Differences vs rclone/MinIO: none observed in the server; only setup cost. Not examined: requireChecksums behaviour (no failure seen with defaults).

- 2026-10-25 (cloud session 14): new server build 4eaab052deaf verified: all clients (adbc, pandas, polars, duckdb, sqlalchemy, grafana, odbc; complete mode) green in one run 40179620497 (~4 min); made it the CI default (int7 selectable). No regressions. AWS S3 item not started (dispatch note: `gh api` needs `-f 'inputs[name]=value'`).
- 2026-10-25 (cloud session 15): AWS S3 backend prepared in `e2e/server.sh` (`S3_BACKEND=aws`: vhost style, region, no endpoint, rclone upload to `finch-ci-<run id>`, purge on stop; fails early without secrets) and `localstack` backend (localstack 3.8.1, path-style only — vhost not testable there). LocalStack ADBC run 40192230933 green (TPC-H 22/22 identical). Real AWS run pending secrets.
- 2026-10-25 (cloud session 16): AWS run dispatched to test for secrets: run 40205838839 failed in ~1 min (fails early; secrets presumably still missing, cause not read from logs). Wrote `docs/CLIENTS.md` (table of all clients; Next step 2 done). Next step 1 still waits on secrets.
- 2026-10-25 (cloud session 17): server build c3b276054cc3 verified: all 7 clients (adbc, pandas, polars, duckdb, sqlalchemy, grafana, odbc; complete mode) green in run 40234340287; made it the CI default. AWS item still waits on secrets.
- 2026-10-26 (cloud session 18): server build 20b887839edf verified: all 7 clients (adbc, pandas, polars, duckdb, sqlalchemy, grafana, odbc; complete mode) green in run 40248211118; made it the CI default. Iceberg time travel not exercised: this repo has no Trino/StarRocks/Iceberg client job yet (the forwarding follow-up lives in the server/connector side); candidate future item: an Iceberg time-travel e2e via ADBC. AWS item still waits on secrets.
- 2026-10-26 (cloud session 19): server build 60e888bc26ec (duckDbThreads default 4) verified: all 7 clients (adbc, pandas, polars, duckdb, sqlalchemy, grafana, odbc; complete mode) green in run 40262843972 (~4m20s, same as before: no noticeable timing change at SF1 in CI); made it the CI default. AWS item still waits on secrets.
- 2026-10-26 (cloud session 20): server build 4d707e2aedfc (includes 7fbe2d75827c changes) verified: all 7 clients (complete mode) green in run 40297959260; made it the CI default (7fbe2d75827c was not run separately). AWS item still waits on secrets.
- 2026-10-26 (cloud session 21): server build 57d252b1437f (shared outbound byte budget) verified: all 7 clients (complete mode) green in run 40320927620; made it the CI default. Failover/concurrent-partial-scan checks need a multi-node cluster and are not covered by this repo's single-node CI. AWS item still waits on secrets.
- 2026-10-26 (cloud session 22): nothing actionable — the only open item (AWS S3) still waits on the maintainer's secrets (secret list not readable via the proxy; no re-dispatch, run 40205838839 already showed the early failure). No changes besides this line.
- 2026-10-27 (cloud session 23): AWS run re-dispatched once: run 40442775727 failed again in ~1 min at step "Start S3 and server" (early failure = secrets still missing). Nothing else actionable; no re-dispatch until the maintainer confirms the secrets exist.
- 2026-10-27 (cloud session 24): server build 775100bf923f (DuckDB 1.5.6; includes 27f583adccd7, which was not run separately) verified with official httpfs/iceberg/avro v1.5.6 extensions (`e2e/server.sh` picks v1.5.6 per build): all 7 clients (complete mode) green in run 40460056926 (job ~4m06s; server start 25 s; client phase 4m06s, same as 1.4.5 builds at SF1 — no small-query difference visible in the coarse CI timing); made it the CI default. AWS item still waits on secrets.
- 2026-10-27 (cloud session 25): server build 45fc0a9e6e02 (DuckDB 1.5.6, per-query overhead cuts) verified: all 7 clients (complete mode) green in run 40479236461 (job 4m21s; push run 40479228157 adbc green); made it the CI default (775100bf923f selectable). Coarse CI timing unchanged at SF1. AWS item still waits on secrets.
