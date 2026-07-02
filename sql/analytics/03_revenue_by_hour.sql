-- ============================================================
-- 03_revenue_by_hour.sql
-- Dashboard: Doanh thu theo giờ trong ngày
-- Trả lời câu hỏi: khung giờ nào trong ngày có nhiều chuyến /
-- doanh thu cao nhất? Giờ nào vắng khách?
-- ============================================================

SELECT
    t.hour AS gio_trong_ngay,
    COUNT(*) AS so_chuyen,
    ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb,
    ROUND(SUM(f.total_amount), 0) AS tong_doanh_thu
FROM dwh.fact_trips f
JOIN dwh.dim_time t ON f.pickup_time_id = t.time_id
GROUP BY t.hour
ORDER BY t.hour;
