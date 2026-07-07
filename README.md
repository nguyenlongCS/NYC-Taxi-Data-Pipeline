# NYC Taxi Data Pipeline

Dự án cá nhân xây dựng pipeline dữ liệu **end-to-end** (Extract → Load → Transform → Serve) cho dữ liệu NYC Yellow Taxi, từ file CSV thô đến dashboard phân tích — chạy hoàn toàn **local, miễn phí** bằng Docker.

## Kết quả

- **~22.3 triệu dòng** dữ liệu chuyến taxi (2 tháng, 2016-01 & 2016-02) nạp vào Data Warehouse dạng **star schema**
- **21.8 triệu dòng** sau khi làm sạch (lọc ~2.2% dữ liệu bẩn: GPS lỗi, giá âm, quãng đường bất thường...)
- **5 dashboard phân tích** trực quan trên Metabase: doanh thu theo giờ, xu hướng theo ngày trong tuần, phân bố hình thức thanh toán, tip theo vendor, ảnh hưởng giờ cao điểm
- **2 đường nạp dữ liệu song song vào staging**: `psycopg2.COPY` trực tiếp từ CSV (nhanh, đơn giản) và **Spark** (đọc CSV → ép kiểu + kiểm tra dữ liệu → Parquet → COPY) — đối chiếu checksum khớp 100% giữa 2 đường
- **Điều phối tự động bằng Airflow**: 1 DAG (`run_spark_job -> load_staging -> dbt_build`) chạy theo lịch `@monthly` hoặc trigger thủ công, mỗi task chạy trong 1 container Docker riêng biệt (docker-outside-of-docker)

## Kiến trúc

![alt text](img_demo/system_architecture.png)

Toàn bộ hạ tầng đóng gói bằng **Docker Compose**: PostgreSQL (data warehouse) + pgAdmin (quản trị DB) + Metabase (BI dashboard) + Spark (xử lý dữ liệu lớn), 3 service DB/BI có volume riêng để dữ liệu/dashboard không mất khi restart.

## Tech stack

| Thành phần | Công nghệ |
|---|---|
| Nguồn dữ liệu | NYC Yellow Taxi Trip Data (Kaggle, gốc từ TLC), 2015-2016 |
| Data Warehouse | PostgreSQL 16 |
| Xử lý dữ liệu lớn | **Apache Spark 4.1.2** (Docker Official Image `spark:python3`, local mode) |
| ETL | Python (`psycopg2` — COPY streaming) + **dbt** (staging → intermediate → marts) |
| Điều phối | **Apache Airflow 2.10.5** (LocalExecutor, DockerOperator — docker-outside-of-docker) |
| BI / Dashboard | Metabase |
| Quản trị DB | pgAdmin |
| Hạ tầng | Docker Compose |

## Bắt đầu nhanh

