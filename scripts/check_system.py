"""Read-only HTTP/DB assertions; run inside the web container."""
import csv
import io
import json
import requests
from pipeline.database import connect

base='http://localhost:8000'
r=requests.get(base+'/health',timeout=15)
r.raise_for_status()
assert r.json()['database']=='postgresql'
data=requests.get(base+'/api/cities',timeout=15).json()
assert data['metrics']['cities']>=100
assert len({c['geoname_id'] for c in data['cities']})==len(data['cities'])
assert all('geonames' in c['sources'] for c in data['cities'])
filtered=requests.get(base+'/api/cities',params={'prefecture':'Hokkaido','year':'2020'},timeout=15).json()
assert filtered['cities'] and all(c['prefecture']=='Hokkaido' and c['population_year']==2020 for c in filtered['cities'])
assert not requests.get(base+'/api/cities',params={'q':"' OR 1=1 --"},timeout=15).json()['cities']
city=data['cities'][0]
detail=requests.get(base+'/api/cities/'+str(city['geoname_id']),timeout=15).json()
assert detail['observations'] and detail['city']['geoname_id']==city['geoname_id']
assert requests.get(base+'/api/cities/0',timeout=15).status_code==404
csv_response=requests.get(base+'/api/export.csv',params={'prefecture':'Hokkaido','year':'2020'},timeout=15)
csv_response.encoding='utf-8-sig'
csv_rows=list(csv.DictReader(io.StringIO(csv_response.text)))
assert len(csv_rows)==len(filtered['cities'])
with connect() as con, con.cursor() as cur:
 cur.execute('SELECT count(*),count(DISTINCT geoname_id) FROM cities')
 counts=cur.fetchone()
 assert counts[0]==counts[1]
print(json.dumps({'health':'passed','api_filters':'passed','sql_parameters':'passed',
                  'csv_export':'passed','detail':'passed','unique_cities':counts[0],
                  'published_metrics':data['metrics']},indent=2))
