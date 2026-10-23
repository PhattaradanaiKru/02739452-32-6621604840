import re
import unicodedata
from collections import defaultdict


def normalize(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value.lower())
                    if not unicodedata.combining(c))
    value = re.sub(r'(?:[-\s]+(?:shi|ken|fu|to))$', '', value)
    value = re.sub(r'[^a-z0-9]', '', value)
    return {'gumma': 'gunma', 'hyogo': 'hyogo', 'hukuoka': 'fukuoka',
            'hirosima': 'hiroshima', 'aiti': 'aichi'}.get(value, value)


def merge_sources(batches, fallback=None):
    """Exact normalized city + prefecture matches; ambiguous UN names are rejected.

    Canonical population priority is e-Stat 2020 > UNdata 2020 > undated
    GeoNames. Keep every observation so figures are never averaged or summed.
    """
    rejected = []
    cities = {}
    geo = batches.get('geonames', [])
    using_saved_coordinates = not geo and bool(fallback)
    if using_saved_coordinates:
        geo = fallback
    for row in geo:
        key = row['geoname_id']
        cities[key] = {
            'geoname_id': key, 'name': re.sub(r'(?:-shi| Shi)$', '', row['name'], flags=re.I),
            'prefecture': row['prefecture'], 'latitude': row['latitude'],
            'longitude': row['longitude'], 'region_code': None,
            'population': None, 'population_year': None, 'population_source': None,
            'coordinate_source': 'geonames', 'coordinate_fetched_at': row.get('fetched_at', row.get('coordinate_fetched_at')),
            'coordinate_reused': using_saved_coordinates, 'observations': [],
            'municipality_confirmed': using_saved_coordinates or row.get('municipality_confirmed', True),
        }
        if not using_saved_coordinates and row.get('population') is not None:
            cities[key]['observations'].append(row)
    by_full = defaultdict(list)
    by_name = defaultdict(list)
    for city in cities.values():
        by_full[(normalize(city['name']), normalize(city['prefecture']))].append(city)
        by_name[normalize(city['name'])].append(city)
    for source in ('estat', 'undata'):
        for row in batches.get(source, []):
            name = normalize(row['name'])
            matches = (by_full[(name, normalize(row['prefecture']))]
                       if row.get('prefecture') else by_name[name])
            ambiguous = len(matches) > 1
            # UNdata provides no prefecture. Use an independently observed
            # exact same-year census value only when it resolves a duplicate.
            if len(matches) > 1 and source == 'undata':
                matches = [city for city in matches if any(
                    x['source'] == 'estat' and x['population'] == row['population']
                    and x['year'] == row['year'] for x in city['observations'])]
            if len(matches) != 1:
                rejected.append({'source': source, 'name': row['name'],
                                 'reason': 'ambiguous_city' if ambiguous else 'no_exact_city_match',
                                 'record': row})
                continue
            city = matches[0]
            city['municipality_confirmed'] = True
            city['observations'].append(row)
            if row.get('region_code'):
                city['region_code'] = row['region_code']
    priority = {'estat': 0, 'undata': 1, 'geonames': 2}
    for city in cities.values():
        dedup = {}
        for row in city['observations']:
            dedup[(row['source'], row.get('year'))] = row
        city['observations'] = list(dedup.values())
        if dedup:
            chosen = min(dedup.values(), key=lambda x: priority[x['source']])
            city.update(population=chosen['population'], population_year=chosen.get('year'),
                        population_source=chosen['source'])
    return list(cities.values()), rejected


def check_quality(cities, rejected, minimum=100):
    valid = []
    rejected = list(rejected)
    seen = set()
    for city in cities:
        reason = None
        if not city.get('municipality_confirmed', True):
            reason = 'not_a_confirmed_city_municipality'
        elif city['geoname_id'] in seen:
            reason = 'duplicate_city'
        elif not city['name'] or not city['prefecture']:
            reason = 'missing_name_or_prefecture'
        elif not (-90 <= city['latitude'] <= 90 and -180 <= city['longitude'] <= 180):
            reason = 'invalid_coordinates'
        elif not (20 <= city['latitude'] <= 46 and 122 <= city['longitude'] <= 154):
            reason = 'outside_japan_bounds'
        elif not isinstance(city['population'], int) or city['population'] <= 0:
            reason = 'missing_or_invalid_population'
        elif city['population_year'] not in (None, 2020):
            reason = 'unexpected_population_year'
        if reason:
            rejected.append({'source': 'merged', 'name': city['name'], 'reason': reason,
                             'record': city})
        else:
            seen.add(city['geoname_id'])
            valid.append(city)
    summary = {'passed': len(valid) >= minimum, 'valid_cities': len(valid),
               'rejected_records': len(rejected), 'minimum_cities': minimum,
               'official_population_cities': sum(x['population_year'] == 2020 for x in valid),
               'reused_coordinate_cities': sum(x['coordinate_reused'] for x in valid)}
    return valid, rejected, summary
