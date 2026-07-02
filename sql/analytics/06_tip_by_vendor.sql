-- ============================================================
-- 06_tip_by_vendor.sql
-- Dashboard: Tip trung bình theo vendor
-- Trả lời câu hỏi: khách đi xe của vendor nào cho tip cao hơn?
-- Có khác biệt về chất lượng dịch vụ giữa 2 vendor không?
-- ============================================================

SELECT
    v.vendor_name,
    COUNT(*) AS so_chuyen,
    ROUND(AVG(f.tip_amount), 2) AS tip_tb,
    ROUND(AVG(f.trip_distance), 2) AS quang_duong_tb,
    ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb,
    -- tỷ lệ tip trên tổng tiền, phản ánh "mức độ hào phóng" tương đối
    ROUND(100.0 * AVG(f.tip_amount) / NULLIF(AVG(f.total_amount), 0), 2) AS ty_le_tip_phan_tram
FROM dwh.fact_trips f
JOIN dwh.dim_vendor v ON f.vendor_id = v.vendor_id
GROUP BY v.vendor_name
ORDER BY tip_tb DESC;
