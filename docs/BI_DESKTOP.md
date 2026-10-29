# Tableau and Power BI (setup docs, not run in CI)

Both tools are desktop/Windows products; no CI is possible. The drivers they use are the ones already proven here
against the TPC-H reference: the Arrow Flight SQL JDBC driver (`jdbc`, `jdbc_meta`) and the Apache Arrow Flight SQL
ODBC driver (`odbc_apache`, see `ODBC.md`). Everything below is therefore setup guidance, **untested in the tools
themselves**.

Server prerequisites (both tools):
- Use `resultMode=complete` if the tool generates joins or subqueries (partial mode accepts single-table SELECTs only).
- Host/port `32010`; token auth: Bearer token, or Basic with the token as the password.
- Catalog is `PARQUET_ARROW_FLIGHT_CATALOG`; tables show up under schemas such as `tpch`.

## Power BI Desktop (ODBC only)

Power BI has no JDBC connector; use ODBC.
1. Install the Apache Arrow Flight SQL ODBC driver (win64 MSI, Apache Arrow >= 26.0.0) or Dremio's MSI.
2. Create a System DSN in "ODBC Data Sources (64-bit)" with keys `Host`, `Port` (32010), `useEncryption` (`false` for
   plaintext, otherwise TLS and optionally `trustedCerts`), and `Token`. Or `UID`/`PWD` for Basic or LDAP login
   (see `AUTH.md`).
3. Power BI: Get data -> ODBC -> pick the DSN (or paste the DSN-less connection string from `ODBC.md`) ->
   Navigator lists the schemas and tables -> Import.
4. DirectQuery works only as far as the generated SQL is accepted by DuckDB; prefer Import mode.

## Tableau (JDBC or ODBC)

Option A, JDBC ("Other Databases (JDBC)" connector):
1. Download `flight-sql-jdbc-driver-<version>.jar` (Maven `org.apache.arrow:flight-sql-jdbc-driver`) into Tableau's
   `Drivers` folder (Windows: `C:\Program Files\Tableau\Drivers`, macOS: `~/Library/Tableau/Drivers`), restart Tableau.
2. Connect -> More -> Other Databases (JDBC): URL
   `jdbc:arrow-flight-sql://<host>:32010/?useEncryption=false&token=<token>`, dialect `SQL92`.

Option B, ODBC ("Other Databases (ODBC)"): same DSN as for Power BI.

Tableau's generic dialect sends plain ANSI SQL; expect to use "Initial SQL"/custom SQL where a generated query uses
a function DuckDB lacks. A TDC (`.tdc`) file can override capabilities; a starting template for the ODBC route is:
```xml
<?xml version='1.0' encoding='utf-8' ?>
<connection-customization class='genericodbc' enabled='true' version='10.0'>
  <vendor name='Hadoop-Arrow-Parquet'/>
  <driver name='Arrow Flight SQL ODBC Driver'/>
  <customizations>
    <customization name='CAP_CREATE_TEMP_TABLES' value='no'/>
    <customization name='CAP_SELECT_INTO' value='no'/>
    <customization name='CAP_QUERY_SUBQUERIES' value='yes'/>
    <customization name='CAP_QUERY_TOP_N' value='no'/>
    <customization name='SQL_IDENTIFIER_QUOTE_CHAR' value='&quot;'/>
  </customizations>
</connection-customization>
```
Save it as `Datasources/*.tdc` in the Tableau repository (My Tableau Repository). Capability names and values are
from Tableau's TDC reference; verify against your Tableau version.

## Known gaps
- Read-only: no DDL/DML, so no extracts to temp tables, no write-back.
- Not verified in the real tools; if a dialect problem appears, report it as a server issue with the generated SQL.
