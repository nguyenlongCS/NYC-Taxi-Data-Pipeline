{#
    Điều kiện lọc gốc #1 (docs/notes.md mục 1 / 02_transform_load.sql):
    trip_distance > 0 AND trip_distance < 100.

    Test PASS khi câu SELECT dưới đây trả về 0 dòng — nghĩa là không còn
    dòng nào vi phạm sót lại trong fact_trips sau khi lọc. Nếu sau này ai
    đó sửa nhầm điều kiện WHERE trong fact_trips.sql, test này sẽ FAIL để
    cảnh báo ngay, thay vì âm thầm lọt outlier vào warehouse.
#}

select *
from {{ ref('fact_trips') }}
where trip_distance <= 0 or trip_distance >= 100
