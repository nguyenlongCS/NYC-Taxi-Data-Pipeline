-- ============================================================
-- 04_trend_by_weekday.sql
-- Dashboard: Xu hướng theo ngày trong tuần
-- Trả lời câu hỏi: ngày nào trong tuần đông khách nhất? Weekend
-- có khác biệt rõ rệt so với ngày thường không?
-- ============================================================

SELECT
    d.day_of_week,
    TRIM(d.day_name) AS ten_ngay,
    d.is_weekend,
    COUNT(*) AS so_chuyen,
    ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb,
    ROUND(AVG(f.tip_amount), 2) AS tip_tb
FROM dwh.fact_trips f
JOIN dwh.dim_date d ON f.pickup_date_id = d.date_id
GROUP BY d.day_of_week, d.day_name, d.is_weekend
ORDER BY d.day_of_week;
