ARG TAG=6.0.0
FROM apache/superset:${TAG}
USER root
ARG DIALECT=superset-sqlalchemy-gizmosql-adbc-dialect
RUN (uv pip install --python /app/.venv/bin/python ${DIALECT} || /app/.venv/bin/python -m pip install ${DIALECT})
USER superset
