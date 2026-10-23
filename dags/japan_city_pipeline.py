"""Japan city ETL, structured like the course's Airflow 2.10.4 workshops."""
from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException
from airflow.operators.python import get_current_context
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

from pipeline import database, workflow


def current_run():
    return get_current_context()['run_id']


@dag(dag_id='japan_city_pipeline', start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
     schedule='0 2 * * *', catchup=False, max_active_runs=1,
     default_args={'owner': 'japan-city-atlas', 'retries': 1, 'retry_delay': timedelta(seconds=15)},
     tags=['japan', 'scraping', 'postgres', 'exam'],
     doc_md='''Collect municipal population and coordinates from GeoNames HTML,
UNdata HTML and e-Stat JSON. Source failures remain visible; merge runs with
all_done. Quality failure branches to quarantine without replacing published data.
GeoNames population year is unknown and is never presented as census 2020.''')
def japan_city_pipeline():
    @task
    def initialize():
        database.start_run(current_run())

    @task(execution_timeout=timedelta(minutes=20))
    def extract(source):
        config = get_current_context()['dag_run'].conf or {}
        disabled = config.get('disabled_sources', [])
        if not isinstance(disabled, list) or any(s not in ('geonames', 'estat', 'undata') for s in disabled):
            raise ValueError('disabled_sources must be a list of source names')
        return workflow.extract(current_run(), source, disabled)

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def merge_and_validate():
        return workflow.prepare(current_run())

    @task.branch
    def quality_gate(summary):
        return 'publish' if summary['passed'] else 'quarantine'

    @task
    def publish():
        return workflow.load(current_run())

    @task(retries=0)
    def quarantine():
        database.fail_quality(current_run())
        raise AirflowException('Fewer than 100 valid cities; inspect rejected_records and source_runs')

    begin = initialize()
    groups = []
    for source in ('geonames', 'estat', 'undata'):
        with TaskGroup(group_id=source) as group:
            extract.override(task_id='extract')(source)
        begin >> group
        groups.append(group)
    merged = merge_and_validate()
    for group in groups:
        group >> merged
    gate = quality_gate(merged)
    gate >> [publish(), quarantine()]


japan_city_pipeline()
