"""Three real sources. No API credentials, Selenium, or invented records."""
import json
import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from pipeline.http import Client

YEAR = 2020
INDICATOR = '0201010000000010000'
UN_FILTER = f'tableCode:240;countryCode:392;refYear:{YEAR};sexCode:0'
UN_URL = 'https://data.un.org/Data.aspx?'
GEO_URL = 'https://www.geonames.org/search.html?'
ESTAT_URL = 'https://dashboard.e-stat.go.jp/api/1.0/Json/'
SOURCES = ('geonames', 'estat', 'undata')


def parse_geonames(body, meta):
    soup = BeautifulSoup(body, 'html.parser')
    result = []
    for tr in soup.select('table.restable tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 6:
            continue
        feature = cells[3].get_text(' ', strip=True)
        if not feature.startswith('second-order administrative division'):
            continue
        a = cells[1].find('a', href=re.compile(r'^/\d+/'))
        if not a:
            continue
        lat, lon = tr.select_one('.latitude'), tr.select_one('.longitude')
        if not lat or not lon:
            continue
        region = cells[2].get_text('|', strip=True).split('|')
        prefecture = region[1].strip(' ,') if len(region) > 1 else ''
        population = re.search(r'population\s+([\d,]+)', feature)
        result.append({
            'geoname_id': int(re.search(r'/(\d+)/', a['href'])[1]),
            'name': a.get_text(strip=True), 'prefecture': prefecture,
            'municipality_confirmed': bool(re.search(r'(?:-shi| Shi)$', a.get_text(strip=True), re.I)),
            'latitude': float(lat.get_text()), 'longitude': float(lon.get_text()),
            'population': int(population[1].replace(',', '')) if population else None,
            'year': None, 'area_type': 'municipality', 'source': 'geonames',
            'source_url': 'https://www.geonames.org' + a['href'],
            'fetched_at': meta['fetched_at'],
        })
    return result


def extract_geonames(directory):
    client = Client(directory)
    results = {}
    # HTML search permits 500 rows per request. Match city municipalities only;
    # exclude historical divisions, wards, towns, villages and prefectures.
    for offset in range(0, 2500, 500):
        url = GEO_URL + urlencode({'q': 'shi', 'country': 'JP', 'featureClass': 'A',
                                   'maxRows': 500, 'startRow': offset})
        body, meta = client.get(url, f'geonames-{offset}.html')
        soup = BeautifulSoup(body, 'html.parser')
        for row in parse_geonames(body, meta):
            results[row['geoname_id']] = row
        if not any('next' in a.get_text().lower() for a in soup.select('a[href]')):
            break
    if len(results) < 100:
        raise ValueError(f'GeoNames HTML returned only {len(results)} municipalities')
    return list(results.values())


def parse_undata(body, meta):
    soup = BeautifulSoup(body, 'html.parser')
    results = []
    for table in soup.find_all('table'):
        headers = [x.get_text(' ', strip=True) for x in table.find_all('th')]
        if 'Country or Area' not in headers or 'City type' not in headers:
            continue
        for tr in table.find_all('tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) < 10:
                continue
            values = [c.get_text(' ', strip=True) for c in cells]
            if values[0] != 'Japan' or values[3] != 'Both Sexes' or values[5] != 'City proper':
                continue
            results.append({'name': values[4], 'population': int(values[9].replace(',', '')),
                            'year': int(values[1]), 'area_type': 'municipality',
                            'source': 'undata', 'source_url': meta['url'],
                            'fetched_at': meta['fetched_at']})
    return results


def extract_undata(directory):
    client = Client(directory)
    rows = []
    pages = 1
    for page in range(1, 31):
        url = UN_URL + urlencode({'d': 'POP', 'f': UN_FILTER, 'v': page})
        body, meta = client.get(url, f'undata-{page}.html')
        soup = BeautifulSoup(body, 'html.parser')
        count = soup.select_one('#spanPageCountB')
        if count:
            pages = int(count.get_text())
        rows.extend(parse_undata(body, meta))
        if page >= pages:
            break
    if not rows:
        raise ValueError('UNdata returned no city-proper population rows')
    return rows


def parse_estat(data_body, region_body, meta):
    data = json.loads(data_body)['GET_STATS']
    regions = json.loads(region_body)['GET_META_REGION_INF']
    for part in (data, regions):
        if part['RESULT']['status'] != '0':
            raise ValueError(part['RESULT']['errorMsg'])
    lookup = {}
    groups = regions['METADATA_INF']['CLASS_INF']['CLASS_OBJ']
    if isinstance(groups, dict):
        groups = [groups]
    for group in groups:
        children = group.get('CLASS', [])
        if isinstance(children, dict):
            children = [children]
        for city in children:
            name = city['@name']
            if name.endswith('-shi'):
                lookup[city['@regionCode']] = (name, group['@name'])
    rows = []
    objects = data['STATISTICAL_DATA']['DATA_INF']['DATA_OBJ']
    if isinstance(objects, dict):
        objects = [objects]
    for obj in objects:
        value = obj['VALUE']
        code = value['@regionCode']
        if code not in lookup or value.get('@time') != f'{YEAR}CY00':
            continue
        name, pref = lookup[code]
        rows.append({'region_code': code, 'name': name, 'prefecture': pref,
                     'population': int(value['$']), 'year': YEAR,
                     'area_type': 'municipality', 'source': 'estat',
                     'source_url': meta['url'], 'fetched_at': meta['fetched_at']})
    if not rows:
        raise ValueError('e-Stat returned no city population')
    return rows


def extract_estat(directory):
    client = Client(directory)
    params = {'Lang': 'EN', 'RegionLevel': 4, 'Time': f'{YEAR}CY00'}
    regions, _ = client.get(ESTAT_URL + 'getRegionInfo?' + urlencode(params), 'estat-regions.json')
    params['IndicatorCode'] = INDICATOR
    data, meta = client.get(ESTAT_URL + 'getData?' + urlencode(params), 'estat-population.json')
    return parse_estat(data, regions, meta)


EXTRACTORS = {'geonames': extract_geonames, 'estat': extract_estat, 'undata': extract_undata}
