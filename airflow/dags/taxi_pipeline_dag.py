"""
airflow/dags/taxi_pipeline_dag.py

DAG điều phối pipeline NYC Taxi (xem docs/roadmap.md, giai đoạn Airflow):

    run_spark_job  --(luồng 7)-->  load_staging  --(luồng 8)-->  dbt_build  --(luồng 9)

Nguyên tắc thiết kế (rút ra từ các lỗi đã gặp khi thử nghiệm trước đó —
xem docs/troubleshooting.md):

- Image Airflow KHÔNG cài dbt/pandas/pyarrow trực tiếp. Mọi task chạy
  trong container Docker RIÊNG qua DockerOperator (docker-outside-of-docker),
  tránh xung đột dependency giữa Airflow và dbt.
- File này KHÔNG chứa bất kỳ đường dẫn kiểu Windows nào (vd. "D:\\..."), để
  tránh lỗi "\\N bị hiểu thành escape unicode". Mọi đường dẫn BÊN TRONG
  container con đều là POSIX ("/opt/...", "/app/...", "/dbt/..."). Đường dẫn
  HOST thật chỉ được lắp ráp lúc chạy từ biến môi trường HOST_PROJECT_DIR
  (đọc qua os.environ, không hardcode) — biến này PHẢI được set trong .env
  (xem airflow/README.md), nếu thiếu Airflow sẽ báo lỗi rõ ràng ngay khi
  container airflow-scheduler khởi động (xem docker-compose.yml).
- Các container con được gắn vào network "taxi_net" (khai cố định tên trong
  docker-compose.yml) để gọi được service `postgres` bằng tên, không phụ
  thuộc tên project Compose tự sinh.
"""
from __future__ import annotations

import os
from datetime import datetime

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

# ---------------------------------------------------------------------------
# Cấu hình đọc từ biến môi trường (đã set trong docker-compose.yml phần
# "environment:" của service airflow-scheduler — KHÔNG hardcode ở đây).
# ---------------------------------------------------------------------------
HOST_PROJECT_DIR = os.environ["HOST_PROJECT_DIR"]
DOCKER_NETWORK = os.environ.get("TAXI_DOCKER_NETWORK", "taxi_net")

DB_HOST = "postgres"  # tên service Postgres trong docker-compose.yml, không phải "localhost"
DB_NAME = os.environ.get("POSTGRES_DB", "taxi_dwh")
DB_USER = os.environ.get("POSTGRES_USER", "taxi_user")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "taxi_pass")

DOCKER_URL = "unix://var/run/docker.sock"

default_args = {
    "owner": "taxi-pipeline",
    "retries": 1,
    "retry_delay": 300,  # giây — đủ để chờ qua các lỗi tạm thời (network, lock DB)
}

