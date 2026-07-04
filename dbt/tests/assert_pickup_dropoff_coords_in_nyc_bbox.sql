{#
    Điều kiện lọc gốc #4 (docs/notes.md mục 1 / 02_transform_load.sql):
    tọa độ pickup/dropoff phải nằm trong bounding box hợp lý của NYC
    (longitude -74.3 → -73.7, latitude 40.5 → 40.9) — loại điểm GPS lỗi
    ghi nhận là (0,0). Test PASS khi trả về 0 dòng.
#}

select *
from {{ ref('fact_trips') }}
where pickup_longitude  not between -74.3 and -73.7
   or pickup_latitude   not between  40.5 and  40.9
   or dropoff_longitude not between -74.3 and -73.7
   or dropoff_latitude  not between  40.5 and  40.9
