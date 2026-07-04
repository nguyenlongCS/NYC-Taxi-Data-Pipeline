"""
load_parquet_to_staging.py

Nạp dữ liệu đã qua Spark (processed_data/yellow_trips_clean/*.parquet) vào
staging.yellow_trips -- thay thế load_staging.py cho khối lượng dữ liệu lớn
(xem docs/roadmap.md, luồng 2 -> staging).

Khác với load_staging.py (COPY thẳng từ CSV), script này đọc từng file Parquet
MỘT LẦN LƯỢT (không gộp cả 22 triệu dòng vào 1 DataFrame duy nhất trong RAM),
ghi ra buffer CSV tạm trong bộ nhớ, rồi COPY vào Postgres -- cùng kỹ thuật
COPY như load_staging.py, chỉ khác nguồn đọc.

⚠️ load_staging.py (đọc thẳng CSV) vẫn được GIỮ LẠI làm phương án dự phòng --
xem docs/roadmap.md. Script này không thay thế, chỉ bổ sung đường nạp dữ liệu
đã qua Spark.

Chạy trên máy host (không chạy trong container Spark) -- cần các thư viện
trong requirements.txt (đã bổ sung pyarrow để đọc Parquet):
    pip install -r requirements.txt
    python load_parquet_to_staging.py
"""

import io
import time
from pathlib import Path

import pandas as pd
import psycopg2

# ---- Cấu hình kết nối (khớp với docker-compose.yml, giống load_staging.py) ----
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "taxi_dwh",
    "user": "taxi_user",
    "password": "taxi_pass",
}

PARQUET_DIR = Path("processed_data/yellow_trips_clean")

# Thứ tự cột PHẢI khớp đúng thứ tự Spark ghi ra Parquet
# (xem TARGET_COLUMNS trong spark_jobs/clean_taxi_data.py)
COLUMN_ORDER = [
    "vendor_id", "tpep_pickup_datetime", "tpep_dropoff_datetime",
    "passenger_count", "trip_distance", "pickup_longitude", "pickup_latitude",
    "rate_code_id", "store_and_fwd_flag", "dropoff_longitude", "dropoff_latitude",
    "payment_type", "fare_amount", "extra", "mta_tax", "tip_amount",
    "tolls_amount", "improvement_surcharge", "total_amount",
]

# HEADER false -- buffer CSV tạo ra không có dòng header (khác với
# load_staging.py vì đó đọc thẳng CSV gốc có sẵn header từ Kaggle)
COPY_SQL = f"""
    COPY staging.yellow_trips ({", ".join(COLUMN_ORDER)})
    FROM STDIN WITH (FORMAT csv, HEADER false)
"""


def find_parquet_files():
    """Tìm các file Parquet thật sự (bỏ qua _SUCCESS, .crc do Spark sinh ra)."""
    files = sorted(PARQUET_DIR.glob("*.parquet"))
    if not files:
        raise RuntimeError(
            f"Không tìm thấy file .parquet nào trong {PARQUET_DIR}. "
            "Kiểm tra lại đã chạy spark_jobs/clean_taxi_data.py chưa."
        )
    return files


def load_one_file(conn, file_path: Path, file_index: int, total_files: int):
    print(f"→ [{file_index}/{total_files}] Đang đọc {file_path.name} ...")
    start = time.time()

    df = pd.read_parquet(file_path, engine="pyarrow", columns=COLUMN_ORDER)
    n_rows = len(df)

    # Ghi ra buffer CSV trong RAM -- không tạo file tạm trên đĩa.
    # index=False: không ghi cột index của pandas.
    # header=False: khớp với COPY_SQL (HEADER false) ở trên.
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    with conn.cursor() as cur:
        cur.copy_expert(COPY_SQL, buffer)
    conn.commit()

    elapsed = time.time() - start
    print(f"  Xong {n_rows:,} dòng trong {elapsed:.1f} giây.")
    return n_rows


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        # Kiểm tra bảng đích tồn tại (giống load_staging.py)
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('staging.yellow_trips');")
            if cur.fetchone()[0] is None:
                raise RuntimeError(
                    "Chưa thấy bảng staging.yellow_trips. "
                    "Kiểm tra lại sql/01_create_schema.sql đã chạy chưa."
                )

        # TRUNCATE trước khi nạp -- an toàn vì không có bảng nào tham chiếu
        # FK tới staging.yellow_trips (xem docs/notes.md mục 2). Giúp script
        # idempotent -- chạy lại bao nhiêu lần cũng ra kết quả giống nhau.
        with conn.cursor() as cur:
            print("Đang TRUNCATE staging.yellow_trips để nạp lại từ đầu...")
            cur.execute("TRUNCATE staging.yellow_trips;")
        conn.commit()

        files = find_parquet_files()
        print(f"Tìm thấy {len(files)} file Parquet trong {PARQUET_DIR}.\n")

        total_rows = 0
        for i, file_path in enumerate(files, start=1):
            total_rows += load_one_file(conn, file_path, i, len(files))

        # Đếm lại trực tiếp trong DB để xác nhận (không tin vào total_rows
        # cộng dồn ở Python, phòng trường hợp lệch do lỗi COPY giữa chừng)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM staging.yellow_trips;")
            db_count = cur.fetchone()[0]

        print(f"\nTổng số dòng đã nạp (Python cộng dồn): {total_rows:,}")
        print(f"Tổng số dòng trong staging.yellow_trips (đếm trực tiếp DB): {db_count:,}")
        if total_rows != db_count:
            print("⚠️  CẢNH BÁO: hai con số trên KHÔNG khớp nhau -- kiểm tra lại log phía trên.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
