"""Relax the GizmoSQL ADBC dialect for our server (see docs/SUPERSET.md):
- accept any ADBC vendor_version (ours reports "0.0.1", the dialect wants "duckdb ...");
- make do_rollback/do_begin/do_commit no-ops: the server only accepts queries ("Only queries are allowed, not ROLLBACK")."""
import re
import sys

import superset_sqlalchemy_gizmosql_adbc_dialect as m

src = open(m.__file__, encoding="utf-8").read()
src, n1 = re.subn(r'if not re\.search\(pattern="\^duckdb ", string=vendor_version\):', "if False:", src)
src, n2 = re.subn(r"(    def do_(?:rollback|begin|commit)\(self, connection: \"Connection\"\) -> None:\n)(?:        .*\n|\n(?=        ))+",
                  r"\1        return\n\n", src)
print("patched vendor check:", n1, "transaction methods:", n2)
if n1 != 1 or n2 != 3:
    sys.exit("patch did not apply")
open(m.__file__, "w", encoding="utf-8").write(src)