```bash
# 1. Clone repo, tải dataset (xem docs/dataset.md), giải nén vào raw_data/
# 2. Khởi động hạ tầng
docker compose up -d

# 3. Cài thư viện Python
pip install -r requirements.txt

# 4a. Nạp dữ liệu thô vào staging -- CÁCH 1: trực tiếp CSV (đơn giản, đủ dùng cho 2 file)
python load_staging.py

# 4b. Nạp dữ liệu thô vào staging -- CÁCH 2: qua Spark (khuyến nghị cho dữ liệu lớn hơn)
docker compose run --rm spark /opt/spark/bin/spark-submit /opt/spark_data/spark_jobs/clean_taxi_data.py
python load_parquet_to_staging.py

# 5. Transform + nạp star schema bằng dbt (cần Python 3.12 — xem dbt/README.md
#    nếu Python hệ thống là 3.14, dbt chưa hỗ trợ)
py -3.12 -m venv .venv-dbt
.venv-dbt\Scripts\Activate.ps1        # (Linux/macOS: source .venv-dbt/bin/activate)
pip install -r requirements.txt
dbt build --project-dir dbt --profiles-dir dbt

# 6. Mở Metabase, kết nối tới taxi_dwh, import các câu truy vấn trong sql/analytics/
#    (docker compose --profile tools up -d để bật pgAdmin/Metabase, xem mục "Điều phối")

# 7. (Thay thế bước 4-5 chạy tay) Điều phối tự động bằng Airflow -- xem airflow/README.md
cp .env.example .env   # điền AIRFLOW_FERNET_KEY + HOST_PROJECT_DIR trước khi chạy
docker compose build airflow-init taxi-loader taxi-dbt
docker compose up airflow-init
docker compose up -d airflow-scheduler airflow-webserver
# Mở http://localhost:8080, trigger DAG "taxi_pipeline"
```
→ Hướng dẫn chi tiết từng bước kèm ảnh chụp màn hình: [`docs/setup.md`](docs/setup.md)
→ Hướng dẫn riêng cho dbt (setup venv, lệnh chạy, lỗi thường gặp trên Windows): [`dbt/README.md`](dbt/README.md)
→ Hướng dẫn riêng cho Airflow (kiến trúc, setup, bảng đối chiếu lỗi đã gặp): [`airflow/README.md`](airflow/README.md)

## Cấu trúc project

```
NYC-Taxi-Data-Pipeline/
├── docs/                  # Toàn bộ tài liệu (xem bảng bên dưới)
├── raw_data/              # Dữ liệu gốc (không đưa lên GitHub)
├── processed_data/        # Output Parquet của Spark (không đưa lên GitHub)
├── spark_jobs/            # clean_taxi_data.py -- đọc CSV, ép kiểu, ghi Parquet
├── sql/
│   ├── 01_create_schema.sql   # Chỉ còn tạo schema + staging.yellow_trips
│   ├── archive/                # 02_transform_load.sql cũ — đã thay bằng dbt/
│   └── analytics/         # 5 câu truy vấn dựng dashboard
├── dbt/                   # staging → intermediate → marts (thay 02_transform_load.sql)
├── airflow/               # Điều phối pipeline: DAG + Dockerfile + scripts khởi tạo
├── docker/                # Build context cho image taxi-loader/taxi-dbt (Airflow gọi qua DockerOperator)
├── docker-compose.yml     # Postgres + pgAdmin + Metabase + Spark + Airflow
├── .env / .env.example    # Biến môi trường dùng chung cho Postgres/dbt/Airflow
├── load_staging.py            # Nạp CSV -> staging trực tiếp (COPY)
├── load_parquet_to_staging.py # Nạp Parquet (output Spark) -> staging (COPY, streaming batch)
└── requirements.txt
```
→ Chi tiết đầy đủ: [`docs/project_structure.md`](docs/project_structure.md)

## Tài liệu

| File | Nội dung |
|---|---|
| [`docs/dataset.md`](docs/dataset.md) | Nguồn dữ liệu, cấu trúc cột gốc, quyết định phạm vi dữ liệu sử dụng |
| [`docs/pipeline.md`](docs/pipeline.md) | Chi tiết luồng ETL, lý do kỹ thuật từng giai đoạn, hướng mở rộng |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Mô tả đầy đủ từng bảng, từng cột trong Data Warehouse |
| [`docs/setup.md`](docs/setup.md) | Hướng dẫn cài đặt và chạy pipeline từng bước, kèm ảnh minh họa |
| [`docs/notes.md`](docs/notes.md) | Kiến thức và bài học kỹ thuật rút ra trong quá trình xây dựng |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Các lỗi thực tế đã gặp và cách xử lý (FK constraint, race condition, Docker volume, Spark OOM, Airflow network/OOM/page-cache thrashing...) |
| [`docs/roadmap.md`](docs/roadmap.md) | Kế hoạch mở rộng (dbt, Spark, Airflow, REST API), trạng thái từng phần |
| [`airflow/README.md`](airflow/README.md) | Kiến trúc điều phối Airflow (docker-outside-of-docker), setup, bảng đối chiếu lỗi đã gặp |

