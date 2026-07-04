{#
    Marts — dim_time. 1440 dòng cố định (mỗi phút trong ngày, 0-1439),
    dùng chung cho cả pickup và dropoff (role-playing dimension). Không
    phụ thuộc dữ liệu nguồn — y hệt logic gốc trong sql/02_transform_load.sql.
#}

with minutes as (

    select generate_series(0, 1439) as m

)

select
    m                                                            as time_id,
    (m / 60)::smallint                                            as hour,
    (m % 60)::smallint                                             as minute,
    case
        when (m / 60) between 5 and 8   then 'Sáng sớm'
        when (m / 60) between 9 and 11  then 'Sáng'
        when (m / 60) between 12 and 13 then 'Trưa'
        when (m / 60) between 14 and 17 then 'Chiều'
        when (m / 60) between 18 and 21 then 'Tối'
        else 'Đêm khuya'
    end                                                             as time_period,
    (m / 60) in (7, 8, 9, 16, 17, 18, 19)                             as is_rush_hour
from minutes
