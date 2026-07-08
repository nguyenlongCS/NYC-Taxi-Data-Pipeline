"""
Pydantic response models — tên field khớp 1-1 với tên cột (alias tiếng Việt)
trả về từ 5 câu SQL trong sql/analytics/, để Swagger UI phản ánh đúng dữ liệu
thật thay vì đoán tên cột.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# 03_revenue_by_hour.sql
# ---------------------------------------------------------------------------
class RevenueByHour(BaseModel):
    gio_trong_ngay: int
    so_chuyen: int
    doanh_thu_tb: float
    tong_doanh_thu: float


# ---------------------------------------------------------------------------
# 04_trend_by_weekday.sql
# ---------------------------------------------------------------------------
class TrendByWeekday(BaseModel):
    day_of_week: int
    ten_ngay: str
    is_weekend: bool
    so_chuyen: int
    doanh_thu_tb: float
    tip_tb: float


# ---------------------------------------------------------------------------
# 05_payment_type_distribution.sql
# ---------------------------------------------------------------------------
class PaymentTypeDistribution(BaseModel):
    hinh_thuc_thanh_toan: str
    so_chuyen: int
    ty_le_phan_tram: float
    doanh_thu_tb: float
    tip_tb: float


# ---------------------------------------------------------------------------
# 06_tip_by_vendor.sql
# ---------------------------------------------------------------------------
class TipByVendor(BaseModel):
    vendor_name: str
    so_chuyen: int
    tip_tb: float
    quang_duong_tb: float
    doanh_thu_tb: float
    # NULLIF(AVG(total_amount), 0) có thể trả NULL về mặt lý thuyết
    ty_le_tip_phan_tram: Optional[float] = None


# ---------------------------------------------------------------------------
# 07_rush_hour_impact.sql
# ---------------------------------------------------------------------------
class RushHourImpact(BaseModel):
    is_rush_hour: bool
    so_chuyen: int
    quang_duong_tb_dam: float
    thoi_gian_tb_phut: float
    # NULLIF(AVG(trip_duration_min), 0) có thể trả NULL về mặt lý thuyết
    toc_do_tb_dam_moi_phut: Optional[float] = None
    doanh_thu_tb: float


# ---------------------------------------------------------------------------
# GET /api/trips — 1 dòng dwh.fact_trips
#
# KHÔNG có field trip_id: mặc dù docs/data_dictionary.md mô tả cột
# `trip_id BIGSERIAL (PK)`, bảng thật do dbt build ra không có cột khóa
# chính/surrogate key nào (đã xác nhận qua information_schema.columns trên
# DB thật) -- xem ghi chú đầy đủ ở đầu routers/trips.py.
# ---------------------------------------------------------------------------
class Trip(BaseModel):
    pickup_date_id: int
    pickup_time_id: int
    dropoff_date_id: int
    dropoff_time_id: int
    vendor_id: int
    payment_type_id: int
    rate_code_id: int
    pickup_longitude: float
    pickup_latitude: float
    dropoff_longitude: float
    dropoff_latitude: float
    passenger_count: int
    trip_distance: float
    trip_duration_min: float
    fare_amount: float
    extra: float
    mta_tax: float
    tip_amount: float
    tolls_amount: float
    improvement_surcharge: float
    total_amount: float


class TripListResponse(BaseModel):
    limit: int
    offset: int
    count: int  # số dòng thực trả về trong trang này (<= limit)
    items: list[Trip]


# ---------------------------------------------------------------------------
# POST /api/pipeline/trigger
# ---------------------------------------------------------------------------
class PipelineTriggerResponse(BaseModel):
    dag_id: str
    dag_run_id: str
    state: Optional[str] = None
    logical_date: Optional[datetime] = None
    airflow_ui_url: str