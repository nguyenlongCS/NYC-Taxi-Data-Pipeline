-- ============================================================
-- 01_create_schema.sql
-- Tạo schema staging + bảng thô cho NYC Yellow Taxi DWH
-- Nguồn: Kaggle elemento/nyc-yellow-taxi-trip-data (2015-2016)
--
-- ⚠️ THAY ĐỔI QUAN TRỌNG (sau khi áp dụng dbt — xem docs/roadmap.md):
-- Toàn bộ DDL cho schema `dwh` (dim_date, dim_time, dim_vendor,
-- dim_payment_type, dim_rate_code, fact_trips) đã được XÓA khỏi file
-- này. Các bảng đó giờ do dbt tự tạo khi chạy `dbt build`:
--   - dim_date, dim_time, fact_trips  → dbt/models/marts/
--   - dim_vendor, dim_payment_type,
--     dim_rate_code                  → dbt/seeds/ (dbt seed)
--
-- File cũ có DDL đầy đủ được lưu tham khảo tại sql/archive/02_transform_load.sql
-- (KHÔNG đặt trong sql/ gốc — Docker docker-entrypoint-initdb.d chỉ quét
-- file trực tiếp trong thư mục, không đệ quy vào thư mục con, nên file
-- archive không bị tự động chạy lại).
--
-- File này CHỈ còn tạo schema `staging` (nơi load_staging.py nạp CSV) và
-- schema `dwh` rỗng (dbt tự tạo bảng bên trong khi chạy `dbt build`, nhưng
-- tạo sẵn schema ở đây để pgAdmin/Metabase thấy ngay cả trước khi chạy dbt
-- lần đầu).
-- ============================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dwh;

-- ------------------------------------------------------------
-- STAGING TABLE — khớp 1-1 với cột gốc trong file CSV
-- Bảng này KHÔNG do dbt quản lý — dbt chỉ đọc (source), không transform
-- ngược lại bảng này. Nạp dữ liệu bằng load_staging.py (xem docs/pipeline.md).
-- ------------------------------------------------------------
DROP TABLE IF EXISTS staging.yellow_trips;
CREATE TABLE staging.yellow_trips (
    vendor_id               INTEGER,
    tpep_pickup_datetime    TIMESTAMP,
    tpep_dropoff_datetime   TIMESTAMP,
    passenger_count         INTEGER,
    trip_distance           NUMERIC(10,2),
    pickup_longitude        NUMERIC(11,7),
    pickup_latitude         NUMERIC(11,7),
    rate_code_id            INTEGER,
    store_and_fwd_flag      CHAR(1),
    dropoff_longitude       NUMERIC(11,7),
    dropoff_latitude        NUMERIC(11,7),
    payment_type            INTEGER,
    fare_amount              NUMERIC(10,2),
    extra                    NUMERIC(10,2),
    mta_tax                  NUMERIC(10,2),
    tip_amount                NUMERIC(10,2),
    tolls_amount               NUMERIC(10,2),
    improvement_surcharge      NUMERIC(10,2),
    total_amount                NUMERIC(10,2)
);