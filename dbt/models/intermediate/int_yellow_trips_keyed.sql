{#
    Intermediate layer — tính surrogate key theo thời gian (date_id, time_id)
    cho cả pickup và dropoff, dùng ĐÚNG công thức trong 02_transform_load.sql
    gốc, để khớp với dwh.dim_date/dwh.dim_time sẽ dựng ở bước marts
    (role-playing dimension — xem docs/data_dictionary.md phần "Sơ đồ quan hệ").

    Cũng tính sẵn trip_duration_min ở đây (phút, từ dropoff - pickup) vì đây
    là cột suy ra (computed), không phải measure gốc từ nguồn.

    Vẫn CHƯA lọc dữ liệu bẩn ở layer này — lọc dữ liệu là việc của
    marts.fact_trips (bước 4), theo đúng convention: intermediate chỉ biến
    đổi/tính toán, business rule (giữ/loại dòng nào) đặt gần fact nhất.
#}

with trips as (

    select * from {{ ref('stg_yellow_trips') }}

),

keyed as (

    select
        -- surrogate key thời gian, khớp định dạng dwh.dim_date.date_id / dwh.dim_time.time_id
        to_char(tpep_pickup_datetime, 'YYYYMMDD')::integer as pickup_date_id,
        (extract(hour from tpep_pickup_datetime) * 60
            + extract(minute from tpep_pickup_datetime))::integer as pickup_time_id,
        to_char(tpep_dropoff_datetime, 'YYYYMMDD')::integer as dropoff_date_id,
        (extract(hour from tpep_dropoff_datetime) * 60
            + extract(minute from tpep_dropoff_datetime))::integer as dropoff_time_id,

        -- thời lượng chuyến đi (phút), tính từ dropoff - pickup
        extract(epoch from (tpep_dropoff_datetime - tpep_pickup_datetime)) / 60.0
            as trip_duration_min,

        -- giữ nguyên toàn bộ cột còn lại từ staging
        vendor_id,
        payment_type_id,
        rate_code_id,
        tpep_pickup_datetime,
        tpep_dropoff_datetime,
        pickup_longitude,
        pickup_latitude,
        dropoff_longitude,
        dropoff_latitude,
        passenger_count,
        trip_distance,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        improvement_surcharge,
        total_amount

    from trips

)

select * from keyed
