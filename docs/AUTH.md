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
