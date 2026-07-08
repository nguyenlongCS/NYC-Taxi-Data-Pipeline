"""
GET /api/trips — đọc trực tiếp dwh.fact_trips (21.8 triệu dòng), phân trang
kiểu LIMIT/OFFSET đơn giản (đã chốt: đủ dùng cho demo/portfolio, đánh đổi
là offset càng lớn thì Postgres càng phải quét/bỏ qua nhiều dòng trước đó).

⚠️ LƯU Ý QUAN TRỌNG — sai khác giữa docs/data_dictionary.md và schema thật:
`data_dictionary.md` mô tả `dwh.fact_trips` có cột `trip_id BIGSERIAL (PK)`,
nhưng bảng thật do dbt build ra KHÔNG có cột khóa chính/surrogate key nào cả
(đã xác nhận bằng `information_schema.columns` trên DB thật — 21 cột, không
có `trip_id`). Đây là gap thật giữa tài liệu và model dbt hiện tại, chưa sửa
ở đây vì ngoài phạm vi API — xem ghi chú "Hướng nâng cấp" cuối file.

Vì không có PK, ORDER BY để phân trang ổn định dùng `ctid` (định danh vật lý
của dòng trong Postgres) thay vì 1 cột nghiệp vụ. Đủ ổn định cho mục đích
demo/portfolio hiện tại (bảng chỉ APPEND qua dbt incremental, không UPDATE
tại chỗ) — nhưng KHÔNG đảm bảo thứ tự giữ nguyên nếu bảng bị VACUUM FULL
hoặc dbt full-refresh lại. Nếu cần thứ tự ổn định lâu dài/theo nghiệp vụ
(vd. theo pickup_date_id), xem "Hướng nâng cấp" cuối file.

KHÔNG chạy COUNT(*) tổng mặc định (rất tốn với 21.8 triệu dòng nếu gọi ở
mỗi request) — response chỉ trả số dòng thực tế của TRANG hiện tại (`count`),
không trả tổng số dòng toàn bảng.

--- Hướng nâng cấp (chưa làm, cần đụng vào dbt/models/marts/fact_trips.sql) ---
Thêm surrogate key thật vào model dbt, ví dụ:
    {{ dbt_utils.generate_surrogate_key(['pickup_date_id','pickup_time_id',
       'vendor_id','pickup_longitude','pickup_latitude','total_amount']) }}
       AS trip_id
rồi `dbt build` lại, cập nhật SELECT/ORDER BY dưới đây dùng trip_id thật,
đồng thời sửa data_dictionary.md cho khớp cách sinh key mới (không còn là
BIGSERIAL tự tăng nữa nếu dùng surrogate key dạng hash).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas import TripListResponse

router = APIRouter(prefix="/api/trips", tags=["trips"])

_BASE_SELECT = """
    SELECT
        pickup_date_id, pickup_time_id, dropoff_date_id, dropoff_time_id,
        vendor_id, payment_type_id, rate_code_id,
        pickup_longitude, pickup_latitude, dropoff_longitude, dropoff_latitude,
        passenger_count, trip_distance, trip_duration_min,
        fare_amount, extra, mta_tax, tip_amount, tolls_amount,
        improvement_surcharge, total_amount
    FROM dwh.fact_trips
"""


@router.get("", response_model=TripListResponse)
def list_trips(
    limit: int = Query(50, ge=1, le=500, description="Số dòng tối đa mỗi trang (1-500)"),
    offset: int = Query(0, ge=0, description="Số dòng bỏ qua từ đầu"),
    vendor_id: Optional[int] = Query(None, description="Lọc theo dwh.dim_vendor.vendor_id"),
    payment_type_id: Optional[int] = Query(None, description="Lọc theo dwh.dim_payment_type.payment_type_id"),
    pickup_date_from: Optional[int] = Query(
        None, description="Lọc pickup_date_id >= giá trị này, định dạng YYYYMMDD (vd. 20160115)"
    ),
    pickup_date_to: Optional[int] = Query(
        None, description="Lọc pickup_date_id <= giá trị này, định dạng YYYYMMDD (vd. 20160131)"
    ),
    db: Session = Depends(get_db),
):
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if vendor_id is not None:
        conditions.append("vendor_id = :vendor_id")
        params["vendor_id"] = vendor_id
    if payment_type_id is not None:
        conditions.append("payment_type_id = :payment_type_id")
        params["payment_type_id"] = payment_type_id
    if pickup_date_from is not None:
        conditions.append("pickup_date_id >= :pickup_date_from")
        params["pickup_date_from"] = pickup_date_from
    if pickup_date_to is not None:
        conditions.append("pickup_date_id <= :pickup_date_to")
        params["pickup_date_to"] = pickup_date_to

    sql = _BASE_SELECT
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY ctid LIMIT :limit OFFSET :offset"

    rows = db.execute(text(sql), params).mappings().all()

    return TripListResponse(limit=limit, offset=offset, count=len(rows), items=rows)