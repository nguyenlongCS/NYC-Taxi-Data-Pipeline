{#
    Staging layer — chỉ rename/cast cho khớp quy ước đặt tên của star schema
    hiện có (đặc biệt payment_type -> payment_type_id, khớp
    dwh.dim_payment_type.payment_type_id).

    CHỦ ĐÍCH: KHÔNG áp 5 điều kiện lọc dữ liệu bẩn ở đây (trip_distance,
    fare_amount, passenger_count, tọa độ NYC, dropoff > pickup — xem
    docs/notes.md mục 1). Việc lọc thuộc về marts.fact_trips, để giữ đúng
    convention dbt: staging phản ánh đúng dữ liệu nguồn (chỉ đổi tên/kiểu),
    business rule (lọc sạch) đặt ở layer gần fact/dim hơn.
#}

with source as (

    select * from {{ source('staging', 'yellow_trips') }}

),

renamed as (

    select
        vendor_id,
        tpep_pickup_datetime,
        tpep_dropoff_datetime,
        passenger_count,
        trip_distance,
        pickup_longitude,
        pickup_latitude,
        rate_code_id,
        store_and_fwd_flag,
        dropoff_longitude,
        dropoff_latitude,
        payment_type as payment_type_id,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        improvement_surcharge,
        total_amount

    from source

)

select * from renamed
