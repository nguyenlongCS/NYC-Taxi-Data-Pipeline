NYC-Taxi-Data-Pipeline/
│
├── docs/                            # Toàn bộ tài liệu của dự án
│   ├── dataset.md                   # Link tải dataset từ Kaggle, mô tả cấu trúc dữ liệu gốc
│   ├── setup.md                     # Hướng dẫn thực hiện từng bước, từ đầu đến khi có dashboard
│   ├── system_architecture.md       # Kiến trúc hệ thống, công nghệ sử dụng, sơ đồ pipeline
│   ├── project_structure.md         # File này — mô tả cấu trúc thư mục và file trong dự án
│   ├── pipeline.md                  # Chi tiết luồng ETL: Extract → Load → Transform → Serve
│   ├── data_dictionary.md           # Từ điển dữ liệu: mô tả từng bảng, từng cột trong DWH
│   ├── notes.md                     # Kiến thức cần nhớ, bài học rút ra trong quá trình làm
│   ├── troubleshooting.md           # Các lỗi đã gặp và cách xử lý
│   ├── checklist.md                 # Đã thực hiện
│   ├── roadmap.md                   # Kế hoạch mở rộng, hướng phát triển tiếp theo
│   └── images/                      # Ảnh dùng cho dự án
│
├── img_demo/                        # Ảnh demo: docker logs, container đang chạy, dashboard...
│
├── raw_data/                        # Dữ liệu gốc — KHÔNG đưa lên GitHub (dung lượng lớn)
│   ├── yellow_tripdata_2015-01.csv  # Dự phòng, chưa nạp
│   ├── yellow_tripdata_2016-01.csv  # ✅ Đã nạp (qua Spark, xem spark_jobs/)
│   ├── yellow_tripdata_2016-02.csv  # ✅ Đã nạp (qua Spark, xem spark_jobs/)
│   └── yellow_tripdata_2016-03.csv  # Dự phòng, chưa nạp
│                                    # (mount read-only vào container spark, xem docker-compose.yml)
│
├── processed_data/                  # 📦 Output của Spark — KHÔNG đưa lên GitHub (dữ liệu trung gian)
│   └── yellow_trips_clean/          # Parquet sạch, 8 file (do coalesce(8) trong clean_taxi_data.py)
│                                    # Input cho load_parquet_to_staging.py
│
├── spark_jobs/                      # ✅ Giai đoạn Spark — dựng luồng 1-2 (xem docs/roadmap.md)
│   └── clean_taxi_data.py           # Đọc CSV -> ép kiểu + audit NULL -> ghi Parquet
│                                    # Chạy trong container spark: xem docker-compose.yml
│
├── sql/
│   ├── 01_create_schema.sql         # DDL rút gọn: chỉ còn tạo schema + staging.yellow_trips
│   │                                # (DDL dwh.* đã chuyển hết sang dbt/ — xem ghi chú trong file)
│   ├── archive/
│   │   └── 02_transform_load.sql    # 📦 Đã nghỉ hưu — thay bằng dbt/ (staging→intermediate→marts).
│   │                                # Giữ lại để tham khảo/đối chiếu lịch sử, KHÔNG đặt ở sql/ gốc
│   │                                # vì Docker initdb sẽ tự chạy lại (đã kiểm chứng số liệu khớp
│   │                                # 100% với dbt trước khi archive — xem docs/troubleshooting.md)
│   └── analytics/                   # Các câu truy vấn dùng để tạo dashboard trên Metabase
│       ├── 03_revenue_by_hour.sql
│       ├── 04_trend_by_weekday.sql
│       ├── 05_payment_type_distribution.sql
│       ├── 06_tip_by_vendor.sql
│       └── 07_rush_hour_impact.sql
│
├── dbt/                             # ✅ Thay thế sql/archive/02_transform_load.sql hoàn toàn
│   │                                # (xem docs/roadmap.md, mục "1. dbt")
│   ├── dbt_project.yml              # Cấu hình project — khai schema đích từng layer
│   │                                # (staging_dbt / intermediate / dwh) + seeds
│   ├── profiles.yml                 # Kết nối Postgres qua env_var (default khớp docker-compose.yml)
│   ├── README.md                    # Setup venv Python 3.12 riêng, lệnh chạy dbt,
│   │                                # các lỗi Windows đã gặp (xem docs/troubleshooting.md)
│   ├── macros/
│   │   └── get_custom_schema.sql    # Override để model/seed đổ đúng vào schema khai báo
│   │                                # (marts đổ thẳng vào `dwh`, không bị ghép tiền tố)
│   ├── models/
│   │   ├── staging/                 # Đọc thô từ source staging.yellow_trips, chỉ rename cột
│   │   │   ├── _sources.yml
│   │   │   ├── _staging.yml
│   │   │   └── stg_yellow_trips.sql
│   │   ├── intermediate/            # Tính surrogate key thời gian + trip_duration_min
│   │   │   ├── _intermediate.yml
│   │   │   └── int_yellow_trips_keyed.sql
│   │   └── marts/                   # dim_date, dim_time, fact_trips (schema `dwh`)
│   │       ├── _marts.yml           # Mô tả + test (not_null, unique, relationships)
│   │       ├── dim_date.sql
│   │       ├── dim_time.sql
│   │       └── fact_trips.sql       # Incremental model, áp 5 điều kiện lọc dữ liệu bẩn
│   ├── seeds/                       # Thay 3 câu INSERT tĩnh cũ trong 01_create_schema.sql
│   │   ├── _seeds.yml               # Test unique/not_null cho khóa chính từng seed
│   │   ├── dim_vendor.csv
│   │   ├── dim_payment_type.csv
│   │   └── dim_rate_code.csv
│   ├── tests/                       # 5 singular test — mỗi file ứng 1 điều kiện lọc gốc
│   │   ├── assert_trip_distance_in_range.sql
│   │   ├── assert_fare_amount_positive.sql
│   │   ├── assert_passenger_count_positive.sql
│   │   ├── assert_pickup_dropoff_coords_in_nyc_bbox.sql
│   │   └── assert_trip_duration_positive.sql
│   ├── snapshots/                   # Không dùng trong phạm vi dự án này (khung chuẩn dbt)
│   └── analyses/                    # Không dùng trong phạm vi dự án này (khung chuẩn dbt)
│
├── .venv-dbt/                       # ⚠️ Không commit (đã .gitignore) — venv Python 3.12 riêng
│                                    # cho dbt, tách khỏi Python hệ thống (xem dbt/README.md)
│
├── docker-compose.yml               # Postgres + pgAdmin + Metabase + Spark, DB/BI có named volume persist
│                                    # (spark không cần volume riêng — không giữ trạng thái, xem ghi chú trong file)
├── .gitignore                       # Loại trừ raw_data/, processed_data/, .env, __pycache__/, dbt/target/, .venv-dbt/...
├── .env.example                     # Mẫu biến môi trường cho dbt (có default khớp docker-compose.yml)
├── requirements.txt                 # psycopg2-binary, pandas, pyarrow, dbt-postgres...
├── README.md                        # Tổng quan
├── load_staging.py                  # Script nạp CSV vào staging bằng COPY (psycopg2)
│                                    # — giữ làm phương án dự phòng, xem load_parquet_to_staging.py
├── load_parquet_to_staging.py       # ✅ Nạp Parquet (output của Spark) vào staging bằng COPY
└── main.py                          # Script khám phá dữ liệu ban đầu (đọc mẫu, đếm dòng)
