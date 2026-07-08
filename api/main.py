"""
Entry point service `api` — expose dữ liệu dwh.* qua REST, dùng để đọc dữ
liệu (luồng 5, 6) và trigger pipeline (luồng 10) theo docs/roadmap.md.

Swagger UI tự động tại /docs, ReDoc tại /redoc.
"""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routers import analytics, pipeline, trips

app = FastAPI(
    title="NYC Taxi Data Pipeline API",
    description=(
        "Expose dữ liệu dwh.* (taxi_dwh) qua REST + trigger thủ công "
        "DAG Airflow taxi_pipeline. Xem docs/roadmap.md mục REST API."
    ),
    version="1.0.0",
)

app.include_router(analytics.router)
app.include_router(trips.router)
app.include_router(pipeline.router)


@app.get("/api/health", tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """Kiểm tra API sống + kết nối được tới Postgres (taxi_dwh)."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
