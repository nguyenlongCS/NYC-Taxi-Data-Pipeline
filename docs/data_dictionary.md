# Data Dictionary — Từ điển dữ liệu

Mô tả chi tiết toàn bộ bảng và cột trong hai schema `staging` và `dwh` của database `taxi_dwh`.

## Schema `staging`

### `staging.yellow_trips`
Bảng thô, khớp 1-1 với cấu trúc CSV gốc từ Kaggle. Không có ràng buộc khóa chính/khóa ngoại, không lọc dữ liệu — mục đích là giữ nguyên dữ liệu gốc để đối chiếu khi cần.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `vendor_id` | INTEGER | Mã nhà cung cấp thiết bị taxi (xem `dwh.dim_vendor`) |
| `tpep_pickup_datetime` | TIMESTAMP | Thời điểm đón khách |
| `tpep_dropoff_datetime` | TIMESTAMP | Thời điểm trả khách |
| `passenger_count` | INTEGER | Số hành khách |
| `trip_distance` | NUMERIC(10,2) | Quãng đường (dặm) |
| `pickup_longitude` / `pickup_latitude` | NUMERIC(11,7) | Tọa độ điểm đón |
| `rate_code_id` | INTEGER | Mã biểu giá (xem `dwh.dim_rate_code`) |
| `store_and_fwd_flag` | CHAR(1) | Cờ lưu tạm do mất kết nối trước khi gửi (`Y`/`N`) |
| `dropoff_longitude` / `dropoff_latitude` | NUMERIC(11,7) | Tọa độ điểm trả |
| `payment_type` | INTEGER | Mã hình thức thanh toán (xem `dwh.dim_payment_type`) |
| `fare_amount` | NUMERIC(10,2) | Giá cước cơ bản |
| `extra` | NUMERIC(10,2) | Phụ phí |
| `mta_tax` | NUMERIC(10,2) | Thuế MTA |
| `tip_amount` | NUMERIC(10,2) | Tiền tip |
| `tolls_amount` | NUMERIC(10,2) | Phí cầu đường |
| `improvement_surcharge` | NUMERIC(10,2) | Phụ phí cải thiện dịch vụ |
| `total_amount` | NUMERIC(10,2) | Tổng tiền |

**Số dòng thực tế:** 22,288,907 (từ 2 file `yellow_tripdata_2016-01.csv` + `2016-02.csv`)

---

## Schema `dwh` — Star Schema

