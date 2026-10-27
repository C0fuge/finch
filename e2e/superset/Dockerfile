ARG TAG=6.0.0
FROM apache/superset:${TAG}
USER root
ARG DIALECT=superset-sqlalchemy-gizmosql-adbc-dialect
RUN (uv pip install --python /app/.venv/bin/python ${DIALECT} || /app/.venv/bin/python -m pip install ${DIALECT})
USER superset
# The dialect refuses servers whose ADBC vendor_version does not start with "duckdb " (ours reports "0.0.1").
# Until the server reports a duckdb version, relax that check in the installed copy (see docs/SUPERSET.md).
RUN f=$(/app/.venv/bin/python -c "import superset_sqlalchemy_gizmosql_adbc_dialect as m;print(m.__file__)") \
 && sed -i 's/if not re.search(pattern="^duckdb ", string=vendor_version):/if False:/' "$f" && grep -n "if False:" "$f"
