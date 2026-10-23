"""Trigger an actual Airflow run with optional source failure injection."""
import argparse
import json
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--disabled', nargs='*', choices=['geonames', 'estat', 'undata'], default=[])
p.add_argument('--run-id')
a = p.parse_args()
command = ['airflow', 'dags', 'trigger', 'japan_city_pipeline', '--conf', json.dumps({'disabled_sources': a.disabled})]
if a.run_id:
    command += ['--run-id', a.run_id]
subprocess.run(command, check=True)
