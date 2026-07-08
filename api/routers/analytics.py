"""
5 endpoint ứng đúng 5 câu SQL trong sql/analytics/ (đã dùng để tạo dashboard
Metabase — xem docs/pipeline.md giai đoạn 4). Nội dung câu SQL giữ NGUYÊN
1-1 với file gốc để đảm bảo API và dashboard Metabase luôn trả cùng 1 kết
quả — nếu sau này sửa logic, sửa cả 2 nơi (hoặc cân nhắc tách SQL ra file
dùng chung, xem README.md mục "Hướng cải tiến thêm").
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    PaymentTypeDistribution,
    RevenueByHour,
    RushHourImpact,
    TipByVendor,
    TrendByWeekday,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


_REVENUE_BY_HOUR_SQL = text(
    """
    SELECT
        t.hour AS gio_trong_ngay,
        COUNT(*) AS so_chuyen,
        ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb,
        ROUND(SUM(f.total_amount), 0) AS tong_doanh_thu
    FROM dwh.fact_trips f
    JOIN dwh.dim_time t ON f.pickup_time_id = t.time_id
    GROUP BY t.hour
    ORDER BY t.hour
    """
)


@router.get("/revenue-by-hour", response_model=list[RevenueByHour])
def get_revenue_by_hour(db: Session = Depends(get_db)):
    """Doanh thu theo giờ trong ngày (ứng sql/analytics/03_revenue_by_hour.sql)."""
    rows = db.execute(_REVENUE_BY_HOUR_SQL).mappings().all()
    return rows


_TREND_BY_WEEKDAY_SQL = text(
    """
    SELECT
        d.day_of_week,
        TRIM(d.day_name) AS ten_ngay,
        d.is_weekend,
        COUNT(*) AS so_chuyen,
        ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb,
        ROUND(AVG(f.tip_amount), 2) AS tip_tb
    FROM dwh.fact_trips f
    JOIN dwh.dim_date d ON f.pickup_date_id = d.date_id
    GROUP BY d.day_of_week, d.day_name, d.is_weekend
    ORDER BY d.day_of_week
    """
)


@router.get("/trend-by-weekday", response_model=list[TrendByWeekday])
def get_trend_by_weekday(db: Session = Depends(get_db)):
    """Xu hướng theo ngày trong tuần (ứng sql/analytics/04_trend_by_weekday.sql)."""
    rows = db.execute(_TREND_BY_WEEKDAY_SQL).mappings().all()
    return rows


_PAYMENT_TYPE_DISTRIBUTION_SQL = text(
    """
    SELECT
        p.payment_name AS hinh_thuc_thanh_toan,
        COUNT(*) AS so_chuyen,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS ty_le_phan_tram,
        ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb,
        ROUND(AVG(f.tip_amount), 2) AS tip_tb
    FROM dwh.fact_trips f
    JOIN dwh.dim_payment_type p ON f.payment_type_id = p.payment_type_id
    GROUP BY p.payment_name
    ORDER BY so_chuyen DESC
    """
)


@router.get("/payment-distribution", response_model=list[PaymentTypeDistribution])
def get_payment_distribution(db: Session = Depends(get_db)):
    """Phân bố hình thức thanh toán (ứng sql/analytics/05_payment_type_distribution.sql)."""
    rows = db.execute(_PAYMENT_TYPE_DISTRIBUTION_SQL).mappings().all()
    return rows


_TIP_BY_VENDOR_SQL = text(
    """
    SELECT
        v.vendor_name,
        COUNT(*) AS so_chuyen,
        ROUND(AVG(f.tip_amount), 2) AS tip_tb,
        ROUND(AVG(f.trip_distance), 2) AS quang_duong_tb,
        ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb,
        ROUND(100.0 * AVG(f.tip_amount) / NULLIF(AVG(f.total_amount), 0), 2) AS ty_le_tip_phan_tram
    FROM dwh.fact_trips f
    JOIN dwh.dim_vendor v ON f.vendor_id = v.vendor_id
    GROUP BY v.vendor_name
    ORDER BY tip_tb DESC
    """
)


@router.get("/tip-by-vendor", response_model=list[TipByVendor])
def get_tip_by_vendor(db: Session = Depends(get_db)):
    """Tip trung bình theo vendor (ứng sql/analytics/06_tip_by_vendor.sql)."""
    rows = db.execute(_TIP_BY_VENDOR_SQL).mappings().all()
    return rows


_RUSH_HOUR_IMPACT_SQL = text(
    """
    SELECT
        t.is_rush_hour,
        COUNT(*) AS so_chuyen,
        ROUND(AVG(f.trip_distance), 2) AS quang_duong_tb_dam,
        ROUND(AVG(f.trip_duration_min), 2) AS thoi_gian_tb_phut,
        ROUND(AVG(f.trip_distance) / NULLIF(AVG(f.trip_duration_min), 0), 3) AS toc_do_tb_dam_moi_phut,
        ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb
    FROM dwh.fact_trips f
    JOIN dwh.dim_time t ON f.pickup_time_id = t.time_id
    WHERE f.trip_duration_min > 0 AND f.trip_duration_min < 180
    GROUP BY t.is_rush_hour
    ORDER BY t.is_rush_hour DESC
    """
)


@router.get("/rush-hour-impact", response_model=list[RushHourImpact])
def get_rush_hour_impact(db: Session = Depends(get_db)):
    """Ảnh hưởng giờ cao điểm (ứng sql/analytics/07_rush_hour_impact.sql)."""
    rows = db.execute(_RUSH_HOUR_IMPACT_SQL).mappings().all()
    return rows
