import os

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values

DDL = '''
CREATE TABLE IF NOT EXISTS pipeline_runs (
 run_id TEXT PRIMARY KEY, started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 finished_at TIMESTAMPTZ, status TEXT NOT NULL, city_count INT NOT NULL DEFAULT 0,
 rejected_count INT NOT NULL DEFAULT 0, quality JSONB NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS source_runs (
 run_id TEXT REFERENCES pipeline_runs(run_id), source TEXT NOT NULL,
 status TEXT NOT NULL, row_count INT NOT NULL DEFAULT 0, message TEXT,
 finished_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (run_id, source));
CREATE TABLE IF NOT EXISTS cities (
 geoname_id BIGINT PRIMARY KEY, name TEXT NOT NULL, prefecture TEXT NOT NULL,
 region_code TEXT, latitude DOUBLE PRECISION NOT NULL, longitude DOUBLE PRECISION NOT NULL,
 population BIGINT NOT NULL CHECK (population > 0), population_year INT,
 population_source TEXT NOT NULL, coordinate_source TEXT NOT NULL,
 coordinate_fetched_at TIMESTAMPTZ NOT NULL, coordinate_reused BOOLEAN NOT NULL DEFAULT false,
 published_run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS population_observations (
 geoname_id BIGINT REFERENCES cities(geoname_id), source TEXT NOT NULL,
 year_key INT NOT NULL, population BIGINT NOT NULL, source_url TEXT NOT NULL,
 fetched_at TIMESTAMPTZ NOT NULL, run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id),
 PRIMARY KEY (geoname_id, source, year_key));
CREATE TABLE IF NOT EXISTS rejected_records (
 run_id TEXT REFERENCES pipeline_runs(run_id), record_index INT,
 source TEXT, name TEXT, reason TEXT NOT NULL, record JSONB,
 PRIMARY KEY (run_id, record_index));
CREATE INDEX IF NOT EXISTS cities_prefecture ON cities(prefecture);
CREATE INDEX IF NOT EXISTS cities_published_run ON cities(published_run_id);
'''


def connect():
    return psycopg2.connect(os.environ['DATABASE_URL'], connect_timeout=10)


def initialize():
    with connect() as con, con.cursor() as cur:
        cur.execute(DDL)


def start_run(run_id):
    initialize()
    with connect() as con, con.cursor() as cur:
        cur.execute('INSERT INTO pipeline_runs(run_id,status) VALUES (%s,%s) '
                    'ON CONFLICT(run_id) DO UPDATE SET status=EXCLUDED.status, finished_at=NULL',
                    (run_id, 'running'))


def source_status(run_id, source, ok, count=0, message=''):
    with connect() as con, con.cursor() as cur:
        cur.execute('INSERT INTO source_runs(run_id,source,status,row_count,message) VALUES (%s,%s,%s,%s,%s) '
                    'ON CONFLICT(run_id,source) DO UPDATE SET status=EXCLUDED.status, '
                    'row_count=EXCLUDED.row_count,message=EXCLUDED.message,finished_at=now()',
                    (run_id, source, 'success' if ok else 'failed', count, message))


def saved_coordinates():
    with connect() as con, con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT geoname_id,name,prefecture,latitude,longitude,coordinate_fetched_at FROM cities')
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            row['coordinate_fetched_at'] = row['coordinate_fetched_at'].isoformat()
        return rows


def save_quality(run_id, rejected, summary):
    with connect() as con, con.cursor() as cur:
        cur.execute('UPDATE pipeline_runs SET quality=%s,rejected_count=%s WHERE run_id=%s',
                    (Json(summary), len(rejected), run_id))
        cur.execute('DELETE FROM rejected_records WHERE run_id=%s', (run_id,))
        if rejected:
            execute_values(cur, 'INSERT INTO rejected_records VALUES %s', [
                (run_id, n, r['source'], r['name'], r['reason'], Json(r['record']))
                for n, r in enumerate(rejected)])


def publish(run_id, cities, degraded=False):
    # One transaction: never expose partially loaded city/observation rows.
    with connect() as con, con.cursor() as cur:
        execute_values(cur, '''INSERT INTO cities
          (geoname_id,name,prefecture,region_code,latitude,longitude,population,population_year,
           population_source,coordinate_source,coordinate_fetched_at,coordinate_reused,published_run_id)
          VALUES %s ON CONFLICT(geoname_id) DO UPDATE SET name=EXCLUDED.name,
          prefecture=EXCLUDED.prefecture,region_code=EXCLUDED.region_code,
          latitude=EXCLUDED.latitude,longitude=EXCLUDED.longitude,population=EXCLUDED.population,
          population_year=EXCLUDED.population_year,population_source=EXCLUDED.population_source,
          coordinate_fetched_at=EXCLUDED.coordinate_fetched_at,coordinate_reused=EXCLUDED.coordinate_reused,
          published_run_id=EXCLUDED.published_run_id,updated_at=now()''', [
              (c['geoname_id'],c['name'],c['prefecture'],c['region_code'],c['latitude'],c['longitude'],
               c['population'],c['population_year'],c['population_source'],c['coordinate_source'],
               c['coordinate_fetched_at'],c['coordinate_reused'],run_id) for c in cities])
        observations = [(c['geoname_id'],o['source'],o.get('year') or 0,o['population'],
                         o['source_url'],o['fetched_at'],run_id)
                        for c in cities for o in c['observations']]
        if observations:
            execute_values(cur, '''INSERT INTO population_observations
              (geoname_id,source,year_key,population,source_url,fetched_at,run_id) VALUES %s
              ON CONFLICT(geoname_id,source,year_key) DO UPDATE SET population=EXCLUDED.population,
              source_url=EXCLUDED.source_url,fetched_at=EXCLUDED.fetched_at,run_id=EXCLUDED.run_id''', observations)
        cur.execute('UPDATE pipeline_runs SET status=%s,city_count=%s,finished_at=now() WHERE run_id=%s',
                    ('degraded' if degraded else 'success', len(cities), run_id))


def fail_quality(run_id):
    with connect() as con, con.cursor() as cur:
        cur.execute("UPDATE pipeline_runs SET status='quality_failed',finished_at=now() WHERE run_id=%s", (run_id,))
