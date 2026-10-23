"""Replay a recorded batch with an intentionally impossible acceptance threshold.

This tests the real quality branch without making more network requests or
replacing the published dataset. Audit entries use a dedicated validation run.
"""
import json
import os
from pipeline import database as db
from pipeline.workflow import run_dir, prepare, load, write_json

with db.connect() as con, con.cursor() as cur:
 cur.execute("SELECT run_id FROM pipeline_runs WHERE status='success' ORDER BY finished_at DESC LIMIT 1")
 base=cur.fetchone()[0]
 cur.execute('SELECT count(*),sum(population) FROM cities')
 before=cur.fetchone()

run='validation_quality_rejection'
db.start_run(run)
for source in ('geonames','estat','undata'):
 recorded=json.loads((run_dir(base)/(source+'.json')).read_text(encoding='utf-8'))
 write_json(run_dir(run)/(source+'.json'),recorded)
 db.source_status(run,source,recorded['ok'],len(recorded['rows']),'Replayed recorded response for quality-gate test')
os.environ['MIN_CITIES']='99999'
summary=prepare(run)
assert not summary['passed']
try:
 load(run)
except ValueError:
 pass
else:
 raise AssertionError('Quality failure did not block publishing')
db.fail_quality(run)
with db.connect() as con, con.cursor() as cur:
 cur.execute('SELECT count(*),sum(population) FROM cities')
 after=cur.fetchone()
assert before==after
print(json.dumps({'test':'quality gate preserves published dataset','passed':True,'cities_unchanged':after[0]}))
