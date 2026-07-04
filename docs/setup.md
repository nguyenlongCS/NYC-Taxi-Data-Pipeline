# Setup — Hướng dẫn thực hiện từng bước

## 1. Tải dataset từ Kaggle
https://www.kaggle.com/datasets/elemento/nyc-yellow-taxi-trip-data?resource=download

## 2. Giải nén và đặt tên `/raw_data`

## 3. Xem tên file và dung lượng từng file
```
cmd: dir raw_data
```
```
Directory of D:\Project\NYC-Taxi-Data-Pipeline\raw_data
07/01/2026  02:20 PM    <DIR>          .
07/01/2026  02:20 PM    <DIR>          ..
12/09/2021  07:31 AM     1,985,964,692 yellow_tripdata_2015-01.csv
12/09/2021  07:33 AM     1,708,674,492 yellow_tripdata_2016-01.csv
12/09/2021  07:36 AM     1,783,554,554 yellow_tripdata_2016-02.csv
12/09/2021  07:38 AM     1,914,669,757 yellow_tripdata_2016-03.csv
        4 File(s)  7,392,863,495 bytes
        2 Dir(s)  12,679,499,776 bytes free
```

## 4. Kiểm tra nhanh cấu trúc dữ liệu bằng Python (không cần load hết vào RAM)
```python
import pandas as pd

# chỉ đọc 5 dòng đầu để xem cột
df_sample = pd.read_csv("raw_data/yellow_tripdata_2015-01.csv", nrows=5)
print(df_sample.columns.tolist())
print(df_sample.dtypes)
print(df_sample.head())

# đếm số dòng thực tế mà không load hết (đọc theo chunk)
total_rows = sum(1 for _ in open("raw_data/yellow_tripdata_2015-01.csv"))
print(f"Tổng số dòng: {total_rows:,}")
```

Output xác nhận 19 cột, dùng tọa độ pickup/dropoff (xem chi tiết tại `dataset.md`):
```
PS D:\Project\NYC-Taxi-Data-Pipeline> python main.py
['VendorID', 'tpep_pickup_datetime', 'tpep_dropoff_datetime', 'passenger_count', 'trip_distance', 'pickup_longitude', 'pickup_latitude', 'RateCodeID', 'store_and_fwd_flag', 'dropoff_longitude', 'dropoff_latitude', 'payment_type', 'fare_amount', 'extra', 'mta_tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount']
...
[5 rows x 19 columns]
```

## 5. Tạo file `docker-compose.yml` và `sql/01_create_schema.sql`
Xem nội dung đầy đủ trong repo — 3 service: `postgres`, `pgadmin`, `metabase`, mỗi service có named volume riêng để persist dữ liệu qua các lần restart.

`sql/01_create_schema.sql` (chạy tự động khi container Postgres khởi tạo lần đầu qua
`docker-entrypoint-initdb.d`) hiện chỉ tạo schema `staging`/`dwh` rỗng + bảng
`staging.yellow_trips` — toàn bộ bảng `dim_*`/`fact_trips` bên trong `dwh` **không còn
được tạo ở đây nữa**, mà do dbt tự tạo khi chạy `dbt build` (xem mục 10-11 bên dưới).

## 6. Khởi động Docker (cài Docker Desktop trước)
```powershell
docker compose up -d
```
```
PS D:\Project\NYC-Taxi-Data-Pipeline> docker compose up -d
[+] up 6/11
 ✔ Image dpage/pgadmin4                Pulled                                                                   5.1s
 ✔ Network nyctaxidatapipeline_default Created                                                                  0.1s
 ✔ Volume nyctaxidatapipeline_pgdata   Created                                                                  0.0s
 ✔ Container taxi_postgres             Started                                                                  1.0s
 ✔ Container taxi_metabase             Started                                                                  1.1s
 ✔ Container taxi_pgadmin              Started                                                                  1.1s
```

## 7. Đặt `load_staging.py` vào thư mục gốc project
Ngang hàng với `raw_data/` và `docker-compose.yml`.

## 8. Cài thư viện
```powershell
pip install psycopg2-binary
```

## 9. Chạy nạp dữ liệu vào staging
```powershell
python load_staging.py
```
```
→ Đang nạp yellow_tripdata_2016-01.csv (1.71 GB)...
  Xong trong 130.2 giây.
→ Đang nạp yellow_tripdata_2016-02.csv (1.78 GB)...
  Xong trong 135.6 giây.

Tổng số dòng trong staging.yellow_trips: 22,288,907
```

## 10. Setup dbt (thay cho việc viết `02_transform_load.sql` thủ công)

⚠️ **Lưu ý quan trọng:** dbt-core (qua thư viện `mashumaro`) chưa hỗ trợ Python 3.14 tại
thời điểm viết tài liệu này. Nếu Python hệ thống là 3.14, **bắt buộc** tạo venv riêng
bằng Python 3.12 cho dbt — không ảnh hưởng gì tới Python hệ thống dùng cho
`load_staging.py`. Chi tiết đầy đủ + toàn bộ lỗi Windows đã gặp: [`dbt/README.md`](../dbt/README.md).

