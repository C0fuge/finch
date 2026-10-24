# ODBC (Tableau / Power BI / Excel route)

Driver: Dremio's Arrow Flight SQL ODBC driver (Linux RPM, v0.9.x), which speaks plain Flight SQL.
Download: `https://download.dremio.com/arrow-flight-sql-odbc-driver/arrow-flight-sql-odbc-driver-LATEST.x86_64.rpm`
(Windows: `arrow-flight-sql-odbc-LATEST-win64.msi`; Apache Arrow 26.0.0 also ships a win64 MSI).

CI (`e2e.yml`, client `odbc`, `e2e/clients/odbc.py`): unixODBC + pyodbc, RPM unpacked with `rpm2cpio`.
Result: TPC-H 22/22 identical to the reference in `resultMode=complete` (run 40121536029); metadata works
(`SQLTables` lists `tpch.*`/`types.*`, `SQLColumns` returns names and types).

## Linux config

`odbcinst.ini`:
```
[Arrow Flight SQL ODBC Driver]
Driver=/opt/arrow-flight-sql-odbc-driver/lib64/libarrow-odbc.so
```
DSN-less connection string (token auth, plaintext gRPC):
```
Driver={Arrow Flight SQL ODBC Driver};Host=<host>;Port=32010;useEncryption=false;Token=<token>
```
`Token=` is sent as Bearer. Use `UID=`/`PWD=` for Basic (password = token). Drop `useEncryption=false` for TLS.

## Notes
- Server reports itself as `Hadoop-Arrow-Parquet`; catalog `PARQUET_ARROW_FLIGHT_CATALOG`.
- Use `resultMode=complete` for arbitrary SQL (joins); partial mode accepts single-table SELECTs only.
- BI tools: Tableau/Power BI/Excel use the same driver on Windows (MSI); not run in CI.
