#!/usr/bin/env bash
# dbt-gizmosql probe against the Flight SQL server: connect, read-only query, view/table materialization.
#   dbt_probe.sh <host:port> <token>
# Prints a result line per step (OK/FAIL + first error line); exits 0 (this is a probe, not a pass/fail test).
set -u
hp=$1; tok=$2; host=${hp%:*}; port=${hp#*:}
d=$(mktemp -d); cd "$d"
mkdir -p models
cat > dbt_project.yml <<Y
name: probe
version: "1.0"
profile: probe
model-paths: [models]
Y
cat > profiles.yml <<Y
probe:
  target: dev
  outputs:
    dev: {type: gizmosql, host: $host, port: $port, use_encryption: false, user: u, password: "$tok", database: tpch, schema: tpch, threads: 1}
Y
echo "select * from tpch.nation" > models/m_view.sql
echo "{{ config(materialized='table') }} select * from tpch.nation" > models/m_table.sql
step() { # name, command...
  n=$1; shift
  if out=$("$@" 2>&1); then echo "OK   $n"; else echo "FAIL $n: $(echo "$out" | grep -iE 'error|unsupported|exception|denied|not' | head -3 | tr '\n' ' ' | cut -c1-400)"; fi
}
step debug dbt debug --profiles-dir .
step show_select dbt show --profiles-dir . --inline "select count(*) as n from tpch.nation"
step run_view dbt run --profiles-dir . -s m_view
step run_table dbt run --profiles-dir . -s m_table
