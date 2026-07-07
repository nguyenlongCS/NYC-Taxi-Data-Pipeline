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
Xem nội dung đầy đủ trong repo — 4 service: `postgres`, `pgadmin`, `metabase`, `spark`, mỗi service DB/BI (`postgres`, `pgadmin`, `metabase`) có named volume riêng để persist dữ liệu qua các lần restart (`spark` không cần volume riêng — không giữ trạng thái giữa các lần chạy job).

`sql/01_create_schema.sql` (chạy tự động khi container Postgres khởi tạo lần đầu qua
`docker-entrypoint-initdb.d`) hiện chỉ tạo schema `staging`/`dwh` rỗng + bảng
`staging.yellow_trips` — toàn bộ bảng `dim_*`/`fact_trips` bên trong `dwh` **không còn
được tạo ở đây nữa**, mà do dbt tự tạo khi chạy `dbt build` (xem mục 11-12 bên dưới).

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

Container `taxi_spark` cũng sẽ được tạo ở bước này (image `spark:python3`), nhưng không
chạy nền liên tục — mặc định chỉ `sleep infinity`, chỉ thực thi job khi được gọi tường
minh bằng `docker compose run` (xem mục 10 bên dưới).

## 7. Đặt `load_staging.py` (và `load_parquet_to_staging.py`) vào thư mục gốc project
Ngang hàng với `raw_data/` và `docker-compose.yml`. Tạo thêm 2 thư mục rỗng nếu chưa có:
```powershell
mkdir spark_jobs
mkdir processed_data
```
Đặt `spark_jobs/clean_taxi_data.py` vào thư mục `spark_jobs/` vừa tạo.

## 8. Cài thư viện
```powershell
pip install -r requirements.txt
```
(đã bao gồm `psycopg2-binary` cho `load_staging.py`, và `pyarrow` cho `load_parquet_to_staging.py` đọc file Parquet)

## 9. Nạp dữ liệu vào staging — Cách 1: trực tiếp từ CSV (COPY)

Đơn giản, đủ dùng tốt với khối lượng 2 file hiện tại (~3.5GB).

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

⚠️ Chỉ cần thực hiện **1 trong 2 cách** (mục 9 hoặc mục 10) để nạp staging — không cần
chạy cả hai. Nếu đã chạy cách này rồi muốn thử cách kia, cứ chạy thẳng mục 10 (script
tự `TRUNCATE` staging trước khi nạp lại, an toàn để đổi qua đổi lại).

## 10. Nạp dữ liệu vào staging — Cách 2: qua Spark (khuyến nghị khi mở rộng dữ liệu lớn hơn)

Spark ở đây đóng vai trò thay thế **cách đọc/ghi** CSV lớn (ép kiểu dữ liệu tường minh,
tự phát hiện dòng lỗi cấu trúc) — output là Parquet sạch, sau đó vẫn nạp vào staging
bằng cùng kỹ thuật `COPY` như cách 1. Xem giải thích đầy đủ tại
[`docs/roadmap.md`](roadmap.md) mục "2. Spark".

**10.1. Chạy Spark job** (đọc CSV → ép kiểu → ghi Parquet vào `processed_data/`):
```powershell
docker compose run --rm spark /opt/spark/bin/spark-submit /opt/spark_data/spark_jobs/clean_taxi_data.py
```
Kỳ vọng output (rút gọn, bỏ log INFO/WARN của Spark):
```
Đang đọc 2 file CSV...
Đang ép kiểu dữ liệu + chuẩn bị audit NULL (chưa thực thi, lazy)...
Đang chạy 1 lượt quét duy nhất: kiểm tra NULL + tính checksum (có thể mất vài phút cho 22 triệu dòng)...
Không phát hiện dữ liệu bị hỏng khi ép kiểu.

=== Checksum ===
count               : 22,288,907
SUM(total_amount)   : 348188436.08
SUM(trip_distance)  : 108299074.48
SUM(fare_amount)    : 277491448.58
So sánh 4 số trên với baseline đã đo trên staging.yellow_trips hiện tại.

Đang ghi Parquet ra /opt/spark_data/processed_data/yellow_trips_clean ...
Hoàn tất.
```
So khớp 4 số checksum này với baseline đo được từ Cách 1 (mục 9) — nếu khớp, dữ liệu
được xử lý đúng, chưa mất/sai lệch gì trước khi nạp vào Postgres.

⚠️ **Lưu ý về phiên bản Spark:** image `spark:python3` chạy **Spark 4.1.2** (không phải
3.5.x như dự tính ban đầu khi còn định dùng `bitnami/spark` — image đó đã ngừng phát
hành tag miễn phí, xem [`docs/troubleshooting.md`](troubleshooting.md) mục 12). Spark
4.x đổi mặc định `spark.sql.ansi.enabled` sang `true`, ảnh hưởng trực tiếp tới cách
script phát hiện dòng lỗi khi ép kiểu — `clean_taxi_data.py` đã chủ động tắt cấu hình
này, không cần chỉnh gì thêm khi chạy theo hướng dẫn ở trên. Chi tiết đầy đủ (kèm sự cố
`OutOfMemoryError` đã gặp và cách sửa) xem `docs/troubleshooting.md` mục 12-13.

