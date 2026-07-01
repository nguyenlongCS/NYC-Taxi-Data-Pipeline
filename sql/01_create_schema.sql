-- ============================================================
-- 01_create_schema.sql
-- Tạo schema staging + star schema cho NYC Yellow Taxi DWH
-- Nguồn: Kaggle elemento/nyc-yellow-taxi-trip-data (2015-2016)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dwh;

-- ------------------------------------------------------------
-- 1. STAGING TABLE — khớp 1-1 với cột gốc trong file CSV
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

-- ------------------------------------------------------------
-- 2. DIMENSION TABLES
-- ------------------------------------------------------------

-- dim_date: mỗi dòng là 1 ngày, sinh trước cho khoảng thời gian dataset bao phủ
DROP TABLE IF EXISTS dwh.dim_date;
CREATE TABLE dwh.dim_date (
    date_id         INTEGER PRIMARY KEY,   -- dạng YYYYMMDD
    full_date        DATE NOT NULL,
    day              SMALLINT,
    month            SMALLINT,
    quarter          SMALLINT,
    year             SMALLINT,
    day_of_week      SMALLINT,             -- 1=Thứ Hai ... 7=Chủ Nhật
    day_name         VARCHAR(10),
    is_weekend       BOOLEAN
);

-- dim_time: mỗi dòng là 1 phút trong ngày (0-1439), dùng chung cho pickup & dropoff
DROP TABLE IF EXISTS dwh.dim_time;
CREATE TABLE dwh.dim_time (
    time_id          INTEGER PRIMARY KEY,  -- 0-1439 (số phút từ 00:00)
    hour             SMALLINT,
    minute           SMALLINT,
    time_period      VARCHAR(20),          -- Sáng sớm / Sáng / Trưa / Chiều / Tối / Đêm khuya
    is_rush_hour     BOOLEAN
);

-- dim_vendor: mã nhà cung cấp thiết bị taxi (theo tài liệu TLC)
DROP TABLE IF EXISTS dwh.dim_vendor;
CREATE TABLE dwh.dim_vendor (
    vendor_id        INTEGER PRIMARY KEY,
    vendor_name      VARCHAR(100)
);

-- dim_payment_type
DROP TABLE IF EXISTS dwh.dim_payment_type;
CREATE TABLE dwh.dim_payment_type (
    payment_type_id  INTEGER PRIMARY KEY,
    payment_name     VARCHAR(50)
);

-- dim_rate_code
DROP TABLE IF EXISTS dwh.dim_rate_code;
CREATE TABLE dwh.dim_rate_code (
    rate_code_id     INTEGER PRIMARY KEY,
    rate_name        VARCHAR(50)
);

-- ------------------------------------------------------------
-- 3. FACT TABLE
-- Grain: 1 dòng = 1 chuyến taxi
-- Hướng A: giữ lat/long trực tiếp trên fact (không tách dim_location tuần này)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS dwh.fact_trips;
CREATE TABLE dwh.fact_trips (
    trip_id                 BIGSERIAL PRIMARY KEY,
    pickup_date_id           INTEGER REFERENCES dwh.dim_date(date_id),
    pickup_time_id            INTEGER REFERENCES dwh.dim_time(time_id),
    dropoff_date_id             INTEGER REFERENCES dwh.dim_date(date_id),
    dropoff_time_id               INTEGER REFERENCES dwh.dim_time(time_id),
    vendor_id                       INTEGER REFERENCES dwh.dim_vendor(vendor_id),
    payment_type_id                   INTEGER REFERENCES dwh.dim_payment_type(payment_type_id),
    rate_code_id                        INTEGER REFERENCES dwh.dim_rate_code(rate_code_id),

    -- Thuộc tính vị trí (degenerate — chưa map sang borough/zone)
    pickup_longitude    NUMERIC(11,7),
    pickup_latitude     NUMERIC(11,7),
    dropoff_longitude   NUMERIC(11,7),
    dropoff_latitude    NUMERIC(11,7),

    -- Measures
    passenger_count      INTEGER,
    trip_distance        NUMERIC(10,2),
    trip_duration_min    NUMERIC(10,2),   -- sinh từ (dropoff - pickup)
    fare_amount           NUMERIC(10,2),
    extra                 NUMERIC(10,2),
    mta_tax                NUMERIC(10,2),
    tip_amount              NUMERIC(10,2),
    tolls_amount              NUMERIC(10,2),
    improvement_surcharge       NUMERIC(10,2),
    total_amount                 NUMERIC(10,2)
);

CREATE INDEX idx_fact_trips_pickup_date ON dwh.fact_trips(pickup_date_id);
CREATE INDEX idx_fact_trips_vendor ON dwh.fact_trips(vendor_id);

-- ------------------------------------------------------------
-- 4. Nạp sẵn dữ liệu tra cứu cho các dimension "tĩnh"
-- (dim_date và dim_time sẽ sinh bằng script riêng ở bước sau,
--  vì cần vòng lặp qua từng ngày/phút)
-- ------------------------------------------------------------

INSERT INTO dwh.dim_vendor (vendor_id, vendor_name) VALUES
    (1, 'Creative Mobile Technologies (CMT)'),
    (2, 'VeriFone Inc (VTS)');

INSERT INTO dwh.dim_payment_type (payment_type_id, payment_name) VALUES
    (1, 'Credit card'),
    (2, 'Cash'),
    (3, 'No charge'),
    (4, 'Dispute'),
    (5, 'Unknown'),
    (6, 'Voided trip');

INSERT INTO dwh.dim_rate_code (rate_code_id, rate_name) VALUES
    (1, 'Standard rate'),
    (2, 'JFK'),
    (3, 'Newark'),
    (4, 'Nassau or Westchester'),
    (5, 'Negotiated fare'),
    (6, 'Group ride');