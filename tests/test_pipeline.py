"""Tests target boundary errors that can silently corrupt city datasets."""
import copy
import json
import unittest

from pipeline.sources import parse_geonames, parse_undata, parse_estat
from pipeline.transform import check_quality, merge_sources

META = {'url': 'https://example.org/source', 'fetched_at': '2026-10-23T00:00:00+00:00'}


def geo(city_id=1, name='Date Shi', prefecture='Hokkaido', population=100):
    return dict(geoname_id=city_id, name=name, prefecture=prefecture,
                latitude=42.4, longitude=140.8, population=population, year=None,
                source='geonames', area_type='municipality', **META)


def census(name='Date-shi', prefecture='Hokkaido', population=99, code='01233'):
    return dict(name=name, prefecture=prefecture, population=population, year=2020,
                region_code=code, source='estat', **META)


class MatchingTests(unittest.TestCase):
    def test_same_name_different_prefectures_are_separate(self):
        g = [geo(), geo(2, prefecture='Fukushima')]
        e = [census(), census(prefecture='Fukushima', population=200, code='07213')]
        u = dict(name='Date', population=200, year=2020, source='undata', **META)
        rows, rejects = merge_sources(dict(geonames=g, estat=e, undata=[u]))
        self.assertFalse(rejects)
        self.assertEqual([r['population'] for r in rows], [99, 200])
        self.assertEqual([len(r['observations']) for r in rows], [2, 3])

    def test_ambiguous_un_name_is_not_arbitrarily_assigned(self):
        g = [geo(), geo(2, prefecture='Fukushima')]
        u = dict(name='Date', population=200, year=2020, source='undata', **META)
        rows, rejects = merge_sources(dict(geonames=g, undata=[u]))
        self.assertEqual(rejects[0]['reason'], 'ambiguous_city')
        self.assertTrue(all(len(r['observations']) == 1 for r in rows))

    def test_missing_shi_suffix_needs_official_confirmation(self):
        g = geo(name='Nagoya', prefecture='Aichi', population=None)
        g['municipality_confirmed'] = False
        rows, rejects = merge_sources(dict(geonames=[g], estat=[census('Nagoya-shi','Aichi',2333406)]))
        valid, _, result = check_quality(rows, rejects, minimum=1)
        self.assertTrue(result['passed'])
        self.assertEqual(valid[0]['population'], 2333406)

    def test_undated_population_does_not_become_census_2020(self):
        rows, rejects = merge_sources(dict(geonames=[geo()]))
        valid, _, result = check_quality(rows, rejects, minimum=1)
        self.assertTrue(result['passed'])
        self.assertIsNone(valid[0]['population_year'])
        self.assertEqual(result['official_population_cities'], 0)

    def test_invalid_coordinates_are_quarantined(self):
        bad = geo()
        bad['latitude'] = 0
        rows, rejects = merge_sources(dict(geonames=[bad]))
        valid, rejects, result = check_quality(rows, rejects, minimum=1)
        self.assertFalse(result['passed'])
        self.assertEqual(valid, [])
        self.assertEqual(rejects[0]['reason'], 'outside_japan_bounds')

    def test_reused_coordinates_keep_original_timestamp(self):
        saved = geo()
        saved['coordinate_fetched_at'] = saved.pop('fetched_at')
        rows, rejects = merge_sources(dict(estat=[census()]), fallback=[saved])
        valid, _, result = check_quality(rows, rejects, minimum=1)
        self.assertTrue(result['passed'])
        self.assertTrue(valid[0]['coordinate_reused'])
        self.assertEqual(valid[0]['coordinate_fetched_at'], META['fetched_at'])


class ParsingTests(unittest.TestCase):
    def test_un_excludes_male_and_urban_agglomeration(self):
        def row(sex, area, value):
            cells=['Japan','2020','Total',sex,'Date',area,'Census','Final','2022',str(value)]
            return '<tr>'+''.join('<td>'+x+'</td>' for x in cells)+'</tr>'
        body='<table><tr><th>Country or Area</th><th>City type</th></tr>'
        body+=row('Both Sexes','City proper',99)+row('Male','City proper',45)+row('Both Sexes','Urban agglomeration',200)+'</table>'
        result=parse_undata(body,META)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['population'],99)

    def test_geo_excludes_historical_and_ward_records(self):
        def row(feature):
            return ('<tr><td>1</td><td><a href="/123/date-shi.html">Date Shi</a>'
                    '<span class="latitude">42.4</span><span class="longitude">140.8</span>'
                    '</td><td><a>Japan</a>, Hokkaido<br><small>Date Shi</small></td>'
                    '<td>'+feature+'<small>population 100</small></td><td>N</td><td>E</td></tr>')
        body='<table class="restable">'+row('second-order administrative division')+row('historical second-order administrative division')+row('third-order administrative division')+'</table>'
        self.assertEqual(len(parse_geonames(body,META)),1)


if __name__ == '__main__':
    unittest.main()
