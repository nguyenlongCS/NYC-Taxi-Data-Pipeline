# Checklist — Đã thực hiện

## Hạ tầng
- [x] Cài Docker Desktop, viết `docker-compose.yml` (Postgres + pgAdmin + Metabase + Spark)
- [x] Named volume cho cả 3 service DB/BI (`pgdata`, `pgadmin_data`, `metabase_data`) — persist qua restart

## Dữ liệu
- [x] Tải dataset NYC Yellow Taxi 2015-2016 từ Kaggle (7.4GB, 4 file)
- [x] Khảo sát cấu trúc CSV gốc (19 cột, dùng lat/long thay vì zone ID)
- [x] Chọn phạm vi dùng 2 file (2016-01, 2016-02 — ~3.5GB) 

## ETL (SQL thủ công — bản gốc, xem `sql/archive/`)
- [x] `01_create_schema.sql` — tạo schema `staging` + `dwh`, toàn bộ bảng dim/fact
- [x] `load_staging.py` — nạp CSV vào staging bằng `psycopg2.COPY` (22,288,907 dòng)
- [x] `02_transform_load.sql` — sinh `dim_date`, `dim_time`, transform + lọc dữ liệu bẩn vào `fact_trips` (21,792,952 dòng, lọc ~2.2%)
- [x] Sửa lỗi TRUNCATE + FK constraint → script idempotent, chạy lại an toàn

## ETL (dbt — thay thế `02_transform_load.sql`, xem `dbt/`)
- [x] Khởi tạo dbt project + kết nối `taxi_dwh` (venv Python 3.12 riêng — dbt chưa hỗ trợ 3.14)
- [x] Staging layer — `stg_yellow_trips` (source `staging.yellow_trips`, chỉ rename cột)
- [x] Intermediate layer — `int_yellow_trips_keyed` (surrogate key `date_id`/`time_id`, `trip_duration_min`)
- [x] Marts layer — `dim_date`, `dim_time`, seeds (`dim_vendor`, `dim_payment_type`, `dim_rate_code`), `fact_trips` (incremental, áp đủ 5 điều kiện lọc gốc)
- [x] Đối chiếu số liệu khớp 100% bản gốc: `dim_date` 506, `dim_time` 1440, `fact_trips` 21,792,952
- [x] dbt tests — 8 cột FK (`not_null` + `relationships`) + 5 singular test ứng 5 điều kiện lọc gốc → **38/38 PASS**
- [x] Archive `02_transform_load.sql` ra `sql/archive/`, rút gọn `01_create_schema.sql` (bỏ DDL `dwh.*`)

## ETL (Spark — thay thế `load_staging.py` cho khối lượng lớn, xem `spark_jobs/`)
- [x] Thêm service `spark` vào `docker-compose.yml` — image `spark:python3` (Docker Official Image, Spark 4.1.2, local mode)
  - ⚠️ Đổi từ `bitnami/spark:3.5` ban đầu — Bitnami ngừng phát hành tag miễn phí từ giữa 2025 (xem `troubleshooting.md` mục 12)
- [x] `spark_jobs/clean_taxi_data.py` — đọc 2 file CSV, ép kiểu dữ liệu khớp `staging.yellow_trips` (DecimalType, TimestampType), audit NULL sinh ra do cast lỗi, ghi Parquet (`processed_data/yellow_trips_clean/`, 8 file)
  - Tắt `spark.sql.ansi.enabled` (Spark 4.x mặc định bật, khác hành vi cast của Spark 3.x — xem `troubleshooting.md` mục 13)
  - Gộp toàn bộ audit + checksum vào 1 lượt `.agg()` duy nhất, không dùng `.cache()` — tránh OOM khi xử lý 22 triệu dòng trong container giới hạn RAM
- [x] `load_parquet_to_staging.py` — đọc từng file Parquet, nạp vào `staging.yellow_trips` bằng `psycopg2.COPY` (thay thế vai trò `load_staging.py`, giữ lại file cũ làm phương án dự phòng)
- [x] Đối chiếu checksum khớp 100% với staging nạp bằng CSV trực tiếp: count 22,288,907; `SUM(total_amount)` 348,188,436.08; `SUM(trip_distance)` 108,299,074.48; `SUM(fare_amount)` 277,491,448.58

## Phân tích & Dashboard
- [x] 5 câu SQL phân tích trong `sql/analytics/` (doanh thu theo giờ, xu hướng theo tuần, phân bố thanh toán, tip theo vendor, rush hour impact)
- [x] Kết nối Metabase tới `taxi_dwh`, tạo 5 Question + gộp thành 1 Dashboard
- [x] Sửa lỗi chart nhiều trục Y (chỉ giữ 1 metric chính mỗi chart)

## Tài liệu (`docs/`)
- [x] `dataset.md`, `setup.md`, `project_structure.md`, `notes.md`
- [x] `pipeline.md`, `data_dictionary.md`, `troubleshooting.md`
- [x] `roadmap.md` — kế hoạch mở rộng (dbt, Spark, Airflow, REST API) kèm sơ đồ 10 luồng
- [x] `README.md` ở thư mục gốc — tổng quan, quickstart, liên kết tới toàn bộ docs
- [x] `dbt/README.md` — setup venv, lệnh chạy dbt, các lỗi Windows đã gặp

## Chưa làm (xem `docs/roadmap.md`)
- [ ] `dbt docs generate` — sinh lineage graph cho portfolio
- [ ] Spark — mở rộng xử lý toàn bộ 4 file (~7.4GB), hiện mới dùng 2 file như các giai đoạn trước
- [ ] Airflow — orchestrate pipeline theo lịch
- [ ] REST API — expose dữ liệu qua FastAPI
