# Image cho airflow-init / airflow-scheduler / airflow-webserver.
#
# QUAN TRỌNG (bài học đã gặp — xem docs/troubleshooting.md mục Airflow):
# Image này CHỈ cài apache-airflow-providers-docker. KHÔNG cài dbt-postgres,
# pandas, pyarrow ở đây — những package đó có ràng buộc version (đặc biệt
# dbt-core qua mashumaro) dễ xung đột với dependency của bản thân Airflow,
# từng gây "pip install treo và fail". Toàn bộ logic nghiệp vụ (Spark, load
# staging, dbt) chạy trong container RIÊNG do DockerOperator tạo ra, không
# chạy trực tiếp trong image Airflow này — xem airflow/dags/taxi_pipeline_dag.py.
FROM apache/airflow:2.10.5-python3.12

COPY requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir -r /requirements-airflow.txt \
    && pip check
