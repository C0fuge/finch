import os
import traceback

import sqlalchemy

print("sqlalchemy", sqlalchemy.__version__)
try:
    e = sqlalchemy.create_engine(os.environ["U"])
    with e.connect() as c:
        print(c.execute(sqlalchemy.text("select 1")).fetchall())
except Exception:  # noqa: BLE001
    traceback.print_exc()
