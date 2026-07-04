# Roadmap — Hướng phát triển tiếp theo

Bốn hướng mở rộng dưới đây được chọn có chủ đích (không thêm công nghệ nào khác ngoài 4 cái này): **dbt, Spark, Airflow, REST API**. Toàn bộ kiến trúc mở rộng được mô tả thống nhất qua **bảng 10 luồng** dưới đây — mọi phần giải thích sau đó đều tham chiếu ngược lại đúng số luồng trong bảng này để dễ đối chiếu với sơ đồ.

## Trạng thái triển khai

| Công nghệ | Luồng | Trạng thái |
|---|---|---|
| **dbt** | 3, 4 | ✅ Hoàn tất |
| **Spark** | 1, 2 | ✅ Hoàn tất (2 file, ~3.5GB — xem ghi chú "Phạm vi đã triển khai" bên dưới) |
| **Airflow** | 7, 8, 9 | ⏳ Tiếp theo |
| **REST API** | 5, 10 | ⏳ |

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

### 1. dbt — dựng luồng (3) và (4) ✅ Hoàn tất

**Vì sao làm trước tiên:** đây là tầng transform trung tâm — luồng (9) của Airflow và luồng (5)/(6) phục vụ RestAPI/Metabase đều phụ thuộc vào dbt chạy đúng trước.

**Việc cụ thể (ứng với luồng 3 → 4):**
- Khởi tạo project dbt, kết nối tới `taxi_dwh`.
- Model layer: `staging` (đọc từ `staging.yellow_trips`, ứng luồng 3) → `intermediate` (tính surrogate key) → `marts` (`dim_date`, `dim_time`, `dim_vendor`, `dim_payment_type`, `dim_rate_code`, `fact_trips` — ứng luồng 4, output là "star schema").
- Chuyển 5 điều kiện lọc dữ liệu hiện tại thành **dbt tests** (`not_null`, `accepted_range`, custom test cho `dropoff > pickup`) khai báo trong `schema.yml`.
- Đổi `fact_trips` sang **incremental model** thay vì `TRUNCATE + full reload`.

**Kết quả:** thư mục `dbt/` thay thế vai trò `sql/02_transform_load.sql`. 38/38 test PASS, số liệu khớp 100% bản gốc (xem `docs/checklist.md`).

**Còn lại:** `dbt docs generate` (sinh lineage graph cho portfolio) — chưa làm, xem mục "Chưa làm" ở `docs/checklist.md`.

### 2. Spark — dựng luồng (1) và (2) ✅ Hoàn tất (phạm vi 2 file)

**Vai trò thực tế đã triển khai (khác một phần so với dự tính ban đầu):** Spark ở đây **chỉ làm vệ sinh kỹ thuật** (ép đúng kiểu dữ liệu, phát hiện dòng lỗi cấu trúc) — **không** áp dụng 5 điều kiện lọc nghiệp vụ như dự tính ban đầu trong roadmap. Lý do: `staging.yellow_trips` được thiết kế là bảng thô, không lọc gì (xem `docs/data_dictionary.md`) — lọc nghiệp vụ vẫn thuộc về dbt trên `fact_trips`, tránh trùng logic ở 2 nơi. Về bản chất, Spark ở bước này thay thế **cách đọc/ghi** của `load_staging.py` (đọc CSV lớn hiệu quả hơn), không thay đổi vai trò của `staging`.

**Việc cụ thể (ứng với luồng 1 → 2):**
- Thêm service `spark` vào `docker-compose.yml` — dùng Docker Official Image `spark:python3` (không dùng `bitnami/spark` như dự tính ban đầu — xem `docs/troubleshooting.md` mục 12), chạy `local[*]`.
- `spark_jobs/clean_taxi_data.py`: đọc CSV (`mode=FAILFAST` để phát hiện dòng lỗi cấu trúc) → ép kiểu khớp `staging.yellow_trips` (`DecimalType` cho tiền/tọa độ, `TimestampType` cho thời gian) → audit NULL sinh ra do cast lỗi (dừng job nếu phát hiện) → ghi Parquet (`processed_data/yellow_trips_clean/`, 8 file).
- `load_parquet_to_staging.py` (file mới, độc lập với Spark, chạy trên host bằng Python thường): đọc từng file Parquet → nạp vào `staging.yellow_trips` bằng `psycopg2.COPY` — dùng lại đúng kỹ thuật COPY của `load_staging.py`.
- Đối chiếu checksum khớp 100% với staging nạp trực tiếp từ CSV: count 22,288,907; `SUM(total_amount)` 348,188,436.08; `SUM(trip_distance)` 108,299,074.48; `SUM(fare_amount)` 277,491,448.58.

**Phạm vi đã triển khai — khác dự tính ban đầu:** roadmap gốc dự định Spark xử lý **cả 4 file** (~7.4GB) để thấy rõ lợi ích xử lý phân tán. Bản đã triển khai **vẫn dùng 2 file** (2016-01, 2016-02 — ~3.5GB, giống các giai đoạn trước) để kiểm chứng luồng kỹ thuật trước khi scale. Mở rộng lên 4 file là việc còn lại — xem `docs/checklist.md` mục "Chưa làm".

**`load_staging.py` (COPY thẳng từ CSV):** vẫn được **giữ nguyên làm phương án dự phòng**, không bị xóa hay thay thế.

**Sự cố đã gặp trong quá trình làm (xem chi tiết `docs/troubleshooting.md`):**
- Mục 12 — `bitnami/spark:3.5` không còn tag miễn phí, đổi sang `spark:python3`.
- Mục 13 — Spark job bị `OutOfMemoryError` do `.cache()` 2 bản dữ liệu đầy đủ + 28 lượt quét riêng lẻ; sửa bằng cách gộp thành 1 lượt `.agg()` duy nhất, bỏ `.cache()`, đồng thời phải tắt `spark.sql.ansi.enabled` (Spark 4.x mặc định bật, khác hành vi cast của Spark 3.x).

### 3. Airflow — dựng luồng (7), (8), (9)

**Vì sao làm sau dbt và Spark:** Airflow chỉ "gói" và lên lịch cho các bước đã chạy ổn định độc lập trước đó.

**Việc cụ thể (ứng với luồng 7 → 8 → 9, chạy tuần tự trong 1 DAG):**
- Thêm service `airflow` vào hạ tầng.
- 1 DAG, task nối tiếp:
  1. `run_spark_job` — ứng **luồng 7** (Airflow → Spark)
  2. `load_staging` — ứng **luồng 8** (Airflow → staging), gọi `load_parquet_to_staging.py`
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
