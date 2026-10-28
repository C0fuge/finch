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

> **Maintainer, 2026-10-28 15:00 - native first.** For every tool, prefer and test its native Arrow Flight / ADBC path
> over JDBC/ODBC; where a tool has both, add a speed row (same query set: TPC-H SF1 total and a 1M-row export) native vs
> JDBC so the gain is visible. Mark JDBC-only tools as such in the README matrix.

> **Server build `server-1.0.0-a9e43ca5e296` is in the assets** (2026-10-28, local coordinator; jar, plugins tar, libs tar +
> merged `SHA256SUMS` in `e2e-assets`; same DuckDB 1.5.6 extension set). The LDAP/JWT providers for C1 are the server
> release asset `flight-auth-...tar.zst`, not in `e2e-assets`.

> **Maintainer, 2026-10-28 14:30: next client pack (C1-C6), take in order.** A new server build `a9e43ca5e296` is being
> uploaded to the assets (adds LDAP/AD and JWT login, Hive ORC and text tables, size-aware DuckDB threads/memory, opt-in
> distributed complete mode); make it the default if the suite is green.
> - C1. **Login rows for every client that can send user/password or a bearer token** (JDBC, ODBC, ADBC Go/C++/Python,
>   pyarrow, Metabase, Superset, Grafana, DuckDB adbc_scanner): server with the LDAP provider against an OpenLDAP container
>   and with the JWT provider against a local JWKS; positive + wrong password / expired token rows. Doc `docs/AUTH.md`.
> - C2. **More language clients:** R (`adbcflightsql` / `arrow`), Go (ADBC Flight SQL driver directly), Rust
>   (`arrow-flight` crate Flight SQL client), .NET (`Apache.Arrow.Flight.Sql` / ADBC), Node.js (if a maintained Flight SQL
>   client exists). TPC-H 22/22 identical per client, or a clear "not usable: why" row.
> - C3. **Dataframe tools:** Polars (`read_database` via ADBC), pandas (`adbc` + `read_sql`), Ibis (if it has a Flight SQL
>   backend), Jupyter notebook smoke (nbconvert run) - answers checked.
> - C4. **dbt:** check whether a maintained adapter can run against Flight SQL (e.g. via ADBC); if none, a "not usable"
>   row with the reason.
> - C5. **Tableau / Power BI docs:** setup docs with the JDBC driver and the official ODBC driver (no CI possible), plus a
>   TDC/connector-file template if useful.
> - C6. **ClickHouse row** as soon as a server build has plain-Flight command descriptors (server plugins lane P5).

> **Server build `cadd1aca9c23`** is verified and the CI default (2026-10-28, see Log). **Compressed-stream rows: ADBC (Python/Go driver), pyarrow.flight and Java Flight zstd+lz4 DONE 2026-10-28; ADBC C++ closed (the ADBC Flight SQL driver is Go; the C++ Flight client is what pyarrow uses). Still open: proof from the server log that frames were really compressed (needs a server-side per-stream log line).** Opt-in
> result stream compression ZSTD/LZ4 (client asks via call header or Flight SQL session option `arrow-compression`; no default
> or wire change for clients that do not ask). Add rows (`zstd` and `lz4`, same answers as plain) for the clients that support
> it: pyarrow, ADBC Go and C++ (call header `arrow-compression`), Java Flight with `arrow-compression` (+ `zstd-jni`;
> `commons-compress` for lz4); stock JDBC/ODBC drivers must not ask. Also still available: opt-in S3 read cache
> `arrowflight.s3.cacheMegabytes`, `flightCompressionThreads`.


