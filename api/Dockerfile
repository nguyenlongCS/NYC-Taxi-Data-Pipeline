# api/Dockerfile
#
# Image cho service `api` — FastAPI đọc dữ liệu từ dwh.* (taxi_dwh) và
# expose endpoint trigger Airflow DAG (luồng 5, 6, 10 — xem docs/roadmap.md).
# Khác với docker/taxi-loader và docker/taxi-dbt (image build để Airflow
# gọi 1 lần qua DockerOperator rồi thoát), image này chạy SERVER thường
# trực (uvicorn), tương tự Metabase/pgAdmin.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
