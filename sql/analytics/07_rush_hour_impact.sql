-- ============================================================
-- 07_rush_hour_impact.sql
-- Dashboard: Ảnh hưởng của giờ cao điểm (Rush Hour Impact)
-- Trả lời câu hỏi: chuyến đi vào giờ cao điểm có mất nhiều thời
-- gian hơn hẳn không, dù quãng đường tương đương? Ảnh hưởng đến
-- doanh thu/km ra sao (giá theo đồng hồ tính giờ chờ tắc đường)?
-- ============================================================

SELECT
    t.is_rush_hour,
    COUNT(*) AS so_chuyen,
    ROUND(AVG(f.trip_distance), 2) AS quang_duong_tb_dam,
    ROUND(AVG(f.trip_duration_min), 2) AS thoi_gian_tb_phut,
    -- tốc độ trung bình (dặm/phút) - càng thấp nghĩa là càng tắc đường
    ROUND(AVG(f.trip_distance) / NULLIF(AVG(f.trip_duration_min), 0), 3) AS toc_do_tb_dam_moi_phut,
    ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb
FROM dwh.fact_trips f
JOIN dwh.dim_time t ON f.pickup_time_id = t.time_id
WHERE f.trip_duration_min > 0 AND f.trip_duration_min < 180  -- loại chuyến bất thường (>3 tiếng)
GROUP BY t.is_rush_hour
ORDER BY t.is_rush_hour DESC;
