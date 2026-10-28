# DuckDB as a client: `adbc_scanner`

Community extension (Query.Farm) that runs SQL on any ADBC driver and returns it as a DuckDB table.

```sql
INSTALL adbc_scanner FROM community; LOAD adbc_scanner;
ATTACH 'grpc://host:32010' AS fl (TYPE adbc,
  driver '/path/to/libadbc_driver_flightsql.so',
  "adbc.flight.sql.authorization_header" 'Bearer <token>');
SELECT * FROM adbc_scan('fl', 'SELECT ... FROM tpch.lineitem');
```

- Driver library: the shared object shipped in the pip package `adbc-driver-flightsql`.
- Server in `resultMode=complete` (arbitrary SQL). Result: TPC-H 22/22 identical to the reference.
- Use DuckDB 1.x (tested 1.5.6). DuckDB 2.0 refuses the community build and points to the Query.Farm repository.
- There is no `adbc_connect()` in the 1.x build; connections are `ATTACH ... (TYPE adbc)` databases.
- Client: `e2e/clients/duckdb_adbc_scanner.py` (CI client `duckdb_adbc_scanner`).
