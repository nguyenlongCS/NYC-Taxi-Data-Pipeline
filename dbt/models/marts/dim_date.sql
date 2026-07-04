{#
    Marts — dim_date. Sinh bằng generate_series() theo khoảng ngày thực tế
    xuất hiện trong dữ liệu (cả pickup lẫn dropoff), y hệt logic gốc trong
    sql/02_transform_load.sql.

    Đọc từ int_yellow_trips_keyed (CHƯA lọc dữ liệu bẩn) chứ không phải từ
    fact_trips (đã lọc) — để đảm bảo phủ hết mọi date_id mà fact_trips có
    thể tham chiếu tới (fact_trips là tập con của dữ liệu chưa lọc, nên
    khoảng ngày của nó luôn nằm trong khoảng ngày ở đây). Giữ đúng hành vi
    gốc: 506 dòng (nhiều hơn ~60 ngày dự kiến vì lẫn vài timestamp lỗi
    trong dữ liệu thô — xem docs/notes.md mục 1 và docs/data_dictionary.md).
#}

with bounds as (

    select
        least(min(tpep_pickup_datetime)::date, min(tpep_dropoff_datetime)::date) as min_date,
        greatest(max(tpep_pickup_datetime)::date, max(tpep_dropoff_datetime)::date) as max_date
    from {{ ref('int_yellow_trips_keyed') }}

),

date_series as (

    select generate_series(min_date, max_date, interval '1 day')::date as full_date
    from bounds

)

select
    to_char(full_date, 'YYYYMMDD')::integer                   as date_id,
    full_date,
    extract(day from full_date)::smallint                      as day,
    extract(month from full_date)::smallint                     as month,
    extract(quarter from full_date)::smallint                    as quarter,
    extract(year from full_date)::smallint                        as year,
    extract(isodow from full_date)::smallint                       as day_of_week,
    to_char(full_date, 'Day')                                        as day_name,
    extract(isodow from full_date) in (6, 7)                          as is_weekend
from date_series
