#!/usr/bin/env bash
# airflow/scripts/entrypoint-init.sh
#
# Chạy 1 lần bởi service airflow-init (xem docker-compose.yml). Gọi bằng
# `entrypoint: ["bash", "/opt/airflow/scripts/entrypoint-init.sh"]` -- KHÔNG
# dựa vào execute-bit của file mount từ host (bind-mount từ Windows thường
# mất execute-bit), nên luôn gọi tường minh qua "bash ...".
set -euo pipefail

echo "== Bước 1/4: Tạo database airflow_db (nếu chưa có) =="
python /opt/airflow/scripts/create_airflow_db.py

echo "== Bước 2/4: airflow db migrate =="
airflow db migrate

echo "== Bước 3/4: Tạo user admin (nếu chưa có) =="
airflow users create \
    --username "${AIRFLOW_ADMIN_USER}" \
    --password "${AIRFLOW_ADMIN_PASSWORD}" \
    --firstname "${AIRFLOW_ADMIN_FIRSTNAME}" \
    --lastname "${AIRFLOW_ADMIN_LASTNAME}" \
    --role Admin \
    --email "${AIRFLOW_ADMIN_EMAIL}" \
    || echo "User '${AIRFLOW_ADMIN_USER}' có thể đã tồn tại -- bỏ qua lỗi tạo user."

echo "== Bước 4/4: Kiểm tra DAG import (phát hiện sớm lỗi 'DagBag rỗng') =="
airflow dags reserialize || true
IMPORT_ERRORS="$(airflow dags list-import-errors 2>&1)"
echo "${IMPORT_ERRORS}"
if echo "${IMPORT_ERRORS}" | grep -qi "error"; then
    echo "!! Phát hiện lỗi import DAG ở trên -- kiểm tra airflow/dags/ trước khi tiếp tục."
    exit 1
fi

echo "airflow-init hoàn tất."
