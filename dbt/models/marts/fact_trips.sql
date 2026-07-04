{{
    config(
        materialized='incremental'
    )
}}

{#
    Marts — fact_trips. Thay TRUNCATE + full reload (02_transform_load.sql
    gốc) bằng incremental model, theo đúng roadmap.

    CHIẾN LƯỢC INCREMENTAL: dữ liệu nguồn không có cột "loaded_at"/"updated_at"
    (staging.yellow_trips được nạp 1 lần bằng COPY, không có mốc thời gian nạp
    riêng) — nên dùng chính pickup_date_id làm mốc: mỗi lần dbt run tiếp theo
    chỉ xử lý các chuyến có pickup_date_id LỚN HƠN giá trị lớn nhất đã có trong
    bảng đích. Mô phỏng đúng kịch bản thực tế của dataset này: dữ liệu taxi
    được nạp thêm theo từng tháng (ví dụ thêm 2016-03 sau này — xem
    docs/dataset.md phần "Dự phòng / mở rộng sau"). Không dùng unique_key/merge
    vì dữ liệu nguồn không có PK tự nhiên (không có trip_id gốc từ TLC).

    LƯU Ý PHẠM VI: khác với 02_transform_load.sql gốc, model này KHÔNG có cột
    trip_id (BIGSERIAL) — dbt model chỉ là SELECT nên không tự sinh serial PK.
    Các câu SQL phân tích (sql/analytics/) không dùng trip_id nên không ảnh
    hưởng. Có thể bổ sung surrogate key ổn định (vd. qua dbt_utils) như một
    bước cải tiến sau nếu cần.
#}

with trips as (

    select * from {{ ref('int_yellow_trips_keyed') }}

    {% if is_incremental() %}
    where pickup_date_id > (select coalesce(max(pickup_date_id), 0) from {{ this }})
    {% endif %}

),

-- 5 điều kiện lọc dữ liệu bẩn, GIỮ NGUYÊN từ 02_transform_load.sql gốc
-- (xem docs/notes.md mục 1 và docs/data_dictionary.md phần fact_trips):
--   1. trip_distance dương và < 100 dặm (loại outlier)
--   2. fare_amount dương
--   3. passenger_count > 0
--   4. tọa độ pickup/dropoff nằm trong bounding box hợp lý của NYC
--   5. dropoff phải sau pickup
-- + 2 điều kiện khớp FK (rate_code_id, payment_type_id phải tồn tại trong
--   dimension tương ứng — nay là seed thay vì INSERT tĩnh)
filtered as (

    select *
    from trips
    where trip_distance > 0 and trip_distance < 100
      and fare_amount > 0
      and passenger_count > 0
      and pickup_longitude  between -74.3 and -73.7
      and pickup_latitude   between  40.5 and  40.9
      and dropoff_longitude between -74.3 and -73.7
      and dropoff_latitude  between  40.5 and  40.9
      and tpep_dropoff_datetime > tpep_pickup_datetime
      and rate_code_id in (select rate_code_id from {{ ref('dim_rate_code') }})
      and payment_type_id in (select payment_type_id from {{ ref('dim_payment_type') }})

)

select
    pickup_date_id,
    pickup_time_id,
    dropoff_date_id,
    dropoff_time_id,
    vendor_id,
    payment_type_id,
    rate_code_id,
    pickup_longitude,
    pickup_latitude,
    dropoff_longitude,
    dropoff_latitude,
    passenger_count,
    trip_distance,
    trip_duration_min,
    fare_amount,
    extra,
    mta_tax,
    tip_amount,
    tolls_amount,
    improvement_surcharge,
    total_amount
from filtered
