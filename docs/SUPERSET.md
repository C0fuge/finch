# Apache Superset

Superset 6.0.0 (`apache/superset`) with the ADBC-based dialect `superset-sqlalchemy-gizmosql-adbc-dialect`
(Apache-2.0, installed with pip into the Superset venv). Replaces the archived `flightsql-dbapi` path
(still its own row: `python_sqlalchemy`, see CLIENTS.md).

## Setup

- Image: `e2e/superset/Dockerfile` (pip install + `patch_dialect.py`); config `e2e/superset/superset_config.py`
  (CSRF off for the API test, big row limits).
- SQLAlchemy URI: `gizmosql://<user>:<token>@<host>:32010` — user is arbitrary, the password is the server token
  (ADBC basic auth, accepted by the server). Plaintext gRPC is the default; add `?useEncryption=true` for TLS.

## What works (CI run 40602735841, `clients=superset`)

- Add database through the REST API, SQL Lab (sync) executes all 22 TPC-H queries: identical to the reference.
- Dataset on `tpch.lineitem` + chart-data query (group by / count) equals native SQL; chart saved.
- Large result (q16, 18314 rows) fine with `queryLimit` raised.

## Known gaps (needs the patch in `patch_dialect.py`)

1. The dialect rejects servers whose ADBC `vendor_version` does not start with `duckdb ` — our server reports `0.0.1`
   ("Unsupported GizmoSQL server backend"). Server-side fix: report e.g. `duckdb v1.5.6`.
2. The dialect sends `ROLLBACK`/`BEGIN`/`COMMIT` as statements; the server answers "Only queries are allowed, not
   ROLLBACK". The patch makes them no-ops. Server-side fix: accept (ignore) transaction statements, or the
   Flight SQL `EndTransaction` path.
Without the patch the database cannot even be added (errors surface as `'Engine' object has no attribute 'cursor'`
or the ROLLBACK error).
