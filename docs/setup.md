1. Tải dataset từ Kaggle: https://www.kaggle.com/datasets/elemento/nyc-yellow-taxi-trip-data?resource=download
2. Giải nén và đặt tên /raw_data
3. Xem tên file và dung lượng từng file (cmd: dir raw_data)
	Directory of D:\Project\NYC-Taxi-Data-Pipeline\raw_data
	07/01/2026  02:20 PM    <DIR>          .
	07/01/2026  02:20 PM    <DIR>          ..
	12/09/2021  07:31 AM     1,985,964,692 yellow_tripdata_2015-01.csv
	12/09/2021  07:33 AM     1,708,674,492 yellow_tripdata_2016-01.csv
	12/09/2021  07:36 AM     1,783,554,554 yellow_tripdata_2016-02.csv
	12/09/2021  07:38 AM     1,914,669,757 yellow_tripdata_2016-03.csv
        4 File(s)  7,392,863,495 bytes
        2 Dir(s)  12,679,499,776 bytes free
4. Kiểm tra nhanh cấu trúc dữ liệu bằng Python (không cần load hết vào RAM)
	import pandas as pd

	# chỉ đọc 5 dòng đầu để xem cột
	df_sample = pd.read_csv("raw_data/yellow_tripdata_2015-01.csv", nrows=5)
	print(df_sample.columns.tolist())
	print(df_sample.dtypes)
	print(df_sample.head())

	# đếm số dòng thực tế mà không load hết (đọc theo chunk)
	total_rows = sum(1 for _ in open("raw_data/yellow_tripdata_2015-01.csv"))
	print(f"Tổng số dòng: {total_rows:,}")

	output:
	PS D:\Project\NYC-Taxi-Data-Pipeline> python main.py
	['VendorID', 'tpep_pickup_datetime', 'tpep_dropoff_datetime', 'passenger_count', 'trip_distance', 'pickup_longitude', 'pickup_latitude', 'RateCodeID', 'store_and_fwd_flag', 'dropoff_longitude', 'dropoff_latitude', 	'payment_type', 'fare_amount', 'extra', 'mta_tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount']
	VendorID                   int64
	tpep_pickup_datetime         str
	tpep_dropoff_datetime        str
	passenger_count            int64
	trip_distance            float64
	pickup_longitude         float64
	pickup_latitude          float64
	RateCodeID                 int64
	store_and_fwd_flag           str
	dropoff_longitude        float64
	dropoff_latitude         float64
	payment_type               int64
	fare_amount              float64
	extra                    float64
	mta_tax                  float64
	tip_amount               float64
	tolls_amount               int64
	improvement_surcharge    float64
	total_amount             float64
	dtype: object
   	VendorID tpep_pickup_datetime tpep_dropoff_datetime  passenger_count  trip_distance  pickup_longitude  pickup_latitude  ...  fare_amount extra  mta_tax  tip_amount  tolls_amount  improvement_surcharge  total_amount
	0         2  2015-01-15 19:05:39   2015-01-15 19:23:42                1           1.59        -73.993896        40.750111  ...         12.0   1.0      0.5        3.25             0                    0.3         17.05
	1         1  2015-01-10 20:33:38   2015-01-10 20:53:28                1           3.30        -74.001648        40.724243  ...         14.5   0.5      0.5        2.00             0                    0.3         17.80
	2         1  2015-01-10 20:33:38   2015-01-10 20:43:41                1           1.80        -73.963341        40.802788  ...          9.5   0.5      0.5        0.00             0                    0.3         10.80
	3         1  2015-01-10 20:33:39   2015-01-10 20:35:31                1           0.50        -74.009087        40.713818  ...          3.5   0.5      0.5        0.00             0                    0.3          4.80
	4         1  2015-01-10 20:33:39   2015-01-10 20:52:58                1           3.00        -73.971176        40.762428  ...         15.0   0.5      0.5        0.00             0                    0.3         16.30
	[5 rows x 19 columns]
5. Tạo file: docker-compose.yml và 01_create_schema.sql
6. Chạy lệnh: docker compose up -d (cài Docker Desktop trước)
	PS D:\Project\NYC-Taxi-Data-Pipeline> docker compose up -d
	[+] up 6/11
	✔ Image dpage/pgadmin4                Pulled                                                                   5.1s
	✔ Network nyctaxidatapipeline_default Created                                                                  0.1s
	✔ Volume nyctaxidatapipeline_pgdata   Created                                                                  0.0s
	✔ Container taxi_postgres             Started                                                                  1.0s
	✔ Container taxi_metabase             Started                                                                  1.1s
	✔ Container taxi_pgadmin              Started                                                                  1.1s
7. Đặt file load_staging.py vào thư mục gốc project (ngang hàng với raw_data/ và docker-compose.yml).
8. Cài thư viện: pip install psycopg2-binary
9. python load_staging.py
10. Tạo sql/02_transform_load.sql
11. chạy lệnh (không đóng cửa sổ chạy lệnh này): Get-Content sql/02_transform_load.sql | docker exec -i taxi_postgres psql -U taxi_user -d taxi_dwh     
Kết quả cuối cùng:
	PS D:\Project\NYC-Taxi-Data-Pipeline> Get-Content sql/02_transform_load.sql | docker exec -i taxi_postgres psql -U taxi_user -d taxi_dwh
	TRUNCATE TABLE
	INSERT 0 506
	INSERT 0 1440
	INSERT 0 21792952
		table_name      | row_count 
	----------------------+-----------
	dwh.dim_date         |       506
	dwh.dim_time         |      1440
	dwh.fact_trips       |  21792952
	staging.yellow_trips |  22288907
	(4 rows)
12. Mở cửa sổ khác để theo dõi tiến độ, chạy lệnh (có thể chạy lệnh này cách vài phút): docker exec -i taxi_postgres psql -U taxi_user -d taxi_dwh -c "SELECT pid, state, now() - query_start AS running_time, LEFT(query, 60) AS query_preview FROM pg_stat_activity WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%';"

