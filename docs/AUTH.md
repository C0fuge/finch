# Login (LDAP / JWT) against the Flight SQL server

Server build `a9e43ca5e296` ships LDAP/AD and JWT providers (release asset `flight-auth-...tar.zst`, classpath
`auth/<ldap|jwt>/*`). Both **refuse to start on plaintext gRPC**, so CI runs these modes with TLS: a throwaway
self-signed cert (`FLIGHT_TLS_CERT` / `FLIGHT_TLS_KEY`, PEM, SAN `localhost`) is generated in `e2e/server.sh`; clients
connect with `grpc+tls://` and trust that cert (ADBC option `adbc.flight.sql.client_option.tls_root_certs` = PEM text).

CI: dispatch `e2e.yml` with `auth_mode=ldap|jwt`, `clients="python_adbc auth_check"`.

| Mode | Server config | Rows |
|---|---|---|
| ldap | OpenLDAP test container (`FLIGHT_LDAP_URL`, bind DN, user search base/filter `(uid={0})`, `FLIGHT_LDAP_SESSION_SECRET` = base64 >= 32 bytes, `FLIGHT_LDAP_ALLOW_PLAINTEXT=true` for the container-internal LDAP link) | **ADBC Python: TPC-H 22/22 identical** with username/password; refused: wrong password, unknown user, no credentials (run 40729632840) |
| jwt | local JWKS file (`FLIGHT_JWT_JWKS_FILE`), issuer + audience required | **blocked by a server bug**, see below |

JWT: with `FLIGHT_JWT_AUDIENCE` set, the server fails at start with `NullPointerException ... DefaultJWTClaimsVerifier.<init>`
(`Set.contains(null)` on an immutable `Set.of(audience)` in `JwtVerifier`; nimbus calls `contains(null)`); without it
the server refuses to start (`requires FLIGHT_JWT_AUDIENCE`). Fix: pass a mutable `HashSet` for the audiences (runs 40730237858, 40730519233).

Other LDAP rows (run 40734590031, `clients="pyarrow_flight jdbc_meta"`): **pyarrow.flight** logs in with `FlightClient.authenticate_basic_token` (TPC-H 22/22 identical; `tls_root_certs` = throwaway cert); **JDBC** URL `jdbc:arrow-flight-sql://host:port/?useEncryption=true&useSystemTrustStore=false&trustStore=<jks>&trustStorePassword=...&user=..&password=..` (without `useSystemTrustStore=false` the trustStore is ignored and the handshake fails); wrong password refused.

**ODBC (official Apache driver, `odbc_apache`)**: connection string `...;useEncryption=true;disableCertificateVerification=false;trustedCerts=<pem>;UID=<user>;PWD=<password>`; TPC-H 22/22 identical, wrong password refused (SQLSTATE 28000, "Invalid LDAP user name or password") - run 40755018981. The Dremio driver was not tried with login (its TLS options differ).

**DuckDB `adbc_scanner`**: `ATTACH 'grpc+tls://host:32010' AS fl (TYPE adbc, driver '<libadbc_driver_flightsql.so>', username '<user>', password '<pw>', "adbc.flight.sql.client_option.tls_root_certs" '<pem>')`; TPC-H 22/22 identical, wrong password refused - run 40770269011 (`auth_mode=ldap clients=duckdb_adbc_scanner`).

**Metabase** (`metabase-flightsql-driver`): database details `{"host","port","username","password","useEncryption":true,"disableCertificateVerification":false,"tls-root-certs-value":"<PEM>"}` (the `tls-root-certs` secret is passed as plain PEM text in `-value`); a wrong password is refused at `POST /api/database` (`UNAUTHENTICATED: Invalid LDAP user name or password`); with the correct login metadata sync, TPC-H 22/22, MBQL and field-filter checks all pass - run 40780371612 (`auth_mode=ldap clients=metabase`).

**Superset** (GizmoSQL ADBC dialect): SQLAlchemy URI `gizmosql://<user>:<password>@host:32010?useEncryption=true`. The dialect has no root-certificate option, so the Superset container trusts the throwaway cert through `SSL_CERT_FILE` (the ADBC Go driver uses the system pool). A wrong password is refused by `test_connection` (`UNAUTHENTICATED: Invalid LDAP user name or password`); with the correct login schemas/tables, SQL Lab TPC-H 22/22 and the chart-data check pass - run 40785650464 (`auth_mode=ldap clients=superset`).