### `dwh.fact_trips` (Fact table)
**Grain (độ chi tiết):** 1 dòng = 1 chuyến taxi.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `trip_id` | BIGSERIAL (PK) | Khóa chính tự sinh |
| `pickup_date_id` | INTEGER (FK → `dim_date`) | Ngày đón khách |
| `pickup_time_id` | INTEGER (FK → `dim_time`) | Phút trong ngày lúc đón khách |
| `dropoff_date_id` | INTEGER (FK → `dim_date`) | Ngày trả khách |
| `dropoff_time_id` | INTEGER (FK → `dim_time`) | Phút trong ngày lúc trả khách |
| `vendor_id` | INTEGER (FK → `dim_vendor`) | Nhà cung cấp thiết bị |
| `payment_type_id` | INTEGER (FK → `dim_payment_type`) | Hình thức thanh toán |
| `rate_code_id` | INTEGER (FK → `dim_rate_code`) | Biểu giá áp dụng |
| `pickup_longitude`, `pickup_latitude` | NUMERIC(11,7) | Tọa độ điểm đón (degenerate — chưa map sang borough/zone, xem `dataset.md`) |
| `dropoff_longitude`, `dropoff_latitude` | NUMERIC(11,7) | Tọa độ điểm trả |
| `passenger_count` | INTEGER | Số hành khách |
| `trip_distance` | NUMERIC(10,2) | Quãng đường (dặm) |
| `trip_duration_min` | NUMERIC(10,2) | Thời lượng chuyến đi (phút) — cột tính toán, sinh từ `dropoff - pickup` |
| `fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `improvement_surcharge`, `total_amount` | NUMERIC(10,2) | Các thành phần giá cước (measures) |

**Điều kiện lọc khi nạp từ staging** (chi tiết xem `notes.md`):
1. `trip_distance > 0 AND trip_distance < 100` (dặm)
2. `fare_amount > 0`
3. `passenger_count > 0`
4. Tọa độ pickup/dropoff nằm trong bounding box hợp lý của NYC (`longitude` -74.3 → -73.7, `latitude` 40.5 → 40.9)
5. `tpep_dropoff_datetime > tpep_pickup_datetime`

**Số dòng sau khi lọc:** 21,792,952 (từ 22,288,907 dòng staging — lọc bỏ ~2.2%)

### `dwh.dim_date` (Dimension)
Mỗi dòng là 1 ngày, sinh tự động theo khoảng ngày thực tế xuất hiện trong dữ liệu.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `date_id` | INTEGER (PK) | Định dạng `YYYYMMDD`, ví dụ `20160115` |
| `full_date` | DATE | Ngày đầy đủ |
| `day`, `month`, `quarter`, `year` | SMALLINT | Thành phần ngày/tháng/quý/năm |
| `day_of_week` | SMALLINT | 1 = Thứ Hai ... 7 = Chủ Nhật (chuẩn ISO) |
| `day_name` | VARCHAR(10) | Tên thứ (Monday, Tuesday...) — lưu ý có khoảng trắng thừa do `TO_CHAR(..., 'Day')` của Postgres, dùng `TRIM()` khi hiển thị |
| `is_weekend` | BOOLEAN | `true` nếu là Thứ Bảy/Chủ Nhật |

**Số dòng:** 506 (bao phủ toàn bộ ngày xuất hiện trong pickup lẫn dropoff của 2 tháng dữ liệu — nhiều hơn ~60 ngày dự kiến do có thể lẫn vài bản ghi timestamp lỗi trong dữ liệu thô; không ảnh hưởng `fact_trips` vì bảng đó đã được lọc riêng).

### `dwh.dim_time` (Dimension)
Mỗi dòng là 1 phút trong ngày, dùng chung cho cả pickup và dropoff.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `time_id` | INTEGER (PK) | 0-1439 (số phút tính từ 00:00) |
| `hour` | SMALLINT | Giờ (0-23) |
| `minute` | SMALLINT | Phút (0-59) |
| `time_period` | VARCHAR(20) | Khung giờ: Sáng sớm (5-8h) / Sáng (9-11h) / Trưa (12-13h) / Chiều (14-17h) / Tối (18-21h) / Đêm khuya (còn lại) |
| `is_rush_hour` | BOOLEAN | `true` nếu giờ thuộc khung 7-9h hoặc 16-19h |

**Số dòng:** 1440 (cố định, không đổi theo dữ liệu)

### `dwh.dim_vendor` (Dimension)
| `vendor_id` | `vendor_name` |
|---|---|
| 1 | Creative Mobile Technologies (CMT) |
| 2 | VeriFone Inc (VTS) |

### `dwh.dim_payment_type` (Dimension)
| `payment_type_id` | `payment_name` |
|---|---|
| 1 | Credit card |
| 2 | Cash |
| 3 | No charge |
| 4 | Dispute |
| 5 | Unknown |
| 6 | Voided trip |

### `dwh.dim_rate_code` (Dimension)
| `rate_code_id` | `rate_name` |
|---|---|
| 1 | Standard rate |
| 2 | JFK |
| 3 | Newark |
| 4 | Nassau or Westchester |
| 5 | Negotiated fare |
| 6 | Group ride |

---

## Sơ đồ quan hệ (tóm tắt)

```
dim_date ──┐
           ├──< fact_trips >── dim_vendor
dim_time ──┘        │
                     ├── dim_payment_type
                     └── dim_rate_code
```

`fact_trips` tham chiếu tới `dim_date` và `dim_time` **hai lần mỗi bảng** (1 lần cho pickup, 1 lần cho dropoff) — đây là kỹ thuật **role-playing dimension** phổ biến trong data warehouse modeling.
