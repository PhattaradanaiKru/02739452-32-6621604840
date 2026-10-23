import hashlib
import json
import os
from pathlib import Path

from pipeline import database as db
from pipeline.sources import EXTRACTORS, SOURCES
from pipeline.transform import check_quality, merge_sources


def run_dir(run_id):
    root = Path(os.getenv('DATA_DIR', 'data')) / 'runs' / hashlib.sha256(run_id.encode()).hexdigest()[:24]
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def extract(run_id, source, disabled_sources=None):
    path = run_dir(run_id) / (source + '.json')
    try:
        if source in (disabled_sources or []) or source in os.getenv('DISABLED_SOURCES', '').split(','):
            raise RuntimeError('Source disabled for failure recovery demonstration')
        rows = EXTRACTORS[source](run_dir(run_id) / 'raw' / source)
        result = {'ok': True, 'rows': rows}
        write_json(path, result)
        db.source_status(run_id, source, True, len(rows))
        return {'source': source, 'rows': len(rows)}
    except Exception as exc:
        write_json(path, {'ok': False, 'rows': [], 'error': str(exc)})
        db.source_status(run_id, source, False, message=str(exc))
        raise


def prepare(run_id):
    batches = {}
    failures = []
    for source in SOURCES:
        path = run_dir(run_id) / (source + '.json')
        result = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'ok': False, 'rows': []}
        if result['ok']:
            batches[source] = result['rows']
        else:
            failures.append(source)
    # Reuse stored coordinates only when GeoNames fails after a successful run.
    # Preserve their original timestamp and label reuse in the dashboard.
    fallback = db.saved_coordinates() if 'geonames' not in batches else None
    cities, rejected = merge_sources(batches, fallback)
    valid, rejected, summary = check_quality(cities, rejected, int(os.getenv('MIN_CITIES', '100')))
    summary['failed_sources'] = failures
    summary['successful_sources'] = list(batches)
    if not batches:
        summary['passed'] = False
    db.save_quality(run_id, rejected, summary)
    write_json(run_dir(run_id) / 'prepared.json', {'cities': valid, 'summary': summary})
    return summary


def load(run_id):
    prepared = json.loads((run_dir(run_id) / 'prepared.json').read_text(encoding='utf-8'))
    if not prepared['summary']['passed']:
        raise ValueError('Quality gate failed; target data is unchanged')
    db.publish(run_id, prepared['cities'], bool(prepared['summary']['failed_sources']))
    return len(prepared['cities'])


if __name__ == '__main__':
    import argparse
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime, timezone
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='cli__' + datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    db.start_run(args.run_id)
    with ThreadPoolExecutor(3) as pool:
        futures = {pool.submit(extract, args.run_id, source): source for source in SOURCES}
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except Exception as exc:
                print(futures[future], type(exc).__name__, str(exc), flush=True)
    summary = prepare(args.run_id)
    print(summary, flush=True)
    if not summary['passed']:
        db.fail_quality(args.run_id)
        raise SystemExit(1)
    print('Published cities:', load(args.run_id), flush=True)
