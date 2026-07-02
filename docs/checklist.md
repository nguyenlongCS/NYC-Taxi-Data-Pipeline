# Checklist — Đã thực hiện

## Hạ tầng
- [x] Cài Docker Desktop, viết `docker-compose.yml` (Postgres + pgAdmin + Metabase)
- [x] Named volume cho cả 3 service (`pgdata`, `pgadmin_data`, `metabase_data`) — persist qua restart

## Dữ liệu
- [x] Tải dataset NYC Yellow Taxi 2015-2016 từ Kaggle (7.4GB, 4 file)
- [x] Khảo sát cấu trúc CSV gốc (19 cột, dùng lat/long thay vì zone ID)
- [x] Chọn phạm vi dùng 2 file (2016-01, 2016-02 — ~3.5GB) cho bản rút gọn 1 tuần

## ETL
- [x] `01_create_schema.sql` — tạo schema `staging` + `dwh`, toàn bộ bảng dim/fact
- [x] `load_staging.py` — nạp CSV vào staging bằng `psycopg2.COPY` (22,288,907 dòng)
- [x] `02_transform_load.sql` — sinh `dim_date`, `dim_time`, transform + lọc dữ liệu bẩn vào `fact_trips` (21,792,952 dòng, lọc ~2.2%)
- [x] Sửa lỗi TRUNCATE + FK constraint → script idempotent, chạy lại an toàn

## Phân tích & Dashboard
- [x] 5 câu SQL phân tích trong `sql/analytics/` (doanh thu theo giờ, xu hướng theo tuần, phân bố thanh toán, tip theo vendor, rush hour impact)
- [x] Kết nối Metabase tới `taxi_dwh`, tạo 5 Question + gộp thành 1 Dashboard
- [x] Sửa lỗi chart nhiều trục Y (chỉ giữ 1 metric chính mỗi chart)

## Tài liệu (`docs/`)
- [x] `dataset.md`, `setup.md`, `project_structure.md`, `notes.md`
- [x] `pipeline.md`, `data_dictionary.md`, `troubleshooting.md`
- [x] `roadmap.md` — kế hoạch mở rộng (dbt, Spark, Airflow, REST API) kèm sơ đồ 10 luồng
- [x] `README.md` ở thư mục gốc — tổng quan, quickstart, liên kết tới toàn bộ docs

## Chưa làm (xem `docs/roadmap.md`)
- [ ] dbt — thay transform SQL thủ công
- [ ] Spark — xử lý toàn bộ 4 file (~7.4GB)
- [ ] Airflow — orchestrate pipeline theo lịch
- [ ] REST API — expose dữ liệu qua FastAPI
