# Roadmap — Hướng phát triển tiếp theo

Bốn hướng mở rộng dưới đây được chọn có chủ đích (không thêm công nghệ nào khác ngoài 4 cái này): **dbt, Spark, Airflow, REST API**. Toàn bộ kiến trúc mở rộng được mô tả thống nhất qua **bảng 10 luồng** dưới đây — mọi phần giải thích sau đó đều tham chiếu ngược lại đúng số luồng trong bảng này để dễ đối chiếu với sơ đồ.

## Bảng luồng chi tiết

| STT | Tên luồng | Loại nét | Từ → Đến | Output / Nhãn | Ý nghĩa |
|---|---|---|---|---|---|
| 1 | Extract raw data | Nét liền | Raw CSV → Spark | — | Spark đọc trực tiếp file CSV gốc (7.4GB, 4 file) |
| 2 | Clean & convert | Nét liền | Spark → staging (Postgres) | **"Parquet sạch"** | Spark làm sạch dữ liệu bằng DataFrame API, ghi kết quả vào staging |
| 3 | Transform | Nét liền | staging (Postgres) → dbt | — | dbt đọc dữ liệu thô từ staging để bắt đầu transform |
| 4 | Build warehouse | Nét liền | dbt → Data Warehouse | **"star schema"** | dbt chạy models, sinh ra các bảng dim/fact theo star schema |
| 5 | Serve to API | Nét liền | Data Warehouse → RestAPI | — | RestAPI đọc dữ liệu đã transform để trả JSON |
| 6 | Serve to BI | Nét liền | Data Warehouse → Metabase | — | Metabase đọc dữ liệu để vẽ dashboard |
| 7 | Trigger Spark job | Nét đứt | Airflow → Spark | — | Airflow gọi chạy task Spark theo lịch (`@monthly`) |
| 8 | Trigger load staging | Nét đứt | Airflow → staging (Postgres) | — | Airflow gọi task nạp dữ liệu vào staging |
| 9 | Trigger dbt run | Nét đứt | Airflow → dbt | — | Airflow gọi `dbt run` / `dbt test` |
| 10 | Trigger pipeline | Nét đứt | RestAPI → Airflow | **`POST /api/pipeline/trigger`** | RestAPI gọi Airflow REST API để kích hoạt chạy DAG thủ công |

**Cách đọc bảng:** 6 luồng nét liền (1-6) là **luồng dữ liệu chính** — dữ liệu thực sự di chuyển qua các bước này. 4 luồng nét đứt (7-10) là **luồng điều phối/điều khiển** — không mang dữ liệu, chỉ mang tín hiệu "hãy chạy việc X".

---

## Thứ tự triển khai: dbt → Spark → Airflow → REST API

Triển khai theo thứ tự này vì có phụ thuộc lẫn nhau — công nghệ sau cần công nghệ trước chạy ổn định.

### 1. dbt — dựng luồng (3) và (4)

**Vì sao làm trước tiên:** đây là tầng transform trung tâm — luồng (9) của Airflow và luồng (5)/(6) phục vụ RestAPI/Metabase đều phụ thuộc vào dbt chạy đúng trước.

**Việc cụ thể (ứng với luồng 3 → 4):**
- Khởi tạo project dbt, kết nối tới `taxi_dwh`.
- Model layer: `staging` (đọc từ `staging.yellow_trips`, ứng luồng 3) → `intermediate` (tính surrogate key) → `marts` (`dim_date`, `dim_time`, `dim_vendor`, `dim_payment_type`, `dim_rate_code`, `fact_trips` — ứng luồng 4, output là "star schema").
- Chuyển 5 điều kiện lọc dữ liệu hiện tại thành **dbt tests** (`not_null`, `accepted_range`, custom test cho `dropoff > pickup`) khai báo trong `schema.yml`.
- Đổi `fact_trips` sang **incremental model** thay vì `TRUNCATE + full reload`.
- `dbt docs generate` — tự động có lineage graph cho portfolio.

**Kết quả:** thư mục `dbt/` thay thế vai trò `sql/02_transform_load.sql`.

### 2. Spark — dựng luồng (1) và (2)

**Vì sao cần mở rộng dữ liệu trước khi dùng Spark:** với 2 file hiện tại (3.5GB), `psycopg2.COPY` đã đủ nhanh — cần tăng khối lượng lên mới thấy rõ lợi ích xử lý phân tán.

**Việc cụ thể (ứng với luồng 1 → 2):**
- Dùng cả 4 file gốc (~7.4GB), có thể tải thêm để lên tới chục GB.
- Thêm service `spark` (image `bitnami/spark`) vào `docker-compose.yml`, chạy local mode.
- Script PySpark: đọc CSV (luồng 1) → lọc dữ liệu bẩn bằng DataFrame API → ghi ra **Parquet sạch** (luồng 2, nhãn output như trong bảng) → nạp Parquet vào `staging.yellow_trips`.

**Kết quả:** `spark_jobs/clean_taxi_data.py`, output Parquet trong `processed_data/`.

### 3. Airflow — dựng luồng (7), (8), (9)

**Vì sao làm sau dbt và Spark:** Airflow chỉ "gói" và lên lịch cho các bước đã chạy ổn định độc lập trước đó.

**Việc cụ thể (ứng với luồng 7 → 8 → 9, chạy tuần tự trong 1 DAG):**
- Thêm service `airflow` vào hạ tầng.
- 1 DAG, task nối tiếp:
  1. `run_spark_job` — ứng **luồng 7** (Airflow → Spark)
  2. `load_staging` — ứng **luồng 8** (Airflow → staging), có thể bỏ qua nếu Spark đã ghi thẳng vào staging ở bước 2
  3. `dbt_run` + `dbt_test` — ứng **luồng 9** (Airflow → dbt)
  4. `notify` — log/thông báo kết quả
- `schedule_interval='@monthly'`, retry khi lỗi tạm thời.

**Kết quả:** `airflow/dags/taxi_pipeline_dag.py`, demo được trên Airflow UI (`localhost:8080`).

### 4. REST API — dựng luồng (5), (6 đã có sẵn), (10)

**Vì sao làm cuối cùng:** API chỉ đọc dữ liệu từ warehouse đã ổn định, và cần Airflow đã chạy được (luồng 7-9) mới có gì để gọi trigger (luồng 10).

**Việc cụ thể (ứng với luồng 5 và 10):**
- Project FastAPI, kết nối `taxi_dwh` — ứng **luồng 5** (Data Warehouse → RestAPI): expose 5 endpoint JSON tương ứng `sql/analytics/` (`/api/trips/by-hour`, `/api/vendors/tip-stats`...).
- Thêm phân trang cho truy vấn trực tiếp `fact_trips` (`GET /api/trips?limit=50&offset=0`).
- Endpoint `POST /api/pipeline/trigger` — ứng **luồng 10** (RestAPI → Airflow): gọi Airflow REST API (`/api/v1/dags/{dag_id}/dagRuns`) để kích hoạt DAG thủ công.
- Thêm service `api` vào `docker-compose.yml`, expose port `8000`.

**Kết quả:** thư mục `api/`, Swagger UI tự động tại `localhost:8000/docs`.

---

## Ghi chú phạm vi

Roadmap này **chỉ giới hạn trong 4 công nghệ và 10 luồng** ở trên — không mở rộng thêm dbt Cloud, Kubernetes, cloud data warehouse (Snowflake/BigQuery), hay streaming (Kafka). Mục tiêu là đi sâu và làm chắc 4 mảnh ghép này trước khi nghĩ đến hướng khác.
