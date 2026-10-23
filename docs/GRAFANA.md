# Grafana (Flight SQL datasource)

Plugin: `influxdata-flightsql-datasource` (install with `GF_INSTALL_PLUGINS=influxdata-flightsql-datasource` or
`grafana cli plugins install ...`). Tested with Grafana OSS 11.3.0. CI: `e2e.yml`, client `grafana`
(`e2e/clients/grafana.py`), TPC-H 22/22 identical to the reference (run 40027308243).

## Datasource

Provisioning (`provisioning/datasources/flight.yaml`) or the HTTP API:

```yaml
apiVersion: 1
datasources:
  - name: flight
    type: influxdata-flightsql-datasource
    access: proxy
    jsonData: { host: "flight-server:32010", secure: false, selectedAuthType: token, metadata: [] }
    secureJsonData: { token: "<FLIGHT_AUTH_TOKEN>" }
```

`secure: true` = TLS. Server in `resultMode=complete` (full DuckDB SQL; partial mode rejects multi-table SQL).
Health check ("Save & test") works.

## Queries

The query field is `queryText` (not `rawSql`) in `/api/ds/query`; `format: table`.

## Known plugin limits (columns come back empty)

The plugin does not map Arrow `decimal128`, `date32` and 128-bit ints: such columns arrive as empty fields and
the query fails with `frame has different field lengths` (or returns 0 rows). Workaround in SQL: cast
`DECIMAL`→`DOUBLE`, `DATE`/`TIMESTAMP`→`VARCHAR`, `HUGEINT` (e.g. `sum(int)`)→`BIGINT`. Integers, doubles and
strings work as is. The CI client applies these casts automatically (via `DESCRIBE`), so the TPC-H result equals
the reference after the usual normalisation.
