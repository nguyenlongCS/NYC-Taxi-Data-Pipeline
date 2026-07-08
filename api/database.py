"""
Kết nối Postgres cho service API — SQLAlchemy (sync) + psycopg2, khớp
style đồng bộ đang dùng trong load_staging.py / load_parquet_to_staging.py
của phần còn lại dự án.

Toàn bộ giá trị kết nối đọc từ biến môi trường do docker-compose.yml truyền
vào (không hardcode giá trị thật ở đây) — cùng quy tắc với các service khác
trong project (xem .env.example).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Trong network nội bộ Docker, host luôn là tên service `postgres`
# (giống cách Metabase/pgAdmin kết nối — xem docs/notes.md mục 6),
# không phải "localhost". Cho phép override qua env để tiện chạy API
# ngoài Docker (vd. dev cục bộ) khi cần.
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ["POSTGRES_DB"]
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# pool_pre_ping tránh lỗi "connection already closed" nếu Postgres restart
# trong lúc API vẫn đang chạy (container postgres có healthcheck riêng,
# nhưng API là service độc lập nên tự phòng vệ thêm ở tầng kết nối).
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency — 1 session cho mỗi request, luôn đóng lại sau khi xong."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
