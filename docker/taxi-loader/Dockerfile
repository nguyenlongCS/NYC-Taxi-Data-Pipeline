# docker/taxi-loader/Dockerfile
#
# Image riêng chỉ để chạy load_parquet_to_staging.py, được Airflow gọi qua
# DockerOperator (xem airflow/dags/taxi_pipeline_dag.py, task "load_staging").
# Tách riêng khỏi image Airflow để tránh xung đột dependency (xem
# airflow/Dockerfile).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY load_parquet_to_staging.py .

ENTRYPOINT ["python", "load_parquet_to_staging.py"]