> **Maintainer, 2026-10-28: BI and tools pack - take these before item 1 (which waits for secrets).** Basis: the
> maintainer's integration research. Each: a CI job against our server (same build as the e2e jobs), answers checked
> against the reference, a short doc `docs/<TOOL>.md` (setup, what works, known gaps), matrix row in README.
> - B1. **Metabase**: DONE 2026-10-27 (see Log, `docs/METABASE.md`).
> - B2. **DONE 2026-10-27** (see Log, `docs/SUPERSET.md`). Was: **Superset / SQLAlchemy**: replace the archived `flightsql-dbapi` path with an ADBC-based dialect
>   (gizmodata/sqlalchemy-gizmosql-adbc-dialect, superset-sqlalchemy-gizmosql-adbc-dialect, Apache-2.0); run a real
>   `apache/superset` container: add database, SQL Lab query, one chart via API. Keep the old path as a separate row.
> - B3. **DONE 2026-10-28** (see Log, `docs/ODBC.md`). Was: **ODBC**: official Apache Arrow Flight SQL ODBC driver; Dremio row kept.
> - B4. **DONE 2026-10-28** (see Log, `docs/JDBC_METADATA.md`). Was: **DBeaver / DataGrip metadata conformance**: a JDBC `DatabaseMetaData` test (catalogs, schemas, tables, columns,
>   types, PK/FK empty, SqlInfo) as those tools call it; list gaps as server issues.
> - B5. **DuckDB `adbc_scanner` DONE 2026-10-28 (see Log, `docs/DUCKDB_ADBC.md`); airport/ClickHouse closed earlier (ClickHouse still waits for P5).** Was: **DuckDB as a client** (`adbc` / `adbc_scanner` community extension or Query.Farm `airport`) and **ClickHouse**
>   (`arrowFlight` table function): add rows; ClickHouse needs the server's plain-Flight command support (server repo,
>   plugins lane P5) - mark it "waits for P5" until a build has it.
> - B6. **DONE 2026-10-28** (see Log, `docs/GRAFANA.md`). Was: **Grafana**: keep the archived influx plugin row; add a row for the maintained fork
>   gizmodata/grafana-gizmosql-datasource and check DECIMAL/DATE/HUGEINT (known empty in the influx plugin).

CI uses server build **a9e43ca5e296** (DuckDB 1.5.6; LDAP/JWT login, Hive ORC/text, distributed complete opt-in; verified 2026-10-28); previous default **cadd1aca9c23** (selectable); earlier: 45fc0a9e6e02 (DuckDB 1.5.6); **45fc0a9e6e02** (= 775100bf923f + per-query overhead cuts: describe once per views snapshot, parse check once per node, partial-mode sample-file cache, async executionPath log; DuckDB 1.5.6; verified 2026-10-27); 775100bf923f (= 27f583adccd7 + complete mode describes a query once per catalog-views snapshot; 27f583adccd7 = DuckDB 1.5.6 + Kerberos ticket cache; needs DuckDB 1.5.6 extensions — `e2e/server.sh` downloads official httpfs/iceberg/avro v1.5.6; verified 2026-10-27; 57d252b1437f (DuckDB 1.4.5) = 4d707e2aedfc + one outbound byte budget shared by all Flight streams; 4d707e2aedfc = 7fbe2d75827c + S3 connect retry ~6 s; 7fbe2d75827c = 60e888bc26ec + planning with a node down + s3a/s3n roots; default in `e2e/server.sh` and `e2e.yml`; verified 2026-10-26; 4d707e2aedfc, 60e888bc26ec, 20b887839edf, c3b276054cc3, 4eaab052deaf and int7 stay selectable via `server_build`; includes Iceberg time travel `FOR VERSION/TIMESTAMP AS OF`). Open follow-up (additive, no approval needed): forward Iceberg time travel (`FOR VERSION/TIMESTAMP AS OF`) from the Trino connector / StarRocks to the server.

1. **AWS S3 with real credentials**: code is ready (`S3_BACKEND=aws`, workflow input `s3_backend=aws`); waits for the
   maintainer's secrets (see Open questions). Once they exist: dispatch `e2e.yml` with `s3_backend=aws`, check TPC-H
   22/22 and timing, record in the Log.

> **C1 status (2026-10-28, session 42):** LDAP proven for ADBC Python (login 22/22 + refusals, `docs/AUTH.md`, TLS throwaway cert).
> Session 43: pyarrow.flight and JDBC LDAP rows DONE. Session 46: Metabase LDAP row DONE. Session 44: ODBC (Apache) LDAP row DONE. Session 45: DuckDB adbc_scanner LDAP row DONE. Remaining C1: JWT (blocked by server bug, Open questions); LDAP rows for
> Superset, Grafana - take them in that order, then C2-C6.


- C1 JWT: server bug - `FLIGHT_JWT_AUDIENCE` set -> NPE at start in `JwtVerifier` (immutable `Set.of(audience)`, nimbus calls `contains(null)`); unset -> refused (required). Server repo fix: use a `HashSet` for the audiences. Maintainer: please forward. (TLS question resolved: CI uses a throwaway cert; `FLIGHT_ALLOW_INSECURE` not used.)

