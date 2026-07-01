"""
load_staging.py
Nạp các file CSV NYC Yellow Taxi vào bảng staging.yellow_trips
bằng lệnh COPY của PostgreSQL (nhanh hơn nhiều lần so với insert từng dòng).

Cài thư viện cần thiết trước khi chạy:
    pip install psycopg2-binary
"""

import psycopg2
import time
from pathlib import Path

# ---- Cấu hình kết nối (khớp với docker-compose.yml) ----
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "taxi_dwh",
    "user": "taxi_user",
    "password": "taxi_pass",
}

# ---- Danh sách file cần nạp ----
RAW_DATA_DIR = Path("raw_data")
FILES_TO_LOAD = [
    "yellow_tripdata_2016-01.csv",
    "yellow_tripdata_2016-02.csv",
]

COPY_SQL = """
    COPY staging.yellow_trips (
        vendor_id, tpep_pickup_datetime, tpep_dropoff_datetime,
        passenger_count, trip_distance,
        pickup_longitude, pickup_latitude,
        rate_code_id, store_and_fwd_flag,
        dropoff_longitude, dropoff_latitude,
        payment_type, fare_amount, extra, mta_tax,
        tip_amount, tolls_amount, improvement_surcharge, total_amount
    )
    FROM STDIN WITH (FORMAT csv, HEADER true)
"""


def load_file(conn, file_path: Path):
    print(f"→ Đang nạp {file_path.name} ({file_path.stat().st_size / 1e9:.2f} GB)...")
    start = time.time()
    with conn.cursor() as cur, open(file_path, "r", encoding="utf-8") as f:
        cur.copy_expert(COPY_SQL, f)
    conn.commit()
    elapsed = time.time() - start
    print(f"  Xong trong {elapsed:.1f} giây.")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        # Kiểm tra bảng đích đã tồn tại chưa trước khi nạp
        with conn.cursor() as cur:
            cur.execute("""
                SELECT to_regclass('staging.yellow_trips');
            """)
            if cur.fetchone()[0] is None:
                raise RuntimeError(
                    "Chưa thấy bảng staging.yellow_trips. "
                    "Kiểm tra lại 01_create_schema.sql đã chạy chưa (xem log: docker logs taxi_postgres)."
                )

        for filename in FILES_TO_LOAD:
            file_path = RAW_DATA_DIR / filename
            if not file_path.exists():
                print(f"  Bỏ qua: không tìm thấy {file_path}")
                continue
            load_file(conn, file_path)

        # Đếm tổng số dòng đã nạp để xác nhận
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM staging.yellow_trips;")
            total = cur.fetchone()[0]
            print(f"\nTổng số dòng trong staging.yellow_trips: {total:,}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()