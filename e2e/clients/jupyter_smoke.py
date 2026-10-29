#!/usr/bin/env python3
"""Build the smoke notebook: pandas over ADBC Flight SQL, run all queries, write TSVs (executed by nbconvert).

    jupyter_smoke.py <notebook.ipynb>
    env at execution time: FLIGHT_URI, FLIGHT_TOKEN, QUERIES_DIR, OUT_DIR
"""
import sys
import nbformat

CELLS = [
    "import os, sys\nsys.path.insert(0, os.path.join(os.environ['REPO'], 'e2e', 'clients'))\n"
    "import python_df as d\nimport adbc_driver_flightsql.dbapi as flight\n"
    "from adbc_driver_flightsql import DatabaseOptions\n"
    "conn = flight.connect(os.environ['FLIGHT_URI'], db_kwargs={DatabaseOptions.AUTHORIZATION_HEADER.value: "
    "'Bearer ' + os.environ['FLIGHT_TOKEN']})",
    "import pandas as pd\ndf = pd.read_sql('select count(*) as n from tpch.nation', conn)\nassert int(df.n[0]) == 25, df\ndf",
    "qdir, out = os.environ['QUERIES_DIR'], os.environ['OUT_DIR']\nos.makedirs(out, exist_ok=True)\n"
    "for name in sorted(f[:-4] for f in os.listdir(qdir) if f.endswith('.sql')):\n"
    "    sql = open(os.path.join(qdir, name + '.sql'), encoding='utf-8').read()\n"
    "    try:\n"
    "        rows = list(d.fetch('pandas', conn, sql))\n"
    "        open(os.path.join(out, name + '.tsv'), 'w', encoding='utf-8').write(''.join('\\t'.join(d.cell(v) for v in r) + '\\n' for r in rows))\n"
    "    except Exception as e:\n"
    "        open(os.path.join(out, name + '.err'), 'w', encoding='utf-8').write(' '.join(str(e).split()) + '\\n')\n"
    "conn.close()",
]

nb = nbformat.v4.new_notebook()
nb.cells = [nbformat.v4.new_code_cell(c) for c in CELLS]
nbformat.write(nb, sys.argv[1])
