"""
load_parquet_to_staging.py

Nạp dữ liệu đã qua Spark (processed_data/yellow_trips_clean/*.parquet) vào
staging.yellow_trips -- thay thế load_staging.py cho khối lượng dữ liệu lớn
(xem docs/roadmap.md, luồng 2 -> staging).

⚠️ ĐÃ SỬA (bài học OOM khi chạy qua Airflow -- xem docs/troubleshooting.md):
Bản đầu tiên đọc NGUYÊN 1 file Parquet (~2.7 triệu dòng) vào 1 DataFrame
pandas, rồi ghi thêm 1 BẢN SAO thứ 2 của toàn bộ dữ liệu đó ra buffer CSV
trong RAM (io.StringIO) trước khi COPY vào Postgres -- tức RAM đỉnh điểm
phải chứa 2 bản đầy đủ dữ liệu cùng lúc. Trong container không giới hạn
mem_limit, chạy chung với Postgres + Airflow scheduler/webserver + Metabase
+ pgAdmin trong cùng 1 máy ảo WSL2 (8GB), việc này gây OOM Kill
(DockerContainerFailedException StatusCode 137).

Cách sửa TRIỆT ĐỂ (không phải chỉ tăng RAM): đọc Parquet theo TỪNG LÔ NHỎ
(batch) bằng pyarrow.parquet.ParquetFile.iter_batches() thay vì
pandas.read_parquet() nạp nguyên file. RAM sử dụng giờ chỉ tỉ lệ với
BATCH_SIZE (mặc định 200,000 dòng/lô -- một phần rất nhỏ so với ~2.7 triệu
dòng/file), KHÔNG phụ thuộc file lớn hay nhỏ, và không phụ thuộc bạn cấp bao
nhiêu RAM cho WSL2/Docker Desktop nữa.

Chạy được ở 2 nơi (không đổi logic, chỉ khác cách set biến môi trường):
  1. Trên máy host: python load_parquet_to_staging.py
     -> không set gì cả, DB_HOST mặc định "localhost" như cũ.
  2. Trong container "taxi-loader" do Airflow gọi qua DockerOperator (xem
     airflow/dags/taxi_pipeline_dag.py) -> Airflow tự set DB_HOST=postgres.
"""

import io
import os
import time
from pathlib import Path

import psycopg2
import pyarrow.parquet as pq

# ---- Cấu hình kết nối -- đọc từ biến môi trường, mặc định KHÔNG đổi so với
# bản gốc (localhost/5432/taxi_dwh/taxi_user/taxi_pass) để chạy tay trên host
# vẫn hoạt động y hệt như trước, không cần set gì thêm. ----
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "taxi_dwh"),
    "user": os.environ.get("DB_USER", "taxi_user"),
    "password": os.environ.get("DB_PASSWORD", "taxi_pass"),
}

# Số dòng xử lý mỗi lô -- đây là "nút vặn" duy nhất kiểm soát RAM sử dụng.
# Tăng lên nếu máy nhiều RAM (chạy nhanh hơn, ít lần COPY hơn); giảm xuống
# nếu máy ít RAM hơn nữa (an toàn hơn, chạy chậm hơn một chút). KHÔNG cần
# đổi code, chỉ cần đổi biến môi trường LOADER_BATCH_SIZE.
BATCH_SIZE = int(os.environ.get("LOADER_BATCH_SIZE", "200000"))

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
    print(f"→ [{file_index}/{total_files}] Đang đọc {file_path.name} (batch={BATCH_SIZE:,} dòng/lô) ...")
    start = time.time()

    parquet_file = pq.ParquetFile(file_path)
    n_rows_file = 0
    n_batches = 0

    # iter_batches() đọc từng lô row-group, KHÔNG nạp nguyên file vào RAM.
    # Mỗi vòng lặp: 1 lô nhỏ -> DataFrame nhỏ -> buffer CSV nhỏ -> COPY ->
    # commit -> giải phóng RAM ngay (buffer/DataFrame hết scope) -- RAM đỉnh
    # điểm chỉ còn tỉ lệ với BATCH_SIZE, không còn tỉ lệ với dung lượng file.
    for batch in parquet_file.iter_batches(batch_size=BATCH_SIZE, columns=COLUMN_ORDER):
        df_chunk = batch.to_pandas()
        n_rows_chunk = len(df_chunk)

        buffer = io.StringIO()
        df_chunk.to_csv(buffer, index=False, header=False)
        buffer.seek(0)

        with conn.cursor() as cur:
            cur.copy_expert(COPY_SQL, buffer)
        conn.commit()

        n_rows_file += n_rows_chunk
        n_batches += 1
        # Giải phóng tường minh, không đợi garbage collector -- giữ RAM ổn
        # định qua nhiều file liên tiếp thay vì tích luỹ dần.
        del df_chunk, buffer

    elapsed = time.time() - start
    print(f"  Xong {n_rows_file:,} dòng ({n_batches} lô) trong {elapsed:.1f} giây.")
    return n_rows_file


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
        # idempotent -- chạy lại bao nhiêu lần cũng ra kết quả giống nhau,
        # kể cả khi lần chạy trước bị OOM Kill giữa chừng (dữ liệu dở dang
        # bị xoá sạch, không lo nạp trùng/thiếu).
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