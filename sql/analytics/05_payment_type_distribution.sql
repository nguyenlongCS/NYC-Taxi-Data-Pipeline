-- ============================================================
-- 05_payment_type_distribution.sql
-- Dashboard: Phân bố hình thức thanh toán
-- Trả lời câu hỏi: khách hàng chủ yếu thanh toán bằng thẻ hay
-- tiền mặt? Tỷ lệ tip có khác nhau giữa các hình thức không?
-- ============================================================

SELECT
    p.payment_name AS hinh_thuc_thanh_toan,
    COUNT(*) AS so_chuyen,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS ty_le_phan_tram,
    ROUND(AVG(f.total_amount), 2) AS doanh_thu_tb,
    ROUND(AVG(f.tip_amount), 2) AS tip_tb
FROM dwh.fact_trips f
JOIN dwh.dim_payment_type p ON f.payment_type_id = p.payment_type_id
GROUP BY p.payment_name
ORDER BY so_chuyen DESC;
