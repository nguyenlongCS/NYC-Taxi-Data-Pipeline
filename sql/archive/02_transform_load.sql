-- ============================================================
-- 02_transform_load.sql
-- Sinh dim_date, dim_time và nạp dữ liệu đã làm sạch vào fact_trips
-- Chạy sau khi staging.yellow_trips đã có dữ liệu (22.28 triệu dòng)
-- ============================================================

-- ------------------------------------------------------------
-- 0. DỌN CẢ 3 BẢNG TRONG CÙNG 1 CÂU LỆNH
-- Postgres luôn từ chối TRUNCATE một bảng bị bảng khác tham chiếu FK
-- (fact_trips → dim_date, fact_trips → dim_time), BẤT KỂ bảng tham
-- chiếu đó có dữ liệu hay không. Cách đúng: liệt kê TẤT CẢ các bảng
-- liên quan trong CÙNG MỘT câu TRUNCATE để Postgres không cần kiểm
-- tra ràng buộc chéo giữa chúng.
-- (Script này idempotent - chạy lại bao nhiêu lần cũng an toàn,
--  miễn là chỉ chạy 1 session tại 1 thời điểm.)
-- ------------------------------------------------------------
TRUNCATE dwh.fact_trips, dwh.dim_date, dwh.dim_time;

-- ------------------------------------------------------------
-- 1. SINH dim_date
-- Lấy khoảng ngày thực tế từ staging (cả pickup lẫn dropoff,
-- vì chuyến gần nửa đêm cuối tháng có thể dropoff sang ngày/tháng kế)
-- ------------------------------------------------------------

INSERT INTO dwh.dim_date (date_id, full_date, day, month, quarter, year, day_of_week, day_name, is_weekend)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER                       AS date_id,
    d::DATE                                                 AS full_date,
    EXTRACT(DAY FROM d)::SMALLINT                            AS day,
    EXTRACT(MONTH FROM d)::SMALLINT                           AS month,
    EXTRACT(QUARTER FROM d)::SMALLINT                          AS quarter,
    EXTRACT(YEAR FROM d)::SMALLINT                              AS year,
    EXTRACT(ISODOW FROM d)::SMALLINT                             AS day_of_week,   -- 1=Mon..7=Sun
    TO_CHAR(d, 'Day')                                              AS day_name,
    EXTRACT(ISODOW FROM d) IN (6, 7)                                AS is_weekend
FROM (
    SELECT generate_series(
        (SELECT LEAST(MIN(tpep_pickup_datetime)::DATE, MIN(tpep_dropoff_datetime)::DATE) FROM staging.yellow_trips),
        (SELECT GREATEST(MAX(tpep_pickup_datetime)::DATE, MAX(tpep_dropoff_datetime)::DATE) FROM staging.yellow_trips),
        interval '1 day'
    ) AS d
) AS date_series;

-- ------------------------------------------------------------
-- 2. SINH dim_time (1440 phút trong ngày, dùng chung pickup/dropoff)
-- ------------------------------------------------------------
INSERT INTO dwh.dim_time (time_id, hour, minute, time_period, is_rush_hour)
SELECT
    m                                                             AS time_id,
    (m / 60)::SMALLINT                                             AS hour,
    (m % 60)::SMALLINT                                              AS minute,
    CASE
        WHEN (m / 60) BETWEEN 5 AND 8   THEN 'Sáng sớm'
        WHEN (m / 60) BETWEEN 9 AND 11  THEN 'Sáng'
        WHEN (m / 60) BETWEEN 12 AND 13 THEN 'Trưa'
        WHEN (m / 60) BETWEEN 14 AND 17 THEN 'Chiều'
        WHEN (m / 60) BETWEEN 18 AND 21 THEN 'Tối'
        ELSE 'Đêm khuya'
    END                                                              AS time_period,
    (m / 60) IN (7, 8, 9, 16, 17, 18, 19)                              AS is_rush_hour
FROM generate_series(0, 1439) AS m;

-- ------------------------------------------------------------
-- 3. NẠP fact_trips TỪ staging — kèm làm sạch dữ liệu
-- Điều kiện lọc bỏ dữ liệu bẩn phổ biến trong taxi data:
--   - trip_distance <= 0 hoặc quá lớn bất thường (>100 dặm)
--   - fare_amount <= 0
--   - passenger_count = 0
--   - tọa độ (0,0) → GPS lỗi, không nằm trong khu vực NYC
--   - dropoff sớm hơn hoặc bằng pickup
-- ------------------------------------------------------------
INSERT INTO dwh.fact_trips (
    pickup_date_id, pickup_time_id, dropoff_date_id, dropoff_time_id,
    vendor_id, payment_type_id, rate_code_id,
    pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude,
    passenger_count, trip_distance, trip_duration_min,
    fare_amount, extra, mta_tax, tip_amount, tolls_amount,
    improvement_surcharge, total_amount
)
SELECT
    TO_CHAR(s.tpep_pickup_datetime, 'YYYYMMDD')::INTEGER                          AS pickup_date_id,
    (EXTRACT(HOUR FROM s.tpep_pickup_datetime) * 60
        + EXTRACT(MINUTE FROM s.tpep_pickup_datetime))::INTEGER                   AS pickup_time_id,
    TO_CHAR(s.tpep_dropoff_datetime, 'YYYYMMDD')::INTEGER                          AS dropoff_date_id,
    (EXTRACT(HOUR FROM s.tpep_dropoff_datetime) * 60
        + EXTRACT(MINUTE FROM s.tpep_dropoff_datetime))::INTEGER                   AS dropoff_time_id,
    s.vendor_id,
    s.payment_type                                                                  AS payment_type_id,
    s.rate_code_id,
    s.pickup_longitude, s.pickup_latitude, s.dropoff_longitude, s.dropoff_latitude,
    s.passenger_count,
    s.trip_distance,
    EXTRACT(EPOCH FROM (s.tpep_dropoff_datetime - s.tpep_pickup_datetime)) / 60.0   AS trip_duration_min,
    s.fare_amount, s.extra, s.mta_tax, s.tip_amount, s.tolls_amount,
    s.improvement_surcharge, s.total_amount
FROM staging.yellow_trips s
WHERE s.trip_distance > 0 AND s.trip_distance < 100
  AND s.fare_amount > 0
  AND s.passenger_count > 0
  AND s.pickup_longitude  BETWEEN -74.3 AND -73.7
  AND s.pickup_latitude   BETWEEN  40.5 AND  40.9
  AND s.dropoff_longitude BETWEEN -74.3 AND -73.7
  AND s.dropoff_latitude  BETWEEN  40.5 AND  40.9
  AND s.tpep_dropoff_datetime > s.tpep_pickup_datetime
  -- Khớp với khoảng dim_date đã sinh (tránh lỗi FK nếu có dữ liệu ngoài khoảng)
  AND s.rate_code_id IN (SELECT rate_code_id FROM dwh.dim_rate_code)
  AND s.payment_type IN (SELECT payment_type_id FROM dwh.dim_payment_type);

-- ------------------------------------------------------------
-- 4. KIỂM TRA NHANH SAU KHI NẠP
-- ------------------------------------------------------------
SELECT 'staging.yellow_trips' AS table_name, COUNT(*) AS row_count FROM staging.yellow_trips
UNION ALL
SELECT 'dwh.fact_trips', COUNT(*) FROM dwh.fact_trips
UNION ALL
SELECT 'dwh.dim_date', COUNT(*) FROM dwh.dim_date
UNION ALL
SELECT 'dwh.dim_time', COUNT(*) FROM dwh.dim_time;