- JDBC metadata gaps (B4, docs/JDBC_METADATA.md): server should report standard SqlInfo (transactions, group by, joins, isolation...) — the JDBC driver NPEs otherwise —, and fill getTypeInfo/keywords. Maintainer: file as server issues?

- AWS S3 test: please add repo secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_TEST_BUCKET`
  (an IAM user limited to that bucket: s3:ListBucket/GetObject/PutObject/DeleteObject). The run uploads SF1 to prefix
  `finch-ci-<run id>/parquet`, uses virtual-hosted style without endpoint, and purges the prefix at the end.
  Untested assumption: the server's `-Ds3UrlStyle=vhost` with no `-Ds3Endpoint` selects AWS endpoint resolution.

- (resolved by the fork plugin, B6; influx plugin only) Grafana plugin cannot read DECIMAL/DATE/HUGEINT columns (see docs/GRAFANA.md); the fix would be server-side
  (e.g. an option to send decimals as double / dates as string) or a plugin change. Maintainer: worth a server option?

- (answered) Table names: partial mode needs `schema.table` and accepts only single-table SELECTs (joins/most FROM-subqueries rejected: "Can only select from ONE table"); complete mode runs full DuckDB SQL, bare names allowed, but `tpch.` prefix also works. Joins in partial mode are expected to be done by the client engine (Trino). Maintainer: confirm that generic clients are meant to use `resultMode=complete` for arbitrary SQL.
- (old) Which table-name form does the server expect from generic clients (`tpch.lineitem`, or a session schema)? The
  maintainer's Trino plugin uses schema `tpch`; ADBC with prefix `tpch.` failed on 20/22 queries.

- Superset dialect (B2) needs server changes to run unpatched: ADBC `vendor_version` should start with `duckdb ` (currently `0.0.1`), and transaction statements (ROLLBACK/BEGIN/COMMIT) should be accepted as no-ops. Maintainer: worth doing in the server repo?

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
- 2026-10-27 (cloud session 26): nothing actionable — AWS S3 item still waits on the maintainer's secrets; no re-dispatch. No changes besides this line.
- 2026-10-27 (cloud session 27): nothing actionable — AWS S3 item still waits on the maintainer's secrets; no re-dispatch. No changes besides this line.
- 2026-10-27 (cloud session 28): nothing actionable — AWS S3 item still waits on the maintainer's secrets; no re-dispatch. No changes besides this line.
- 2026-10-27 (cloud session 29): B1 Metabase DONE. Driver J0hnG4lt/metabase-flightsql-driver (latest release jar) in `metabase/metabase:v0.64.2.9`: add database via API (token auth), metadata sync, TPC-H 22/22 identical (native), MBQL count/filter+sum/group-by equal native SQL, native field filter OK — run 40588680869 (client `metabase` in e2e.yml, `e2e/clients/metabase.py`, `docs/METABASE.md`, CLIENTS row). Pitfalls found: `/plugins` must be writable for the container user (else driver silently not loaded); `/api/dataset` caps at 2000 rows (q16 via CSV export); field filters need an un-aliased table. No driver fork needed. Next: B2 (Superset).
- 2026-10-27 (cloud session 30): B2 Superset DONE. `apache/superset:6.0.0` + superset-sqlalchemy-gizmosql-adbc-dialect: add database, SQL Lab TPC-H 22/22 identical, dataset + chart-data equal native SQL — run 40602735841 (client `superset` in e2e.yml, `e2e/clients/superset.py`, `e2e/superset/`, `docs/SUPERSET.md`, CLIENTS row). Needs a small dialect patch for two server behaviours (vendor_version `0.0.1` instead of `duckdb ...`; ROLLBACK/BEGIN/COMMIT rejected as non-queries) — see Open questions. Next: B3 (ODBC official driver).
- 2026-10-28 (cloud session 31): B3 ODBC DONE. Official Apache Arrow Flight SQL ODBC 26.0.0 (el9 RPM from apache.jfrog.io, unpacked with rpm2cpio; extra runtime libs liburiparser1/libre2/libutf8proc via apt + symlinks) + unixODBC + pyodbc: metadata OK, TPC-H 22/22 identical, run 40610392211 together with the Dremio driver (clients `odbc_apache odbc`; probe run 40609911205). Helper workflow `odbc-apache-probe.yml` (dispatch only) lists Arrow packages. Pitfall: dispatched e2e runs get cancelled by a pending push run (concurrency group). Next: B4 (DBeaver/DataGrip metadata conformance).
- 2026-10-28 (cloud session 32): B4 JDBC metadata DONE. Client `jdbc_meta` (`e2e/jdbc/MetaConformance.java`, driver 18.3.0 from Maven Central, runs with the source launcher): run 40614144465 green, 0 FAIL, 8 GAPs (missing SqlInfo -> driver NPE, empty getTypeInfo/keywords/functions, no remarks); first run 40613669218 failed on the NPE before the check was made per-method. Doc `docs/JDBC_METADATA.md`, CLIENTS row. Next: B5 (DuckDB adbc/airport client + ClickHouse; both previously probed - airport and ClickHouse arrowFlight closed in sessions 5 and 12, so B5 is mostly the `adbc_scanner` community extension; check it).
- 2026-10-28 (cloud session 33): server build cadd1aca9c23 verified and made the CI default (`e2e/server.sh`, `e2e.yml`; 1.5.6 extension set): all 11 clients (adbc, pandas, polars, duckdb, sqlalchemy, grafana, odbc, odbc_apache, metabase, superset, jdbc_meta; complete mode) green in run 40625378574 (job 6m26s, server start 29 s, clients 5m44s). Compressed-stream rows not started (see Next steps). B5 (adbc_scanner) still open after that.
- 2026-10-28 (cloud session 34): compressed-stream rows for ADBC (python_adbc_zstd, python_adbc_lz4; call header `arrow-compression` via `adbc.flight.sql.rpc.call_header.arrow-compression`, env FLIGHT_COMPRESSION in `e2e/clients/python_adbc.py`): TPC-H 22/22 identical to reference with plain, zstd and lz4 in run 40636578980 (3m). Not proven: that the server really sent compressed frames (no server-log check yet; job log was not conclusive). pyarrow/C++/Java Flight rows and B5 remain open.
- 2026-10-28 (cloud session 35): pyarrow.flight rows `pyarrow_flight`, `pyarrow_flight_zstd`, `pyarrow_flight_lz4` (`e2e/clients/python_pyarrow_flight.py`: hand-built Flight SQL CommandStatementQuery, header `arrow-compression`, reads all endpoints): TPC-H 22/22 identical for all three, run 40644285328 (~2.5 min). Server log only shows the startup line "Flight stream compression: default NONE (clients choose with the arrow-compression header)" - no per-stream log, so wire compression is still not proven from the server side (ask maintainer for a per-stream/debug log line or a counter). Next: ADBC C++ / Java Flight rows, then B5 (adbc_scanner).
- 2026-10-28 (cloud session 36): Java Flight rows `java_flight`, `java_flight_zstd`, `java_flight_lz4` (`e2e/java-flight/JavaFlight.java`, FlightSqlClient 18.3.0 + arrow-compression, zstd-jni, commons-compress via `e2e/java-flight/pom.xml`; header `arrow-compression`, all endpoints read): TPC-H 22/22 identical for all three, run 40648571065 (clients ~1.5 min). Job shows red only because the final upload-artifact step failed (`ENOTFOUND`, Actions infrastructure), not the clients. Wire compression still not proven server-side. Next: ADBC C++ row (if a C++ driver is installable in CI, e.g. via conda/apt; else close), then B5 (adbc_scanner).
- 2026-10-28 (cloud session 37): B5 DuckDB `adbc_scanner` DONE: client `duckdb_adbc_scanner`, TPC-H 22/22 identical, run 40663958686 (earlier runs 40662645537, 40662989360, 40663309099, 40663639118 were API discovery: needs `duckdb<2`, no `adbc_connect`, `ATTACH ... (TYPE adbc, driver ..., "adbc.flight.sql.authorization_header" ...)` + `adbc_scan`). `docs/DUCKDB_ADBC.md`, CLIENTS row. ADBC C++ row closed (no separate C++ ADBC driver; C++ Flight covered via pyarrow). Next: B6 (Grafana maintained fork gizmodata/grafana-gizmosql-datasource).
- 2026-10-28 (cloud session 38): B6 Grafana fork DONE: `gizmodata-gizmosql-datasource` (latest release zip, unsigned plugin) client `grafana_gizmosql`, TPC-H 22/22 identical with no casts (DECIMAL/DATE/HUGEINT fine), run 40672712545; docs/GRAFANA.md, CLIENTS row. BI pack B1-B6 complete. Remaining: compressed-stream server-side proof (needs server log line), AWS S3 (secrets).
- 2026-10-28 (cloud session 39): nothing actionable — no new server build in the release (newest cadd1aca9c23), compressed-stream server-side proof needs a server log line, AWS S3 item still waits on the maintainer's secrets; no re-dispatch. No changes besides this line.
- 2026-10-28 (cloud session 40): server build a9e43ca5e296 verified and made the CI default: 20 clients green (complete mode) — run 40695391444 (15 clients OK, then failed only because container `grafana` still held port 3000 for `grafana_gizmosql`; fixed by `docker rm -f grafana`) + run 40696574164 (grafana, grafana_gizmosql, odbc, odbc_apache, metabase, superset, jdbc_meta, duckdb_adbc_scanner all green). Next: C1 (login rows; LDAP/JWT providers are in asset `flight-auth-1.0.0-a9e43ca5e296.tar.zst`), then C2-C6; native-first rule applies.
- 2026-10-28 (cloud session 41): C1 started, not finished. Added `AUTH_MODE=ldap|jwt` to `e2e/server.sh` (flight-auth tar from assets on the classpath; OpenLDAP test container `ghcr.io/rroemhild/docker-test-openldap` with search-mode config, or a local JWKS file via `e2e/jwt_keys.py` with good/expired/wrong-key tokens), workflow input `auth_mode`, client `auth_check` (`e2e/clients/auth_check.py`: good credential works, wrong password/unknown user/expired/wrong key/garbage/no credentials refused) and user/password login in `python_adbc.py`. Provider env names are in the jars (FLIGHT_LDAP_*, FLIGHT_JWT_*; JWKS URL must be https, so a JWKS *file* is used; LDAP needs FLIGHT_LDAP_SESSION_SECRET, base64 >= 32 bytes). Runs 40715075120 (missing session secret) and 40715537498 (providers require TLS) failed at server start; see Open questions. Next: fix the TLS point, run `python_adbc auth_check` for ldap and jwt, then the other clients.
- 2026-10-28 (cloud session 42): C1 partial. TLS route for the ldap/jwt modes (throwaway cert in `e2e/server.sh`, ADBC clients trust it via `FLIGHT_TLS_CA`). LDAP: ADBC Python 22/22 + `auth_check` PASS (login ok; wrong password, unknown user, no credentials refused) - run 40729632840. JWT: server NPE in `JwtVerifier` with audience set, audience required (runs 40730237858, 40730519233); `docs/AUTH.md`. Next: LDAP rows for the other clients, then C2.
- 2026-10-28 (cloud session 43): C1 LDAP rows for pyarrow.flight (handshake login via `authenticate_basic_token`, TLS root cert; TPC-H 22/22 identical) and JDBC (`jdbc_meta`: user/password URL, JKS truststore from the throwaway cert, `useSystemTrustStore=false` is required or the trustStore is ignored; wrong password refused, 0 FAIL) - run 40734590031 green (first run 40734261638 failed on the truststore point). Next: LDAP rows for ODBC, duckdb_adbc_scanner, Metabase, Superset, Grafana; JWT waits for the server fix.
- 2026-10-28 (cloud session 44): C1 LDAP row for ODBC (official Apache driver, UID/PWD over TLS with `trustedCerts`; `e2e/clients/odbc.py`): TPC-H 22/22 identical, wrong password refused - run 40755018981 (`auth_mode=ldap clients=odbc_apache`), docs/AUTH.md. Next: LDAP rows for duckdb_adbc_scanner, Metabase, Superset, Grafana; JWT waits for the server fix.
- 2026-10-28 (cloud session 45): C1 LDAP row for DuckDB `adbc_scanner` (username/password + `tls_root_certs` ATTACH options; TPC-H 22/22 identical, wrong password refused) - run 40770269011, docs/AUTH.md. Next: LDAP rows for Metabase, Superset, Grafana; JWT waits for the server fix.
- 2026-10-28 (session 46): C1 Metabase LDAP row DONE (TLS + custom CA, wrong password refused, sync, TPC-H 22/22, MBQL + field filter OK; run 40780371612, docs/AUTH.md). Next: Superset LDAP, then Grafana LDAP.
