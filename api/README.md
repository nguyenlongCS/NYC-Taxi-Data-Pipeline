# api/ — REST API cho NYC Taxi Data Pipeline

FastAPI expose dữ liệu từ `dwh.*` (database `taxi_dwh`) qua REST, và cho phép
trigger thủ công pipeline Airflow qua HTTP — ứng luồng 5, 6, 10 trong
[`docs/roadmap.md`](../docs/roadmap.md).

Swagger UI tự động: `http://localhost:8000/docs` (sau khi container chạy).

## Endpoint

| Method | Path | Mô tả | Ứng file gốc |
|---|---|---|---|
| GET | `/api/health` | Kiểm tra API + kết nối Postgres | — |
| GET | `/api/analytics/revenue-by-hour` | Doanh thu theo giờ trong ngày | `sql/analytics/03_revenue_by_hour.sql` |
| GET | `/api/analytics/trend-by-weekday` | Xu hướng theo ngày trong tuần | `sql/analytics/04_trend_by_weekday.sql` |
| GET | `/api/analytics/payment-distribution` | Phân bố hình thức thanh toán | `sql/analytics/05_payment_type_distribution.sql` |
| GET | `/api/analytics/tip-by-vendor` | Tip trung bình theo vendor | `sql/analytics/06_tip_by_vendor.sql` |
| GET | `/api/analytics/rush-hour-impact` | Ảnh hưởng giờ cao điểm | `sql/analytics/07_rush_hour_impact.sql` |
| GET | `/api/trips` | Đọc `dwh.fact_trips`, phân trang `limit`/`offset`, lọc `vendor_id`/`payment_type_id`/`pickup_date_from`/`pickup_date_to` | — (mới) |
| POST | `/api/pipeline/trigger` | Trigger thủ công DAG `taxi_pipeline` qua Airflow REST API | — (mới, luồng 10) |
| GET | `/api/pipeline/status/{dag_run_id}` | Xem trạng thái 1 lần chạy DAG | — (mới) |

5 endpoint `analytics/*` giữ nguyên 1-1 nội dung SQL với `sql/analytics/` —
đảm bảo API và dashboard Metabase luôn trả cùng một kết quả.

## Cấu trúc

```
api/
├── Dockerfile
├── requirements.txt
├── main.py           # khởi tạo FastAPI app, gắn router, /api/health
├── database.py        # SQLAlchemy engine + session (đọc config từ env)
├── schemas.py          # Pydantic response models, khớp tên cột thật của từng câu SQL
└── routers/
    ├── analytics.py    # 5 endpoint /api/analytics/*
    ├── trips.py         # /api/trips (phân trang LIMIT/OFFSET)
    └── pipeline.py       # /api/pipeline/trigger, /api/pipeline/status/{id}
```

## Biến môi trường (truyền qua `docker-compose.yml`, giá trị thật ở `.env`)

| Biến | Ý nghĩa |
|---|---|
| `POSTGRES_HOST` | Mặc định `postgres` (tên service trong `taxi_net`) |
| `POSTGRES_PORT` | Mặc định `5432` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Dùng chung với các service khác, lấy từ `.env` |
| `AIRFLOW_BASE_URL` | URL nội bộ Docker gọi Airflow REST API, mặc định `http://airflow-webserver:8080` |
| `AIRFLOW_EXTERNAL_URL` | URL Airflow UI mở từ trình duyệt trên host, mặc định `http://localhost:8080` |
| `AIRFLOW_DAG_ID` | Mặc định `taxi_pipeline` |
| `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` | Dùng lại thẳng tài khoản admin Airflow đã có trong `.env` |

## ⚠️ Yêu cầu hạ tầng để `/api/pipeline/trigger` hoạt động

Airflow webserver mặc định chỉ bật auth backend `session` (dựa cookie đăng
nhập UI), **không** chấp nhận Basic Auth gọi từ ngoài vào REST API. Cần
thêm biến sau vào service `airflow-webserver` trong `docker-compose.yml`
(đã thêm sẵn trong bản cập nhật đi kèm PR này):

```yaml
AIRFLOW__API__AUTH_BACKENDS: airflow.api.auth.backend.basic_auth
```

Thiếu biến này, gọi `/api/pipeline/trigger` sẽ nhận `403 Forbidden` từ
Airflow dù user/password đúng.

## Chạy thử cục bộ (không qua Docker, để dev nhanh)

```powershell
cd api
pip install -r requirements.txt
$env:POSTGRES_HOST = "localhost"        # map cổng Postgres ra host trước
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "taxi_dwh"
$env:POSTGRES_USER = "taxi_user"
$env:POSTGRES_PASSWORD = "taxi_pass"
uvicorn main:app --reload --port 8000
```

## Chạy qua Docker Compose (khuyến nghị)

Service `api` gắn Compose profile `tools` (giống pgAdmin/Metabase) — không
tự khởi động cùng Airflow để tránh chiếm RAM (xem `docs/troubleshooting.md`
mục 19). Bật khi cần:

```powershell
docker compose --profile tools up -d --build api
```

Mở `http://localhost:8000/docs`.

## Hướng cải tiến thêm (chưa làm ở bản này)

- Tách 5 câu SQL trong `routers/analytics.py` ra file `.sql` dùng chung
  thật sự với `sql/analytics/` (hiện đang copy nội dung, phải sửa 2 nơi
  nếu đổi logic) — cần cách nạp SQL từ file khi build Docker image.
- Keyset pagination cho `/api/trips` (theo `trip_id`) nếu cần phân trang
  nhanh ở các trang sâu — hiện dùng `LIMIT/OFFSET` đơn giản theo quyết định
  ban đầu, đủ cho mục đích demo/portfolio.
- Test tự động (pytest + `TestClient`) — chưa viết ở giai đoạn này, ưu tiên
  chạy được + Swagger UI trước.
- Rate limiting / API key nếu expose ra ngoài Internet thay vì chỉ chạy local.
