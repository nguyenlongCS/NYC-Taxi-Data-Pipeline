{#
    Điều kiện lọc gốc #2 (docs/notes.md mục 1 / 02_transform_load.sql):
    fare_amount > 0. Test PASS khi trả về 0 dòng.
#}

select *
from {{ ref('fact_trips') }}
where fare_amount <= 0
