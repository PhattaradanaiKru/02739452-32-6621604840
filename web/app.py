"""Flask dashboard: every data endpoint reads the target PostgreSQL directly."""
import csv
import io

from flask import Flask, Response, jsonify, render_template, request
from psycopg2 import Error as DatabaseError
from psycopg2.extras import RealDictCursor

from pipeline.database import connect, initialize

app = Flask(__name__)
initialize()


def fetch(sql, params=()):
    with connect() as con, con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


@app.errorhandler(DatabaseError)
def unavailable(exc):
    app.logger.error('Target PostgreSQL query failed (%s)', type(exc).__name__)
    return jsonify(error='ไม่สามารถเชื่อมต่อ PostgreSQL ได้ โปรดตรวจสอบบริการฐานข้อมูล'), 503


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/health')
def health():
    fetch('SELECT 1')
    return jsonify(status='ok', database='postgresql')


PUBLISHED = "(SELECT run_id FROM pipeline_runs WHERE status IN ('success','degraded') ORDER BY finished_at DESC LIMIT 1)"


def city_rows():
    where = ['c.published_run_id=' + PUBLISHED]
    values = []
    pref, q = request.args.get('prefecture', ''), request.args.get('q', '').strip()
    year, source = request.args.get('year', ''), request.args.get('source', '')
    if pref:
        where.append('c.prefecture=%s')
        values.append(pref)
    if q:
        where.append('(c.name ILIKE %s OR c.region_code ILIKE %s)')
        values.extend(['%' + q + '%'] * 2)
    if year == '2020':
        where.append('c.population_year=2020')
    elif year == 'unknown':
        where.append('c.population_year IS NULL')
    if source == 'geonames':
        where.append("c.coordinate_source='geonames'")
    elif source in ('estat', 'undata'):
        where.append('EXISTS (SELECT 1 FROM population_observations o WHERE o.geoname_id=c.geoname_id '
                     'AND o.run_id=c.published_run_id AND o.source=%s)')
        values.append(source)
    try:
        minimum = max(0, int(request.args.get('min_population', '0')))
    except ValueError:
        minimum = 0
    where.append('c.population >= %s')
    values.append(minimum)
    order = {'population': 'c.population DESC', 'name': 'c.name', 'prefecture': 'c.prefecture,c.name'}
    sort = order.get(request.args.get('sort', ''), 'c.population DESC')
    return fetch('''SELECT c.*,
       ARRAY(SELECT o.source FROM population_observations o WHERE o.geoname_id=c.geoname_id
         AND o.run_id=c.published_run_id UNION SELECT c.coordinate_source ORDER BY source) AS sources
       FROM cities c WHERE ''' + ' AND '.join(where) + ' ORDER BY ' + sort, values)


@app.get('/api/cities')
def cities():
    rows = city_rows()
    prefs = fetch('SELECT DISTINCT prefecture FROM cities WHERE published_run_id=' + PUBLISHED + ' ORDER BY prefecture')
    return jsonify(cities=rows, prefectures=[p['prefecture'] for p in prefs],
                   metrics={'cities': len(rows), 'population': sum(c['population'] for c in rows),
                            'prefectures': len({c['prefecture'] for c in rows}),
                            'official': sum(c['population_year'] == 2020 for c in rows)})


@app.get('/api/cities/<int:city_id>')
def city_detail(city_id):
    city = fetch('SELECT * FROM cities WHERE geoname_id=%s AND published_run_id=' + PUBLISHED, (city_id,))
    if not city:
        return jsonify(error='ไม่พบเมืองนี้ในชุดข้อมูลที่เผยแพร่'), 404
    observations = fetch('SELECT source,year_key,population,source_url,fetched_at FROM population_observations '
                         'WHERE geoname_id=%s AND run_id=%s ORDER BY source', (city_id, city[0]['published_run_id']))
    return jsonify(city=city[0], observations=observations)


@app.get('/api/status')
def status():
    runs = fetch('SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 12')
    sources = fetch('SELECT * FROM source_runs WHERE run_id=%s ORDER BY source', (runs[0]['run_id'],)) if runs else []
    published = fetch('SELECT * FROM pipeline_runs WHERE run_id=' + PUBLISHED)
    reasons = fetch('SELECT source,reason,count(*) AS count FROM rejected_records WHERE run_id=%s '
                    'GROUP BY source,reason ORDER BY count(*) DESC', (runs[0]['run_id'],)) if runs else []
    rejected = fetch('SELECT source,name,reason FROM rejected_records WHERE run_id=%s ORDER BY record_index LIMIT 100',
                     (runs[0]['run_id'],)) if runs else []
    return jsonify(runs=runs, sources=sources, published=published[0] if published else None,
                   rejection_reasons=reasons, rejected=rejected)


@app.get('/api/export.csv')
def export():
    output = io.StringIO()
    fields = ['geoname_id', 'region_code', 'name', 'prefecture', 'latitude', 'longitude',
              'population', 'population_year', 'population_source', 'coordinate_source',
              'coordinate_fetched_at', 'coordinate_reused', 'sources']
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for row in city_rows():
        row['sources'] = ','.join(row['sources'])
        writer.writerow(row)
    return Response('\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename=japan-cities.csv'})
