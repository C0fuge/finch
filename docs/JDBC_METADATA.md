# JDBC DatabaseMetaData conformance (DBeaver / DataGrip)

DBeaver, DataGrip and similar tools build their schema tree from `java.sql.DatabaseMetaData` only. Client
`jdbc_meta` (`e2e/jdbc/MetaConformance.java`, run with the stock Arrow Flight SQL JDBC driver 18.3.0, token auth,
plaintext) calls what those tools call and reports `OK` / `GAP` (degraded but usable) / `FAIL` (tree or column list
unusable; fails the job). It runs against the same server build as the other e2e clients (45fc0a9e6e02, complete
mode); run 40614144465 — **0 FAIL**, 8 of the checks are GAPs, all server-side SqlInfo/metadata completeness.

URL: `jdbc:arrow-flight-sql://<host>:32010/?useEncryption=false&token=<token>` (driver: `org.apache.arrow:flight-sql-jdbc-driver`).

## What works

- Catalog `PARQUET_ARROW_FLIGHT_CATALOG`; schemas `tpch`, `types`; `getSchemas` with a pattern.
- `getTableTypes` = `[TABLE]`; `getTables` (all types, `TABLE` filter, name pattern `line%`) lists the 8 TPC-H tables with
  correct `TABLE_CAT/TABLE_SCHEM/TABLE_TYPE`.
- `getColumns` for `lineitem`: 16 columns in table order, `ORDINAL_POSITION` 1..16, `NULLABLE`, types `BIGINT`,
  `DECIMAL(15,2)`, `DATE`, `VARCHAR`; all `tpch` columns in one call (61).
- `getPrimaryKeys`, `getImportedKeys`, `getExportedKeys`, `getIndexInfo`, `getProcedures`, `getFunctions`: empty
  result sets, no exception.
- `ResultSetMetaData` of a SELECT, prepared statement with a parameter, `isValid`, `information_schema.tables` via SQL.
- `getIdentifierQuoteString` = `"`, `getMaxColumnsInTable` = 1000, `supportsSchemasInDataManipulation` and
  `supportsCatalogsInDataManipulation` = true, `isReadOnly` = true.

## Gaps (server-side; suggested issues for the server repo)

1. **SqlInfo not reported** — these throw `NullPointerException` inside the driver because the server omits the value:
   `supportsTransactions`, `supportsBatchUpdates`, `supportsGroupBy`, `supportsOuterJoins`, `supportsSubqueriesInExists`,
   `supportsUnion`, `getDefaultTransactionIsolation`, `supportsSelectForUpdate`, `supportsStoredProcedures`,
   `supportsResultSetType`. Tools that call them without a guard may show errors in connection properties; the server
   should answer the standard `SqlInfo` ids (`FLIGHT_SQL_SERVER_TRANSACTION`, `SQL_SUPPORTS_GROUP_BY`, ...).
2. `getTypeInfo` is empty (DBeaver uses it for the data-type list in the table editor).
3. `getSQLKeywords`, string/numeric/time/system function lists are empty (no editor keyword highlighting from metadata).
4. `getTables` has no `REMARKS`; `getSearchStringEscape` is null (patterns containing `_` such as `l_%` match loosely).
5. Product name/version is `Hadoop-Arrow-Parquet Source 0.0.1` (also the cause of the Superset dialect patch, see SUPERSET.md);
   `getUserName` is null; `Connection.getCatalog()/getSchema()` are null (no default schema, so use `tpch.<table>` in SQL).
6. Only table type `TABLE`; there are no views/system tables in the tree.

None of these stop DBeaver/DataGrip from browsing schemas, tables and columns; items 1 and 2 are the likely sources of
warnings in those tools. The DBeaver GUI itself is not run in CI — this test exercises the same JDBC calls.
