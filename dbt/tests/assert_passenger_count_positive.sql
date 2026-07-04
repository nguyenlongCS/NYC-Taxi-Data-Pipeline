{#
    Điều kiện lọc gốc #3 (docs/notes.md mục 1 / 02_transform_load.sql):
    passenger_count > 0. Test PASS khi trả về 0 dòng.
#}

select *
from {{ ref('fact_trips') }}
where passenger_count <= 0
