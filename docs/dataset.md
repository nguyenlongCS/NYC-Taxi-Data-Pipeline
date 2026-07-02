# Dataset — NYC Yellow Taxi Trip Data

## Nguồn dữ liệu
- **Kaggle:** https://www.kaggle.com/datasets/elemento/nyc-yellow-taxi-trip-data?resource=download
- **Gốc:** NYC Taxi & Limousine Commission (TLC) — dữ liệu chuyến đi Yellow Taxi giai đoạn **2015-2016**

## Danh sách file & dung lượng

| File | Dung lượng | Trạng thái sử dụng trong dự án |
|---|---|---|
| `yellow_tripdata_2015-01.csv` | 1,985,964,692 bytes (~1.85 GB) | Dự phòng / mở rộng sau |
| `yellow_tripdata_2016-01.csv` | 1,708,674,492 bytes (~1.59 GB) | ✅ Dùng chính |
| `yellow_tripdata_2016-02.csv` | 1,783,554,554 bytes (~1.66 GB) | ✅ Dùng chính |
| `yellow_tripdata_2016-03.csv` | 1,914,669,757 bytes (~1.78 GB) | Dự phòng / mở rộng sau |
| **Tổng cộng** | 7,392,863,495 bytes (~7.4 GB) | |

> **Quyết định phạm vi:** dự án chỉ nạp **2016-01 + 2016-02** (~3.5 GB, **22,288,907 dòng** thực tế sau khi nạp vào staging) để thử nghiệm. Hai file `2015-01` và `2016-03` giữ lại làm phần mở rộng nếu muốn tăng khối lượng dữ liệu sau này.

## Cấu trúc cột gốc (19 cột)

Xác nhận bằng cách đọc thử 5 dòng đầu (`pd.read_csv(nrows=5)`):

| # | Cột | Kiểu dữ liệu | Mô tả |
|---|---|---|---|
| 1 | `VendorID` | int64 | Mã nhà cung cấp thiết bị taxi (1 hoặc 2) |
| 2 | `tpep_pickup_datetime` | str (→ timestamp khi nạp DB) | Thời điểm đón khách |
| 3 | `tpep_dropoff_datetime` | str (→ timestamp khi nạp DB) | Thời điểm trả khách |
| 4 | `passenger_count` | int64 | Số lượng hành khách |
| 5 | `trip_distance` | float64 | Quãng đường di chuyển (dặm) |
| 6 | `pickup_longitude` | float64 | Kinh độ điểm đón |
| 7 | `pickup_latitude` | float64 | Vĩ độ điểm đón |
| 8 | `RateCodeID` | int64 | Mã biểu giá áp dụng |
| 9 | `store_and_fwd_flag` | str | Cờ đánh dấu chuyến bị lưu tạm do mất kết nối với server trước khi gửi |
| 10 | `dropoff_longitude` | float64 | Kinh độ điểm trả |
| 11 | `dropoff_latitude` | float64 | Vĩ độ điểm trả |
| 12 | `payment_type` | int64 | Mã hình thức thanh toán |
| 13 | `fare_amount` | float64 | Giá cước cơ bản theo đồng hồ |
| 14 | `extra` | float64 | Phụ phí (giờ cao điểm, ban đêm...) |
| 15 | `mta_tax` | float64 | Thuế MTA cố định |
| 16 | `tip_amount` | float64 | Tiền tip |
| 17 | `tolls_amount` | float64 | Phí cầu đường |
| 18 | `improvement_surcharge` | float64 | Phụ phí cải thiện dịch vụ |
| 19 | `total_amount` | float64 | Tổng tiền thanh toán |

## Điểm quan trọng khi thiết kế schema

Dataset này thuộc giai đoạn **trước tháng 7/2016**, nên dùng **tọa độ pickup/dropoff (longitude/latitude)** để xác định vị trí — **KHÔNG có** `PULocationID`/`DOLocationID` (mã khu vực/zone) như dữ liệu TLC từ giữa 2016 trở đi.

**Hệ quả thiết kế:** `dim_location` **không được tách thành bảng riêng** trong star schema. Tọa độ được giữ làm thuộc tính trực tiếp trên `fact_trips` (xem chi tiết tại `data_dictionary.md`). Đây là lựa chọn có chủ đích để giữ phạm vi dự án gọn trong 1 tuần — hướng nâng cao (join tọa độ với ranh giới borough qua `geopandas`) được ghi lại như một bước mở rộng trong `pipeline.md`.