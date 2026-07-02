# Pipeline — Luồng xử lý dữ liệu

Tài liệu này mô tả chi tiết từng giai đoạn của pipeline, từ dữ liệu thô đến dashboard, kèm lý do kỹ thuật cho từng quyết định.

## Sơ đồ tổng quan

```
[CSV thô trên Kaggle]
        │  tải thủ công, giải nén vào raw_data/
        ▼
[raw_data/*.csv]  ── 2016-01, 2016-02 (~3.5 GB, 22,288,907 dòng)
        │  load_staging.py  (psycopg2 COPY, streaming, không load hết vào RAM)
        ▼
[staging.yellow_trips]  ── bảng thô, khớp 1-1 cấu trúc cột CSV gốc
        │  sql/02_transform_load.sql
        │  ├─ sinh dwh.dim_date (generate_series theo khoảng ngày thực tế)
        │  ├─ sinh dwh.dim_time (1440 dòng cố định)
        │  └─ transform + lọc dữ liệu bẩn → dwh.fact_trips
        ▼
[dwh.fact_trips + dim_date + dim_time + dim_vendor + dim_payment_type + dim_rate_code]
        │  Metabase kết nối trực tiếp qua network nội bộ Docker
        ▼
[sql/analytics/*.sql]  ── 5 câu truy vấn phân tích
        ▼
[Metabase Dashboard]  ── 5 chart tổng hợp
```

## Giai đoạn 1 — Extract (Trích xuất)

**Nguồn:** file CSV tải thủ công từ Kaggle (không dùng Kaggle API để giữ pipeline đơn giản trong phạm vi 1 tuần).

**Công cụ:** không cần script riêng — bước "extract" ở đây chỉ là tải & giải nén, vì dữ liệu đã ở dạng file tĩnh (khác với các pipeline production thường phải tự động hóa việc gọi API/database nguồn định kỳ).

## Giai đoạn 2 — Load vào Staging

**Script:** `load_staging.py`

**Kỹ thuật:** dùng `psycopg2.cursor.copy_expert()` với lệnh `COPY ... FROM STDIN` của PostgreSQL, stream trực tiếp file CSV qua kết nối mạng vào bảng `staging.yellow_trips` — **nhanh hơn nhiều lần** so với đọc qua `pandas` rồi `INSERT` từng dòng hoặc dùng `to_sql()`, và không cần load toàn bộ file vào RAM.

**Tại sao có bước staging riêng** (thay vì transform thẳng từ CSV vào fact_trips)? Tách staging giúp:
- Debug dễ hơn: nếu transform sai, dữ liệu gốc vẫn còn nguyên trong staging để đối chiếu.
- Tái sử dụng: nếu muốn thử nghiệm logic làm sạch khác, không cần nạp lại CSV từ đầu (chỉ cần chạy lại bước transform).

**Kết quả thực tế:** 2 file × ~130-135 giây/file, tổng 22,288,907 dòng.

## Giai đoạn 3 — Transform & Load vào Data Warehouse

**Script:** `sql/02_transform_load.sql`

**Ba bước con, chạy tuần tự trong 1 script:**

1. **Sinh `dim_date`** — dùng `generate_series()` giữa `MIN`/`MAX` ngày thực tế xuất hiện trong staging (cả pickup lẫn dropoff), không hardcode khoảng ngày.
2. **Sinh `dim_time`** — 1440 dòng cố định (mỗi phút trong ngày), tính sẵn `time_period` (Sáng/Trưa/Chiều/Tối...) và `is_rush_hour`.
3. **Transform + nạp `fact_trips`** — `SELECT` từ `staging.yellow_trips`, join tính surrogate key cho các dimension theo thời gian, đồng thời áp **5 điều kiện lọc dữ liệu bẩn** (xem `data_dictionary.md` mục `fact_trips` để biết chi tiết từng điều kiện).

**Vì sao dùng SQL thuần thay vì dbt/pandas cho bước transform?** Với phạm vi 1 tuần và khối lượng dữ liệu vừa phải (~22 triệu dòng), SQL chạy trực tiếp trong Postgres tận dụng được engine tối ưu sẵn có, tránh chi phí học thêm công cụ mới. dbt được ghi nhận là hướng nâng cấp hợp lý nếu mở rộng dự án (xem phần Hướng mở rộng).

## Giai đoạn 4 — Serve (Phục vụ truy vấn/báo cáo)

**Công cụ:** Metabase, kết nối trực tiếp tới `taxi_dwh` qua network nội bộ Docker (host `postgres`, không phải `localhost`).

**5 câu truy vấn phân tích** (`sql/analytics/03` đến `07`) trả lời các câu hỏi nghiệp vụ cụ thể:
1. Doanh thu theo giờ trong ngày
2. Xu hướng theo ngày trong tuần
3. Phân bố hình thức thanh toán
4. Tip trung bình theo vendor
5. Ảnh hưởng của giờ cao điểm đến tốc độ di chuyển

Mỗi câu truy vấn được lưu thành 1 Question trong Metabase, sau đó gom vào 1 Dashboard duy nhất.

## Điều phối (Orchestration)

**Hiện tại:** chạy thủ công theo đúng thứ tự (`load_staging.py` → `02_transform_load.sql`), phù hợp vì dữ liệu là file tĩnh, không cần lịch chạy tự động.

**Nếu mở rộng thành pipeline chạy định kỳ** (ví dụ giả lập dữ liệu mới đến hàng ngày): cần thêm **Apache Airflow** để đóng gói 2 bước trên thành 1 DAG, tự động chạy theo lịch, có retry và alerting khi lỗi.
