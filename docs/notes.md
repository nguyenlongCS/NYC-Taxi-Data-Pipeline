# Notes — Kiến thức cần nhớ

Tổng hợp các quyết định thiết kế và bài học thực chiến rút ra trong quá trình xây dựng pipeline. Mục tiêu: để người đọc sau (hoặc chính bạn 6 tháng sau) hiểu **vì sao** mọi thứ được làm như vậy, không chỉ **làm cái gì**.

## 1. Thiết kế dimension theo dữ liệu thực tế

- **`dim_date`** — sinh tự động theo đúng khoảng ngày thực tế có trong dữ liệu (`generate_series` dựa trên `MIN`/`MAX` của cả pickup lẫn dropoff), không hardcode khoảng ngày. Tránh thiếu ngày nếu chuyến cuối tháng dropoff sang ngày/tháng kế tiếp.
- **`dim_time`** — 1440 dòng cố định (mỗi phút trong ngày, từ 0 đến 1439), dùng chung cho cả pickup và dropoff. Không cần sinh lại theo dữ liệu vì đây là tập giá trị hữu hạn, không đổi.
- **`fact_trips`** — nạp từ staging kèm 5 điều kiện làm sạch dữ liệu phổ biến với taxi data:
  1. `trip_distance` dương và < 100 dặm (loại outlier)
  2. `fare_amount` dương
  3. `passenger_count` > 0
  4. Tọa độ nằm trong phạm vi hợp lý của NYC (loại các điểm GPS lỗi ghi nhận là 0,0)
  5. `dropoff` phải sau `pickup`

  Kết quả: 22,288,907 dòng staging → 21,792,952 dòng fact_trips (**lọc bỏ ~495,955 dòng, ~2.2%**) — đây là con số nên đưa vào README, thể hiện có kiểm soát chất lượng dữ liệu chứ không nạp thô.

## 2. Bài học về PostgreSQL — TRUNCATE và Foreign Key

**Sai lầm ban đầu:** nghĩ rằng chỉ cần đổi *thứ tự* TRUNCATE (dọn bảng con `fact_trips` trước, bảng cha `dim_date`/`dim_time` sau) là đủ để tránh lỗi FK.

**Thực tế:** PostgreSQL luôn từ chối `TRUNCATE` một bảng đang bị bảng khác tham chiếu FK — **bất kể** bảng tham chiếu đó có dữ liệu hay không, và bất kể thứ tự chạy trước/sau. Cách đúng duy nhất: liệt kê **tất cả** các bảng liên quan trong **cùng một câu lệnh**:

```sql
TRUNCATE dwh.fact_trips, dwh.dim_date, dwh.dim_time;
```

(Hoặc dùng `TRUNCATE ... CASCADE` nếu chỉ muốn gọi trên 1 bảng cha, chấp nhận xóa luôn dữ liệu liên quan ở bảng con.)

## 3. Bài học về chạy lệnh song song (concurrency)

Chạy 2 script cùng ghi vào cùng 1 bảng ở 2 terminal khác nhau → tranh chấp khóa (lock) → lỗi domino khó hiểu (FK error, duplicate key error) dù bản thân từng script không có lỗi logic.

**Quy tắc phân biệt:**
| Loại lệnh | Chạy song song được không? |
|---|---|
| `SELECT`, `pg_stat_activity`, xem cấu trúc bảng | ✅ An toàn, chạy bao nhiêu terminal cũng được |
| `TRUNCATE`, `INSERT`, `UPDATE`, `DELETE`, `COPY` vào cùng bảng | ❌ Chỉ chạy 1 nơi tại 1 thời điểm |

Cách kiểm tra có query nào đang chạy trước khi bắt đầu thao tác ghi mới:
```sql
SELECT pid, state, now() - query_start AS running_time, LEFT(query, 60) AS query_preview
FROM pg_stat_activity
WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%';
```

Cách hủy sạch session đang treo nếu cần reset:
```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname='taxi_dwh' AND pid <> pg_backend_pid();
```

## 4. Bài học về PowerShell

Toán tử redirect `<` (dùng để nạp file SQL kiểu `psql < file.sql`) **không được hỗ trợ trên PowerShell** (chỉ hoạt động trên bash/cmd). Thay thế bằng pipe:

```powershell
Get-Content sql/02_transform_load.sql | docker exec -i taxi_postgres psql -U taxi_user -d taxi_dwh
```

## 5. Bài học về Docker Volumes

- **Dữ liệu lưu trong container sẽ mất khi container bị xóa/recreate**, trừ khi có khai báo `volumes:` tường minh trong `docker-compose.yml`. Ban đầu chỉ khai `pgdata` cho Postgres, quên mất Metabase và pgAdmin cũng cần volume riêng để giữ dashboard/cấu hình qua các lần `docker compose down/up`.
- **Volume ẩn danh (anonymous volume)**: nếu image có khai báo `VOLUME` nội bộ (ví dụ `dpage/pgadmin4` có `/var/lib/pgadmin`) mà bạn không chỉ định tên volume trong `docker-compose.yml`, Docker tự tạo 1 volume với **tên hash ngẫu nhiên**. Không đổi tên được — chỉ có thể sửa `docker-compose.yml` để khai named volume tường minh, rồi `down`/`up` lại (mất cấu hình cũ, cần setup lại từ đầu).
- Dọn volume rác (không container nào dùng) an toàn bằng: `docker volume prune` — lệnh này **không** đụng đến volume đang được container sử dụng.

## 6. Bài học về Metabase

- Câu hỏi (Question)/Dashboard tạo trong Metabase được lưu vào **database nội bộ của chính Metabase**, hoàn toàn tách biệt với database `taxi_dwh` (nơi chứa dữ liệu taxi) và tách biệt với project repo trên máy/GitHub. → Cần lưu song song các câu SQL thành file `.sql` trong `sql/analytics/` để version control và làm bằng chứng cho portfolio.
- Khi viết SQL trả về nhiều cột số liệu (ví dụ vừa `so_chuyen` vừa `doanh_thu_tb` vừa `tong_doanh_thu`), Metabase mặc định vẽ **tất cả** các cột đó lên cùng 1 chart với nhiều trục Y khác nhau → rối, khó đọc. Cách sửa: vào phần **Cài đặt (gear icon) → Dữ liệu**, tắt bớt series, **chỉ giữ lại 1 metric chính mỗi chart**. Muốn xem nhiều metric thì tách thành nhiều chart riêng thay vì nhồi vào 1 chart.
- Khi add database connection trong Metabase, dùng **tên service trong `docker-compose.yml`** (`postgres`) làm Host, **không phải** `localhost` — vì Metabase gọi qua network nội bộ Docker, không qua cổng đã map ra ngoài máy host.