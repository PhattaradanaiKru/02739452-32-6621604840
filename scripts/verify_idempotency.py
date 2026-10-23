"""Re-publish the same validated batch and assert stable table counts."""
import json
from pipeline import database as db
from pipeline.workflow import run_dir

with db.connect() as con, con.cursor() as cur:
 cur.execute("SELECT run_id FROM pipeline_runs WHERE status='success' ORDER BY finished_at DESC LIMIT 1")
 run_id=cur.fetchone()[0]

def counts():
 with db.connect() as con, con.cursor() as cur:
  cur.execute('SELECT (SELECT count(*) FROM cities),(SELECT count(*) FROM population_observations)')
  return cur.fetchone()

prepared=json.loads((run_dir(run_id)/'prepared.json').read_text(encoding='utf-8'))
before=counts()
db.publish(run_id,prepared['cities'])
after=counts()
assert before==after,(before,after)
print(json.dumps({'test':'UPSERT idempotency','before':before,'after':after,'passed':True}))
