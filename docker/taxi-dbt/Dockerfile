# docker/taxi-dbt/Dockerfile
#
# Image riêng chỉ để chạy `dbt build`, được Airflow gọi qua DockerOperator
# (xem airflow/dags/taxi_pipeline_dag.py, task "dbt_build"). Tách hẳn khỏi
# image Airflow -- đây là điểm mấu chốt để tránh lỗi "xung đột dependency
# Airflow + dbt / pip install treo" đã gặp khi thử nghiệm trước đó.
#
# Project dbt (thư mục dbt/ trong repo) KHÔNG được COPY vào image -- được
# bind-mount lúc chạy (xem HOST_PROJECT_DIR trong airflow/dags/taxi_pipeline_dag.py),
# để không phải build lại image mỗi khi sửa model/test.
FROM python:3.12-slim

RUN pip install --no-cache-dir dbt-postgres==1.9.0

ENTRYPOINT ["dbt"]