## Điểm nhấn kỹ thuật

- **Xử lý file CSV lớn (3.5GB) hiệu quả**: 2 cách tiếp cận song song — `COPY` streaming qua `psycopg2` (không load vào RAM), và Spark (đọc theo schema tường minh, ép kiểu, tự phát hiện dòng lỗi bằng `FAILFAST`).
- **Data quality có kiểm soát**: 5 điều kiện lọc dữ liệu bẩn rõ ràng ở tầng dbt (có số liệu đối chiếu trước/sau, xem `docs/data_dictionary.md`), cộng thêm audit "cast lỗi → NULL" ở tầng Spark để đảm bảo không mất dữ liệu khi ép kiểu.
- **Star schema chuẩn** với kỹ thuật *role-playing dimension* (`dim_date`/`dim_time` được dùng lại cho cả pickup và dropoff).
- **Hạ tầng persist đúng cách**: named volume cho các service DB/BI, tránh mất dữ liệu/dashboard khi container restart.
- **Transform bằng dbt**: `staging → intermediate → marts`, `fact_trips` là **incremental model**, 38 test (not_null, unique, relationships, và 5 custom test tái hiện đúng 5 điều kiện lọc dữ liệu bẩn) — xem [`dbt/README.md`](dbt/README.md).
- **Xử lý dữ liệu lớn bằng Spark**: đọc CSV theo schema tường minh (`DecimalType` để tránh sai số làm tròn, `FAILFAST` để phát hiện dòng lỗi cấu trúc), kiểm tra dữ liệu bị hỏng khi ép kiểu trong 1 lượt `.agg()` duy nhất (tối ưu để tránh OOM trên máy có RAM giới hạn — xem `docs/troubleshooting.md` mục 13), checksum khớp 100% với đường nạp CSV trực tiếp.
- **Điều phối bằng Airflow, kiến trúc docker-outside-of-docker**: 1 DAG duy nhất (`run_spark_job -> load_staging -> dbt_build`), mỗi task chạy trong 1 container Docker riêng biệt qua `DockerOperator` (image Airflow không cài chung dependency với dbt/pandas, tránh xung đột) — chạy được cả theo lịch `@monthly` lẫn trigger thủ công, đã kiểm chứng số liệu khớp 100% bản gốc.
- **Xử lý dữ liệu theo batch để tránh OOM**: `load_parquet_to_staging.py` đọc Parquet theo từng lô (`pyarrow.iter_batches`) thay vì nạp nguyên file vào RAM — RAM sử dụng không còn phụ thuộc dung lượng file, chạy ổn định trong container giới hạn tài nguyên (xem `docs/troubleshooting.md` mục 17-18).

## Hướng phát triển tiếp theo
 
Nâng pipeline hiện tại thành nền tảng dữ liệu tự động, theo thứ tự **dbt → Spark → Airflow → REST API**:
 
| Công nghệ | Vai trò | Trạng thái |
|---|---|---|
| **dbt** | Thay `02_transform_load.sql` bằng models + tests, sinh lineage graph tự động | ✅ Hoàn tất |
| **Spark** | Đọc CSV lớn, ép kiểu + kiểm tra dữ liệu, ghi Parquet sạch nạp vào staging | ✅ Hoàn tất (2 file, ~3.5GB — mở rộng lên 4 file/~7.4GB là bước tiếp theo) |
| **Airflow** | Đóng gói pipeline thành 1 DAG chạy theo lịch, tự retry khi lỗi | ✅ Hoàn tất |
| **REST API** | Expose dữ liệu warehouse qua FastAPI, có thể trigger Airflow chạy thủ công | ⏳ |
 
→ Sơ đồ luồng chi tiết (10 luồng, có đánh số) và kế hoạch triển khai từng bước: [`docs/roadmap.md`](docs/roadmap.md)
