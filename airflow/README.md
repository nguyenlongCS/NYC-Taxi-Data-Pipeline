# Airflow — Điều phối pipeline

Đóng gói `run_spark_job -> load_staging -> dbt_build` thành 1 DAG chạy theo lịch
(xem `docs/roadmap.md`, luồng 7-8-9). Toàn bộ kiến trúc được thiết kế lại từ
đầu để tránh 8 lỗi đã gặp ở lần thử nghiệm trước — xem bảng đối chiếu ở cuối
file này.

## Kiến trúc tóm tắt

```
airflow-scheduler ──┐
airflow-webserver ──┴── image "taxi-airflow" (CHỈ Airflow + docker provider,
        │                không cài dbt/pandas -- xem Dockerfile)
        │
        │ DockerOperator (qua /var/run/docker.sock) -- mỗi task 1 container
        │ riêng, tự chứa toàn bộ dependency của nó:
        │
        ├─ run_spark_job  → image spark:python3       (đã có sẵn, không đổi)
        ├─ load_staging   → image taxi-loader:latest   (mới -- docker/taxi-loader/)
        └─ dbt_build      → image taxi-dbt:latest      (mới -- docker/taxi-dbt/)
```

Airflow metadata (DAG run, log, connection...) lưu trong database **`airflow_db`**,
tạo mới trong CHÍNH container `taxi_postgres` đang có sẵn — không thêm container
Postgres nào khác.

## Chuẩn bị (chỉ làm 1 lần)

### 1. Tạo file `.env`

`docker-compose.yml` (ở thư mục gốc project) **chỉ tham chiếu biến môi
trường** — không có giá trị hay giá trị mặc định nào nằm trong đó. Toàn bộ
giá trị thật (bao gồm cả phần Postgres/dbt đã có từ trước lẫn phần Airflow
mới) nằm trong **1 file `.env` duy nhất** ở thư mục gốc, dựa theo
[`.env.example`](../.env.example) (cũng ở gốc project):

```bash
cp .env.example .env
```

Sau đó mở `.env` sửa ít nhất 2 chỗ:

1. **`AIRFLOW_FERNET_KEY`** — sinh 1 key thật:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Dán giá trị sinh ra vào `.env` (giá trị mẫu trong `.env.example` chỉ đúng
   định dạng, không được dùng thật).
2. **`HOST_PROJECT_DIR`** — đường dẫn tuyệt đối của project trên máy bạn,
   dùng dấu `/` kể cả trên Windows (ví dụ `D:/Project/NYC-Taxi-Data-Pipeline`).

Có thể đổi thêm `AIRFLOW_ADMIN_PASSWORD` và các cổng (`*_HOST_PORT`) nếu muốn.

### 2. Build các image

```bash
docker compose build airflow-init taxi-loader taxi-dbt
```

(3 image dùng chung Dockerfile/tag: `taxi-airflow`, `taxi-loader`, `taxi-dbt` —
`airflow-scheduler`/`airflow-webserver` dùng lại tag `taxi-airflow:latest` đã
build bởi `airflow-init`, không cần build riêng.)

### 3. Khởi tạo (tạo `airflow_db`, migrate, tạo user admin)

```bash
docker compose up airflow-init
```

Đọc log tới dòng `airflow-init hoàn tất.` — nếu có lỗi, container sẽ dừng với
exit code khác 0 (không âm thầm trôi qua bước tiếp theo).

### 4. Khởi động scheduler + webserver

```bash
docker compose up -d airflow-scheduler airflow-webserver
```

Kiểm tra ngay (đừng bỏ qua bước này — đây là bước từng bị thiếu, gây lỗi
"DagBag rỗng" không xác nhận được ở lần thử trước):

```bash
docker compose exec airflow-scheduler airflow dags list-import-errors
```

Kết quả rỗng (không có dòng lỗi nào) mới coi là DAG load thành công. Nếu có lỗi
import, sửa xong rồi chạy lại đúng lệnh trên để xác nhận trước khi bật DAG.

### 5. Truy cập UI

`http://localhost:8080` — đăng nhập bằng `AIRFLOW_ADMIN_USER` /
`AIRFLOW_ADMIN_PASSWORD` đã set trong `.env`. Bật (unpause) DAG `taxi_pipeline`
rồi trigger thủ công lần đầu để kiểm tra full pipeline.

## Đối chiếu lỗi đã gặp trước đó → cách xử lý trong bản thiết kế này

| # | Lỗi cũ | Cách xử lý trong bản này |
|---|---|---|
| 1 | Xung đột dependency Airflow + dbt | 3 image tách biệt hoàn toàn: `taxi-airflow` (chỉ docker provider), `taxi-loader`, `taxi-dbt` — không image nào cài cả `apache-airflow` lẫn `dbt-core` |
| 2 | Compose interpolate sai biến `${...}` | Mọi giá trị nhạy cảm đi qua `environment:` (interpolation hợp lệ, có chủ đích), KHÔNG có `${...}` nào nhúng trong chuỗi `command:`/`entrypoint:` inline — nên không cần escape `$$` ở đâu cả |
| 3 | Race condition `airflow-init` | `postgres` có `healthcheck` (`pg_isready`) + `airflow-init` dùng `depends_on: condition: service_healthy`; `airflow-scheduler`/`airflow-webserver` dùng `depends_on: condition: service_completed_successfully` trên `airflow-init` |
| 4 | Lỗi collation khi tạo DB | `create_airflow_db.py` dùng `TEMPLATE template0` + ép `LC_COLLATE`/`LC_CTYPE = 'C'`, không dựa vào `template1` |
| 5 | `\N` bị hiểu escape Unicode | DAG không chứa đường dẫn Windows nào; `HOST_PROJECT_DIR` chỉ nằm trong `.env`, đọc qua `os.environ` lúc chạy |
| 6 | Spark ghi Parquet lỗi qua bind-mount Windows | Thêm `spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version=2` trong `clean_taxi_data.py` |
| 7 | Airflow OOM do gộp scheduler+webserver | Tách hẳn 2 service `airflow-scheduler` / `airflow-webserver`, mỗi service `mem_limit: 1g` riêng |
| 8 | DagBag rỗng (nghi do thiếu biến host dir) | `HOST_PROJECT_DIR` bắt buộc (`${HOST_PROJECT_DIR:?...}` — báo lỗi rõ nếu thiếu, không chạy tiếp với giá trị rỗng); bước 4 ở trên bắt buộc chạy `airflow dags list-import-errors` để xác nhận trước khi coi là xong |

## Lưu ý khi chạy trên Linux (không phải Docker Desktop)

Nếu gặp lỗi quyền truy cập `/var/run/docker.sock` (Permission denied) trong
`airflow-scheduler`, thường do socket thuộc group `docker` mà user trong
container không nằm trong group đó. Cách xử lý nhanh (chỉ cho môi trường
dev/demo, không khuyến khích production): thêm vào service `airflow-scheduler`
trong `docker-compose.yml`:

```yaml
user: "0:0"
```

## Việc còn lại (chưa làm ở bước này)

- Chưa cập nhật `docs/checklist.md`, `docs/roadmap.md`, `README.md` gốc để
  đánh dấu Airflow "Hoàn tất" — nên làm sau khi chạy thử thành công `docker
  compose up airflow-init` và trigger DAG ít nhất 1 lần trót lọt.
- Chưa thêm bước dọn container con nếu task fail giữa chừng (`auto_remove`
  đã set `"success"` — container CHỈ tự xoá khi thành công, cố ý giữ lại
  container lỗi để debug log qua `docker logs`).