**10.2. Nạp Parquet vào staging** (đọc từng file Parquet → `COPY` vào Postgres):
```powershell
python load_parquet_to_staging.py
```
Kỳ vọng output:
```
Đang TRUNCATE staging.yellow_trips để nạp lại từ đầu...
Tìm thấy 8 file Parquet trong processed_data\yellow_trips_clean.
→ [1/8] Đang đọc part-00000-....snappy.parquet ...
  Xong 2,574,701 dòng trong 50.4 giây.
...
→ [8/8] Đang đọc part-00007-....snappy.parquet ...
  Xong 2,577,916 dòng trong 45.0 giây.
Tổng số dòng đã nạp (Python cộng dồn): 22,288,907
Tổng số dòng trong staging.yellow_trips (đếm trực tiếp DB): 22,288,907
```

**10.3. Đối chiếu lần cuối trên pgAdmin** (đảm bảo dữ liệu trong Postgres khớp checksum ở bước 10.1):
```sql
SELECT
  COUNT(*),
  SUM(total_amount),
  SUM(trip_distance),
  SUM(fare_amount)
FROM staging.yellow_trips;
```

## 11. Setup dbt (thay cho việc viết `02_transform_load.sql` thủ công)

⚠️ **Lưu ý quan trọng:** dbt-core (qua thư viện `mashumaro`) chưa hỗ trợ Python 3.14 tại
thời điểm viết tài liệu này. Nếu Python hệ thống là 3.14, **bắt buộc** tạo venv riêng
bằng Python 3.12 cho dbt — không ảnh hưởng gì tới Python hệ thống dùng cho
`load_staging.py`/`load_parquet_to_staging.py`. Chi tiết đầy đủ + toàn bộ lỗi Windows đã gặp: [`dbt/README.md`](../dbt/README.md).

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

## 12. Chạy `dbt build` — transform + nạp star schema + chạy test

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

## 13. (Tùy chọn) Theo dõi tiến độ từ cửa sổ terminal khác
An toàn để chạy song song vì đây là câu lệnh chỉ đọc (`SELECT`):
```powershell
docker exec -i taxi_postgres psql -U taxi_user -d taxi_dwh -c "SELECT pid, state, now() - query_start AS running_time, LEFT(query, 60) AS query_preview FROM pg_stat_activity WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%';"
```

## 14. Setup Metabase
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

## 15. Tạo Question SQL và Dashboard

- Quay về trang chủ (`http://localhost:3000`) → chọn **"Mới"** góc phải → chọn **"Truy vấn SQL"** → chọn database **Taxi DWH** → chạy lệnh SQL (nội dung lấy từ `sql/analytics/`):

![alt text](images/image06.png)

- Bấm nút **"Trực quan hóa"** (góc dưới trái, cạnh biểu tượng bánh răng) → chọn loại biểu đồ Cột/Đường → vào **Cài đặt** chỉnh trục X, và **chỉ giữ 1 metric chính mỗi chart** (tránh nhiều trục Y gây rối — xem `troubleshooting.md`):

![alt text](images/image07.png)

- Bấm **Lưu**, đặt tên câu hỏi (ví dụ: "Doanh thu theo giờ trong ngày"), chọn bộ sưu tập — lặp lại cho cả 5 câu hỏi trong `sql/analytics/`.

- Tạo Dashboard: quay về trang chủ → **"Mới"** → **"Bảng điều khiển"** → đặt tên → thêm lần lượt cả 5 câu hỏi đã lưu vào dashboard → **Lưu**.

![alt text](images/dashboard.png)
## 16. Setup Airflow (điều phối pipeline tự động)

Thay vì chạy tay tuần tự các bước 9/10 → 12 mỗi lần có dữ liệu mới, Airflow đóng gói toàn bộ thành 1 DAG (`run_spark_job -> load_staging -> dbt_build`), chạy theo lịch `@monthly` hoặc trigger thủ công qua UI.

Hướng dẫn đầy đủ (build image, khởi tạo, kiểm tra, bảng đối chiếu lỗi thường gặp) nằm ở [`airflow/README.md`](../airflow/README.md) — không lặp lại chi tiết ở đây, chỉ tóm tắt các bước chính:

```powershell
# 1. Tạo .env từ .env.example (nếu chưa có), điền AIRFLOW_FERNET_KEY + HOST_PROJECT_DIR
cp .env.example .env

# 2. Build image
docker compose build airflow-init taxi-loader taxi-dbt

# 3. Khởi tạo (tạo database airflow_db, migrate, tạo user admin)
docker compose up airflow-init

# 4. Khởi động scheduler + webserver
docker compose up -d airflow-scheduler airflow-webserver
```

Mở `http://localhost:8080`, đăng nhập bằng `AIRFLOW_ADMIN_USER`/`AIRFLOW_ADMIN_PASSWORD` trong `.env`, trigger DAG `taxi_pipeline` để chạy full pipeline tự động.

⚠️ **Lưu ý:** `pgadmin`/`metabase` gắn Compose profile `tools`, không tự khởi động cùng lệnh `docker compose up -d` mặc định nữa (tiết kiệm RAM khi chạy Airflow) — cần dùng khi nào thì chạy thêm:
```powershell
docker compose --profile tools up -d
```
