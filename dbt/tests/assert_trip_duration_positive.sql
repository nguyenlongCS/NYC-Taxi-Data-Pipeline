{#
    Điều kiện lọc gốc #5 (docs/notes.md mục 1 / 02_transform_load.sql):
    tpep_dropoff_datetime > tpep_pickup_datetime.

    fact_trips không giữ lại 2 cột timestamp gốc (chỉ có date_id/time_id
    surrogate key + trip_duration_min tính sẵn) — nên kiểm tra gián tiếp
    qua trip_duration_min: nếu dropoff > pickup thật sự đúng, thời lượng
    chuyến đi luôn phải dương. Test PASS khi trả về 0 dòng.
#}

select *
from {{ ref('fact_trips') }}
where trip_duration_min <= 0
