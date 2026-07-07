"""
airflow/scripts/create_airflow_db.py

Tạo database cho Airflow metadata (airflow_db) trong CÙNG container Postgres
đang chứa taxi_dwh (quyết định "dùng chung container postgres" — xem
docs/roadmap.md, giai đoạn Airflow). Chạy 1 lần bởi airflow-init trước khi
`airflow db migrate`. Idempotent — kiểm tra database đã tồn tại chưa trước
khi tạo, an toàn để chạy lại nhiều lần.

Lưu ý về lỗi collation đã gặp khi thử nghiệm trước đó:
`CREATE DATABASE ... ` mặc định dùng TEMPLATE template1. Nếu template1 trong
image postgres:16-alpine (musl libc, không phải glibc như bản Debian) có
collation không khớp mong đợi, lệnh tạo DB sẽ báo lỗi collation. Cách né an
toàn: dùng thẳng TEMPLATE template0 (bản gốc, chưa bị thay đổi) và ép cứng
LC_COLLATE/LC_CTYPE = 'C' để không phụ thuộc locale mặc định của container.
"""
import os
import sys

import psycopg2
from psycopg2 import sql

PG_HOST = os.environ.get("PGHOST", "postgres")
PG_PORT = os.environ.get("PGPORT", "5432")
PG_USER = os.environ["PGUSER"]
PG_PASSWORD = os.environ["PGPASSWORD"]
PG_ADMIN_DB = os.environ.get("PG_ADMIN_DB", "postgres")
TARGET_DB = os.environ["AIRFLOW_DB_NAME"]


def main():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_ADMIN_DB,
    )
    # CREATE DATABASE không được phép chạy trong transaction block -> bắt buộc autocommit.
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (TARGET_DB,))
            exists = cur.fetchone() is not None

        if exists:
            print(f"Database '{TARGET_DB}' đã tồn tại, bỏ qua.")
            return

        with conn.cursor() as cur:
            print(
                f"Đang tạo database '{TARGET_DB}' "
                f"(TEMPLATE template0, LC_COLLATE/LC_CTYPE='C')..."
            )
            cur.execute(
                sql.SQL(
                    "CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' "
                    "LC_COLLATE 'C' LC_CTYPE 'C';"
                ).format(sql.Identifier(TARGET_DB))
            )
        print(f"Đã tạo database '{TARGET_DB}'.")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Lỗi khi tạo database Airflow: {exc}", file=sys.stderr)
        sys.exit(1)
