# dbt — NYC Taxi DWH

Thay thế `sql/02_transform_load.sql` bằng dbt models (staging → intermediate → marts).
Xem kế hoạch tổng thể tại [`docs/roadmap.md`](../docs/roadmap.md).

## ⚠️ Yêu cầu Python — dùng riêng venv, KHÔNG dùng Python hệ thống nếu là 3.14+

dbt-core (qua thư viện phụ thuộc `mashumaro`) **chưa hỗ trợ Python 3.14** tại thời điểm
viết tài liệu này (dbt chính thức hỗ trợ tới Python 3.13). Nếu máy bạn cài Python 3.14
làm mặc định, `dbt debug`/`dbt run` sẽ crash với lỗi:
```
mashumaro.exceptions.UnserializableField: Field "schema" of type Optional[str]
in JSONObjectSchema is not serializable
```

**Cách xử lý:** tạo venv riêng cho dbt bằng Python 3.12 (hoặc 3.11/3.13), tách biệt
hoàn toàn với Python hệ thống dùng cho `load_staging.py`.

## Setup (chạy 1 lần)

```powershell
# Từ thư mục gốc repo
py -3.12 -m venv .venv-dbt

# Windows PowerShell chặn script theo mặc định — nới lỏng cho phiên hiện tại:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.venv-dbt\Scripts\Activate.ps1

pip install -r requirements.txt
```

## ⚠️ Lỗi encoding trên Windows: `UnicodeDecodeError: 'charmap' codec can't decode byte...`

Python trên Windows mặc định đọc file bằng codepage hệ thống (`cp1252`) thay vì UTF-8.
Vì các file `.sql`/`.yml` trong project có comment tiếng Việt có dấu, dbt sẽ crash khi
quét project nếu thiếu biến môi trường này. **Set trước khi chạy bất kỳ lệnh `dbt` nào:**

```powershell
$env:PYTHONUTF8 = "1"
```

(Chỉ áp dụng cho phiên PowerShell hiện tại — phải set lại mỗi khi mở terminal mới,
cùng lúc với `Activate.ps1`.)

## Chạy dbt (mỗi lần làm việc)

```powershell
.venv-dbt\Scripts\Activate.ps1        # nếu chưa activate
$env:PYTHONUTF8 = "1"                 # tránh lỗi UnicodeDecodeError ở trên

docker compose up -d                  # đảm bảo Postgres đang chạy

dbt debug --project-dir dbt --profiles-dir dbt   # kiểm tra kết nối
dbt run   --project-dir dbt --profiles-dir dbt   # build models (từ bước 2 trở đi)
dbt test  --project-dir dbt --profiles-dir dbt   # chạy data quality tests (từ bước 5)
```

## Cấu trúc

```
dbt/
├── dbt_project.yml          # cấu hình project, khai schema đích từng layer
├── profiles.yml             # kết nối Postgres (qua env_var, có default khớp docker-compose.yml)
├── macros/
│   └── get_custom_schema.sql   # override để marts đổ đúng vào schema `dwh` có sẵn
├── models/
│   ├── staging/              # đọc thô từ source staging.yellow_trips (bước 2)
│   ├── intermediate/         # tính surrogate key theo thời gian (bước 3)
│   └── marts/                # dim_date, dim_time, dim_vendor, dim_payment_type,
│                              # dim_rate_code, fact_trips (bước 4)
├── seeds/                    # dữ liệu tĩnh (vendor/payment/rate) dạng CSV (bước 4)
└── tests/                    # test tùy biến, vd. dropoff > pickup (bước 5)
```
