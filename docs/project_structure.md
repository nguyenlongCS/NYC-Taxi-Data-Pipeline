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
│   ├── yellow_tripdata_2016-01.csv  # ✅ Đã nạp vào staging
│   ├── yellow_tripdata_2016-02.csv  # ✅ Đã nạp vào staging
│   └── yellow_tripdata_2016-03.csv  # Dự phòng, chưa nạp
│
├── sql/
│   ├── 01_create_schema.sql         # DDL: tạo schema staging + dwh, toàn bộ bảng dim/fact
│   ├── 02_transform_load.sql        # Sinh dim_date/dim_time, transform + nạp fact_trips
│   └── analytics/                   # Các câu truy vấn dùng để tạo dashboard trên Metabase
│       ├── 03_revenue_by_hour.sql
│       ├── 04_trend_by_weekday.sql
│       ├── 05_payment_type_distribution.sql
│       ├── 06_tip_by_vendor.sql
│       └── 07_rush_hour_impact.sql
│
├── docker-compose.yml               # Postgres + pgAdmin + Metabase, đều có named volume persist
├── .gitignore                       # Loại trừ raw_data/, .env, __pycache__/...
├── requirements.txt                 # psycopg2-binary, pandas...
├── README.md                        # Tổng quan
├── load_staging.py                  # Script nạp CSV vào staging bằng COPY (psycopg2)
└── main.py                          # Script khám phá dữ liệu ban đầu (đọc mẫu, đếm dòng)