with DAG(
    dag_id="taxi_pipeline",
    description="Spark clean -> load staging -> dbt build (xem docs/pipeline.md)",
    default_args=default_args,
    schedule="@monthly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["taxi", "etl"],
) as dag:

    # ---- Luồng 7: Airflow -> Spark (xem docs/roadmap.md) ----
    # Tương đương lệnh thủ công:
    #   docker compose run --rm spark /opt/spark/bin/spark-submit \
    #       /opt/spark_data/spark_jobs/clean_taxi_data.py
    run_spark_job = DockerOperator(
        task_id="run_spark_job",
        image="spark:python3",
        api_version="auto",
        auto_remove="success",
        docker_url=DOCKER_URL,
        network_mode=DOCKER_NETWORK,
        mount_tmp_dir=False,
        command=[
            "/opt/spark/bin/spark-submit",
            "/opt/spark_data/spark_jobs/clean_taxi_data.py",
        ],
        mounts=[
            Mount(
                source=f"{HOST_PROJECT_DIR}/raw_data",
                target="/opt/spark_data/raw_data",
                type="bind",
                read_only=True,
            ),
            Mount(
                source=f"{HOST_PROJECT_DIR}/spark_jobs",
                target="/opt/spark_data/spark_jobs",
                type="bind",
                read_only=True,
            ),
            Mount(
                source=f"{HOST_PROJECT_DIR}/processed_data",
                target="/opt/spark_data/processed_data",
                type="bind",
                read_only=False,
            ),
        ],
    )

    # ---- Luồng 8: Airflow -> staging (xem docs/roadmap.md) ----
    # Tương đương lệnh thủ công: python load_parquet_to_staging.py
    # Image "taxi-loader:latest" build từ docker/taxi-loader/ (xem
    # docker-compose.yml, service build-only "taxi-loader").
    load_staging = DockerOperator(
        task_id="load_staging",
        image="taxi-loader:latest",
        api_version="auto",
        auto_remove="success",
        docker_url=DOCKER_URL,
        network_mode=DOCKER_NETWORK,
        mount_tmp_dir=False,
        working_dir="/app",
        # Giới hạn RAM tường minh -- trước đây KHÔNG set, khiến container
        # này có thể phình to không kiểm soát và làm cả máy ảo WSL2 hết RAM
        # (OOM Kill toàn hệ thống, StatusCode 137 -- xem docs/troubleshooting.md).
        # Từ khi load_parquet_to_staging.py đọc Parquet theo batch (streaming,
        # xem LOADER_BATCH_SIZE), RAM cần cho container này rất nhỏ và ổn
        # định -- 512m dư sức cho batch mặc định 200,000 dòng/lô.
        # Giới hạn RAM tường minh. Từng thử 512m nhưng quá sát: page cache
        # của file Parquet đang đọc (bind-mount từ Windows) bị tính vào
        # giới hạn cgroup, gây "thrashing" (CPU 100% nhưng gần như đứng im
        # trong nhiều giờ) thay vì OOM rõ ràng -- xem docs/troubleshooting.md.
        # 1536m đủ dư cho batch 200,000 dòng + page cache của file, không
        # còn phải giành giật bộ nhớ liên tục.
        mem_limit="1536m",
        environment={
            "DB_HOST": DB_HOST,
            "DB_PORT": "5432",
            "DB_NAME": DB_NAME,
            "DB_USER": DB_USER,
            "DB_PASSWORD": DB_PASSWORD,
            # Số dòng xử lý mỗi lô (xem load_parquet_to_staging.py). Giảm
            # xuống (vd. "100000") nếu vẫn OOM ở mem_limit hiện tại; tăng
            # lên nếu muốn chạy nhanh hơn và có dư RAM.
            "LOADER_BATCH_SIZE": os.environ.get("LOADER_BATCH_SIZE", "200000"),
        },
        mounts=[
            Mount(
                source=f"{HOST_PROJECT_DIR}/processed_data",
                target="/app/processed_data",
                type="bind",
                read_only=True,
            ),
        ],
    )


    # ---- Luồng 9: Airflow -> dbt (xem docs/roadmap.md) ----
    # Tương đương lệnh thủ công:
    #   dbt build --project-dir dbt --profiles-dir dbt
    # Image "taxi-dbt:latest" build từ docker/taxi-dbt/ (xem
    # docker-compose.yml, service build-only "taxi-dbt") — KHÔNG dùng chung
    # image với Airflow, tránh xung đột dependency (xem airflow/Dockerfile).
    dbt_build = DockerOperator(
        task_id="dbt_build",
        image="taxi-dbt:latest",
        api_version="auto",
        auto_remove="success",
        docker_url=DOCKER_URL,
        network_mode=DOCKER_NETWORK,
        mount_tmp_dir=False,
        command=["build", "--project-dir", "/dbt/project", "--profiles-dir", "/dbt/project"],
        environment={
            "DBT_HOST": DB_HOST,
            "DBT_PORT": "5432",
            "DBT_DBNAME": DB_NAME,
            "DBT_USER": DB_USER,
            "DBT_PASSWORD": DB_PASSWORD,
            # Tránh UnicodeDecodeError do comment tiếng Việt trong file dbt
            # (giống lưu ý đã ghi trong docs/setup.md mục 12 khi chạy tay).
            "PYTHONUTF8": "1",
        },
        mounts=[
            Mount(
                source=f"{HOST_PROJECT_DIR}/dbt",
                target="/dbt/project",
                type="bind",
                read_only=False,
            ),
        ],
    )

    run_spark_job >> load_staging >> dbt_build