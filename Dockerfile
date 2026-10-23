FROM apache/airflow:2.10.4
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY dags /opt/airflow/dags
COPY pipeline /opt/airflow/pipeline
COPY web /opt/airflow/web
COPY scripts /opt/airflow/scripts
COPY tests /opt/airflow/tests
ENV PYTHONPATH=/opt/airflow