```powershell
# Tạo venv riêng cho dbt (chỉ 1 lần)
py -3.12 -m venv .venv-dbt

# PowerShell chặn script .ps1 mặc định — nới lỏng cho phiên hiện tại
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.venv-dbt\Scripts\Activate.ps1

# Cài thư viện (đã gồm dbt-postgres trong requirements.txt)
pip install -r requirements.txt
```

Kiểm tra kết nối:
```powershell
$env:PYTHONUTF8 = "1"   # tránh UnicodeDecodeError do comment tiếng Việt trong file dbt
dbt debug --project-dir dbt --profiles-dir dbt
```
Kỳ vọng: `All checks passed!`

## 11. Chạy `dbt build` — transform + nạp star schema + chạy test

```powershell
.venv-dbt\Scripts\Activate.ps1   # nếu chưa activate
$env:PYTHONUTF8 = "1"

dbt build --project-dir dbt --profiles-dir dbt
```

`dbt build` chạy theo đúng thứ tự phụ thuộc: **seed** (`dim_vendor`, `dim_payment_type`,
`dim_rate_code`) → **staging** (`stg_yellow_trips`) → **intermediate**
(`int_yellow_trips_keyed`) → **marts** (`dim_date`, `dim_time`, `fact_trips` — incremental,
áp 5 điều kiện lọc dữ liệu bẩn) → **test** (not_null, unique, relationships, và 5 test
tái hiện đúng 5 điều kiện lọc — xem `docs/notes.md` mục 1).

Kết quả cuối cùng kỳ vọng:
```
Done. PASS=38 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=38
```
Đối chiếu nhanh số liệu (khớp đúng bản gốc — xem `docs/data_dictionary.md`):
```sql
SELECT 'dim_date', COUNT(*) FROM dwh.dim_date        -- kỳ vọng 506
UNION ALL SELECT 'dim_time', COUNT(*) FROM dwh.dim_time      -- kỳ vọng 1440
UNION ALL SELECT 'fact_trips', COUNT(*) FROM dwh.fact_trips; -- kỳ vọng 21,792,952
```

(Tuỳ chọn) Sinh lineage graph trực quan cho portfolio:
```powershell
dbt docs generate --project-dir dbt --profiles-dir dbt
dbt docs serve --project-dir dbt --profiles-dir dbt
```

## 12. (Tùy chọn) Theo dõi tiến độ từ cửa sổ terminal khác
An toàn để chạy song song vì đây là câu lệnh chỉ đọc (`SELECT`):
```powershell
docker exec -i taxi_postgres psql -U taxi_user -d taxi_dwh -c "SELECT pid, state, now() - query_start AS running_time, LEFT(query, 60) AS query_preview FROM pg_stat_activity WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%';"
```

## 13. Setup Metabase
Truy cập `http://localhost:3000` → làm theo wizard tạo tài khoản admin đầu tiên (email/password tùy bạn, chỉ dùng local).

![alt text](images/image01.png)

Sau khi tạo tài khoản thành công:

![alt text](images/image02.png)

Thêm dữ liệu → chọn PostgreSQL:

![alt text](images/image03.png)

Cấu hình kết nối:
- Database type: `PostgreSQL`
- Host: `postgres` *(dùng tên service trong docker-compose, không phải `localhost`, vì Metabase gọi qua network nội bộ Docker)*
- Port: `5432`
- Database name: `taxi_dwh`
- Username: `taxi_user` / Password: `taxi_pass`

![alt text](images/image04.png)

Kết nối thành công — trạng thái "Đã kết nối" (chấm xanh) xác nhận Metabase đã thấy được `taxi_dwh`:

![alt text](images/image05.png)

## 14. Tạo Question SQL và Dashboard

- Quay về trang chủ (`http://localhost:3000`) → chọn **"Mới"** góc phải → chọn **"Truy vấn SQL"** → chọn database **Taxi DWH** → chạy lệnh SQL (nội dung lấy từ `sql/analytics/`):

![alt text](images/image06.png)

- Bấm nút **"Trực quan hóa"** (góc dưới trái, cạnh biểu tượng bánh răng) → chọn loại biểu đồ Cột/Đường → vào **Cài đặt** chỉnh trục X, và **chỉ giữ 1 metric chính mỗi chart** (tránh nhiều trục Y gây rối — xem `troubleshooting.md`):

![alt text](images/image07.png)

- Bấm **Lưu**, đặt tên câu hỏi (ví dụ: "Doanh thu theo giờ trong ngày"), chọn bộ sưu tập — lặp lại cho cả 5 câu hỏi trong `sql/analytics/`.

- Tạo Dashboard: quay về trang chủ → **"Mới"** → **"Bảng điều khiển"** → đặt tên → thêm lần lượt cả 5 câu hỏi đã lưu vào dashboard → **Lưu**.

![alt text](images/dashboard.png)