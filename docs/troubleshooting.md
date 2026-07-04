# Troubleshooting — Các lỗi đã gặp và cách xử lý

Tổng hợp toàn bộ sự cố thực tế trong quá trình triển khai, kèm nguyên nhân gốc rễ và cách khắc phục — không chỉ để tự tra cứu lại mà còn là bằng chứng cho thấy quá trình debug có hệ thống (điểm cộng cho portfolio).

---

## 1. Lỗi: `cannot truncate a table referenced in a foreign key constraint`

**Log lỗi:**
```
ERROR:  cannot truncate a table referenced in a foreign key constraint
DETAIL:  Table "fact_trips" references "dim_date".
HINT:  Truncate table "fact_trips" at the same time, or use TRUNCATE ... CASCADE.
```

**Nguyên nhân:** PostgreSQL từ chối `TRUNCATE` một bảng (`dim_date`) đang bị bảng khác (`fact_trips`) tham chiếu qua khóa ngoại (FK) — **bất kể** bảng tham chiếu đó hiện có dữ liệu hay không.

**Sai lầm ban đầu:** tưởng chỉ cần đổi thứ tự (`TRUNCATE fact_trips` trước, `TRUNCATE dim_date` sau) là đủ — **không đúng**, ràng buộc FK vẫn chặn dù bảng con đã rỗng.

**Cách xử lý đúng:** liệt kê tất cả bảng liên quan trong **cùng một câu lệnh**:
```sql
TRUNCATE dwh.fact_trips, dwh.dim_date, dwh.dim_time;
```

---

## 2. Lỗi: `duplicate key value violates unique constraint`

**Log lỗi:**
```
ERROR:  duplicate key value violates unique constraint "dim_date_pkey"
DETAIL:  Key (date_id)=(20150207) already exists.
```

**Nguyên nhân:** hệ quả trực tiếp của lỗi #1 — vì câu `TRUNCATE dim_date` bị chặn (không thực sự dọn bảng), câu `INSERT` chạy ngay sau đó cố ghi lại dữ liệu đã tồn tại → đụng khóa chính.

**Cách xử lý:** cùng cách với lỗi #1 — dùng `TRUNCATE` gộp nhiều bảng. Sau khi sửa, script trở nên **idempotent** (chạy lại bao nhiêu lần cũng an toàn).

---

## 3. Lỗi: 2 session ghi đè lên nhau (race condition)

**Triệu chứng:** chạy script đã sửa đúng nhưng vẫn ra lỗi FK/duplicate key như trên, dù script không còn bug logic.

**Nguyên nhân thật sự:** mở 2 cửa sổ terminal, terminal 1 đang chạy script cũ (`INSERT INTO fact_trips`, 25+ phút chưa xong), terminal 2 chạy script mới đè lên cùng lúc → 2 session tranh chấp khóa (lock) trên cùng bảng.

**Cách phát hiện:** kiểm tra query đang active trước khi thao tác:
```sql
SELECT pid, state, now() - query_start AS running_time, LEFT(query, 60) AS query_preview
FROM pg_stat_activity
WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%';
```

**Cách xử lý:** hủy sạch session cũ trước khi chạy lại:
```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname='taxi_dwh' AND pid <> pg_backend_pid();
```

**Quy tắc phòng tránh:** câu lệnh `SELECT` (đọc) luôn an toàn để chạy song song ở nhiều terminal; câu lệnh ghi (`TRUNCATE`/`INSERT`/`UPDATE`/`COPY`) vào cùng bảng thì chỉ được chạy ở **1 nơi tại 1 thời điểm**.

---

## 4. Lỗi: `The '<' operator is reserved for future use` (PowerShell)

**Log lỗi:**
```
docker exec -i taxi_postgres psql -U taxi_user -d taxi_dwh < sql/02_transform_load.sql
At line:1 char:60
+ ... < sql/02_t ...
+                ~
The '<' operator is reserved for future use.
```

**Nguyên nhân:** toán tử redirect `<` (cú pháp bash/cmd quen thuộc) **không được PowerShell hỗ trợ**.

**Cách xử lý:** dùng pipe với `Get-Content`:
```powershell
Get-Content sql/02_transform_load.sql | docker exec -i taxi_postgres psql -U taxi_user -d taxi_dwh
```

---

## 5. Rủi ro: mất dashboard/cấu hình khi container bị xóa

**Triệu chứng:** không phải lỗi hiện tại, mà là rủi ro phát hiện trước khi xảy ra — hỏi "các câu SQL chạy trên Metabase có lưu vào project không?".

**Nguyên nhân:** `docker-compose.yml` ban đầu chỉ khai `volumes:` cho service `postgres` (`pgdata`), chưa khai cho `metabase` và `pgadmin`. Dữ liệu ứng dụng của 2 service này (dashboard đã lưu, cấu hình server connection) nằm trong filesystem của container — mất hoàn toàn nếu container bị xóa/recreate mà không có volume backing.

**Cách xử lý:** thêm named volume cho từng service:
```yaml
metabase:
  volumes:
    - metabase_data:/metabase-data
  environment:
    MB_DB_FILE: /metabase-data/metabase.db

pgadmin:
  volumes:
    - pgadmin_data:/var/lib/pgadmin

volumes:
  pgdata:
  metabase_data:
  pgadmin_data:
```
Áp dụng bằng `docker compose down` rồi `docker compose up -d`. **Đánh đổi:** vì đây là volume mới, cấu hình cũ (câu hỏi đã lưu, tài khoản admin) bị mất 1 lần — cần setup lại, nhưng từ đó về sau sẽ được giữ nguyên qua các lần restart.

**Bài học tổng quát:** những gì lưu **trong** Metabase (qua nút "Lưu" trên UI) không tự động xuất hiện trong git repo. Cách đúng để version-control các câu phân tích: copy SQL ra thành file `.sql` riêng trong `sql/analytics/`.

---

## 6. Rủi ro: volume ẩn danh với tên hash ngẫu nhiên

**Triệu chứng:** thấy 1 volume lạ tên `75d4c6db52baa86731c50f8ea853f66993c6045d9f942346858903b3...` trong Docker Desktop, không rõ dùng để làm gì.

**Nguyên nhân:** image `dpage/pgadmin4` có khai báo sẵn 1 thư mục `VOLUME` nội bộ (`/var/lib/pgadmin`) trong Dockerfile gốc của nó. Khi `docker-compose.yml` không chỉ định tên volume tường minh cho đường dẫn đó, Docker tự tạo 1 volume ẩn danh với tên là chuỗi hash ngẫu nhiên.

**Cách xác nhận:** trong Docker Desktop → tab Volumes, cột trạng thái bên trái tên volume — chấm rỗng (◯) nghĩa là không còn container nào dùng (an toàn để xóa); chấm xanh đặc (●) nghĩa là đang được dùng.

**Cách xử lý:**
1. Không thể "đổi tên" volume trực tiếp (Docker không hỗ trợ).
2. Sửa `docker-compose.yml` thêm named volume tường minh (xem mục #5) → `docker compose down && docker compose up -d` → từ giờ dùng volume tên rõ ràng thay vì hash.
3. Dọn volume hash cũ (đã orphan) bằng `docker volume prune` — lệnh này chỉ xóa volume không còn container nào tham chiếu, an toàn với dữ liệu đang dùng.

---

## 7. Vấn đề UX: chart nhiều trục Y gây rối trong Metabase

**Triệu chứng:** dashboard hiển thị được nhưng 4/5 chart nhìn rối — nhiều đường/cột chồng lên nhau với các thang đo (trục Y) khác nhau, khó đọc.

**Nguyên nhân:** khi câu SQL trả về nhiều cột số liệu (ví dụ vừa `so_chuyen`, vừa `doanh_thu_tb`, vừa `tong_doanh_thu`), Metabase mặc định vẽ **tất cả** các cột đó lên cùng 1 chart, mỗi cột 1 trục Y riêng.

**Cách xử lý:** mở lại câu hỏi → **Trực quan hóa → Cài đặt (gear icon) → tab Dữ liệu** → tắt bớt series, chỉ giữ 1 metric chính mỗi chart (ví dụ chart "Doanh thu theo giờ" chỉ giữ `tong_doanh_thu`, bỏ các cột phụ). Muốn xem nhiều metric cùng lúc thì tách thành nhiều chart riêng thay vì nhồi vào 1 chart.

---

## 8. Lỗi: dbt crash với `mashumaro.exceptions.UnserializableField` trên Python 3.14

**Log lỗi:**
```
mashumaro.exceptions.UnserializableField: Field "schema" of type Optional[str]
in JSONObjectSchema is not serializable
```

**Nguyên nhân:** dbt-core (qua thư viện phụ thuộc `mashumaro`) chưa hỗ trợ Python 3.14 tại thời điểm triển khai (dbt chính thức hỗ trợ tới Python 3.13). Máy dùng Python 3.14 làm mặc định nên `dbt debug`/`dbt run` crash ngay từ bước import.

**Cách xử lý:** tạo virtual environment riêng cho dbt bằng Python 3.12, tách biệt hoàn toàn với Python hệ thống dùng cho `load_staging.py`:
```powershell
py -3.12 -m venv .venv-dbt
```
Chi tiết đầy đủ tại [`dbt/README.md`](../dbt/README.md).

---

## 9. Lỗi: PowerShell chặn `Activate.ps1` (`UnauthorizedAccess`/`PSSecurityException`)

**Log lỗi:**
```
File ...\.venv-dbt\Scripts\Activate.ps1 cannot be loaded because running scripts
is disabled on this system.
```

**Nguyên nhân:** Windows PowerShell mặc định chặn chạy file `.ps1` (Execution Policy `Restricted`) — không liên quan tới dbt hay venv, ai mới dùng PowerShell + Python venv cũng gặp.

**Cách xử lý:** nới lỏng chỉ cho phiên terminal hiện tại (an toàn, tự reset khi đóng terminal):
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.venv-dbt\Scripts\Activate.ps1
```
Hoặc đổi policy mức user (chỉ 1 lần, không cần admin):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## 10. Lỗi: `UnicodeDecodeError: 'charmap' codec can't decode byte...` khi chạy dbt

**Log lỗi:**
```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x8d in position 534:
character maps to <undefined>
```

**Nguyên nhân:** Python trên Windows mặc định đọc file bằng codepage hệ thống (`cp1252`) thay vì UTF-8. Các file `.sql`/`.yml` trong `dbt/` có comment tiếng Việt có dấu → dbt crash khi quét project.

**Cách xử lý:** set biến môi trường UTF-8 mode trước khi chạy bất kỳ lệnh `dbt` nào (mỗi phiên terminal mới phải set lại):
```powershell
$env:PYTHONUTF8 = "1"
```

---

## 11. Lỗi: `dbt seed` báo lại đúng lỗi TRUNCATE-FK (giống mục #1) khi build lần đầu

**Log lỗi:**
```
Database Error in seed dim_payment_type (seeds\dim_payment_type.csv)
  cannot truncate a table referenced in a foreign key constraint
  DETAIL:  Table "fact_trips" references "dim_payment_type".
```

**Nguyên nhân:** `dbt seed` mặc định dùng chiến lược `TRUNCATE` rồi `INSERT` lại. Bảng `dwh.fact_trips` **CŨ** (do `sql/01_create_schema.sql`/`sql/02_transform_load.sql` gốc tạo, có `REFERENCES` cứng tới `dim_vendor`/`dim_payment_type`/`dim_rate_code`) vẫn còn tồn tại trong DB tại thời điểm chuyển sang dbt-managed schema — seed trùng tên bảng với 3 dimension đó nên bị chặn TRUNCATE, đúng cơ chế ở mục #1.

**Cách xử lý:** đây là bước "bàn giao" 1 lần duy nhất khi chuyển từ pipeline SQL thủ công sang dbt — xóa bảng `fact_trips` cũ để gỡ luôn 3 FK đang chặn (đã đối chiếu số liệu khớp 100% trước khi xóa, xem `docs/checklist.md`):
```powershell
docker exec -it taxi_postgres psql -U taxi_user -d taxi_dwh -c "DROP TABLE dwh.fact_trips;"
```
Sau đó `dbt build` lại — không cần lặp lại bước này về sau vì `dim_date`/`dim_time`/`fact_trips` từ giờ hoàn toàn do dbt quản lý (materialize bằng create-and-replace, không TRUNCATE).

---

## 12. Lỗi: `bitnami/spark:3.5` không pull được — "not found"

**Log lỗi:**
```
docker compose up -d
✘ Image bitnami/spark:3.5 Error failed to resolve reference "docker.io/bitnami/spark:3.5": docker.io/bitnami/spar... not found
```

**Nguyên nhân:** Bitnami đổi mô hình phát hành từ giữa 2025 — kho `bitnami/*` công khai trên Docker Hub (bao gồm `bitnami/spark`) **không còn tag miễn phí nào** nữa; bản đầy đủ chỉ dành cho khách hàng trả phí "Bitnami Secure Images". Repo `bitnamilegacy/spark` (image cũ được giữ tạm) chỉ còn tag dạng hash (`sha256-...`), không ổn định để dùng lâu dài trong `docker-compose.yml`.

**Cách xử lý:** chuyển sang **Docker Official Image `spark`** (tag `python3`), do cộng đồng Docker phối hợp Apache Spark duy trì trực tiếp, có sẵn PySpark, cập nhật thường xuyên:
```yaml
spark:
  image: spark:python3
```

**Bài học tổng quát:** không nên giả định tag ngắn (`:3.5`, `:latest`) của các image bên thứ ba (đặc biệt Bitnami) sẽ luôn tồn tại — cần kiểm tra Docker Hub trước khi đưa vào `docker-compose.yml`, ưu tiên Docker Official Images khi có lựa chọn tương đương.

---

## 13. Lỗi: `OutOfMemoryError: Java heap space` khi chạy Spark job trên 22 triệu dòng

**Log lỗi:**
```
java.lang.OutOfMemoryError: Java heap space
        at org.apache.spark.unsafe.types.UTF8String.fromAddress(UTF8String.java:177)
        ...
py4j.protocol.Py4JJavaError: An error occurred while calling o269.count.
: org.apache.spark.SparkException: Job 0 cancelled because SparkContext was shut down
```

**Nguyên nhân:** bản đầu tiên của `spark_jobs/clean_taxi_data.py` gọi `.cache()` trên **cả hai** DataFrame (`raw_df` và `clean_df` — mỗi bản 22,288,907 dòng × 19 cột), sau đó kiểm tra dữ liệu bị hỏng khi ép kiểu bằng vòng lặp thủ công: 14 cột × 2 lần `.count()` = 28 job Spark riêng biệt, mỗi job cố tái sử dụng cache. Container Spark chạy `local[*]` với bộ nhớ JVM mặc định chỉ ~1GB (`ResourceProfile: memory amount 1024`) — không đủ để giữ đồng thời 2 bản đầy đủ dữ liệu trong RAM.

**Sự cố phụ liên quan (không phải lỗi, nhưng cần biết trước):** image `spark:python3` chạy **Spark 4.1.2** (không phải 3.5.x như dự tính ban đầu khi còn định dùng `bitnami/spark`). Spark 4.x đổi mặc định `spark.sql.ansi.enabled` từ `false` sang `true` — với ANSI bật, một giá trị cast lỗi (vd. chuỗi không phải số ép sang `int`) sẽ làm job **crash ngay lập tức** với exception thô, thay vì trả về `NULL` như hành vi Spark 3.x. Điều này phá vỡ đúng thiết kế "cast lỗi → NULL → tự đếm để báo cáo" ban đầu của script.

**Cách xử lý (2 phần):**
1. **Tắt ANSI mode** để khôi phục hành vi "cast lỗi → NULL" (khớp thiết kế kiểm tra dữ liệu của script):
   ```python
   SparkSession.builder.config("spark.sql.ansi.enabled", "false")
   ```
2. **Viết lại logic kiểm tra để chỉ quét dữ liệu 1 lần** thay vì 28 lần: gộp toàn bộ việc ép kiểu + tính cờ "dữ liệu có bị mất khi cast không" vào **1 lượt `.select()`**, rồi tính hết checksum + đếm dòng lỗi trong **1 lượt `.agg()`** duy nhất. Đồng thời **bỏ hẳn `.cache()`** — đổi lại, dữ liệu được đọc lại từ CSV 2 lần (1 lần kiểm tra, 1 lần ghi Parquet) thay vì tái dùng cache, chậm hơn một chút nhưng không phụ thuộc vào cấu hình RAM của container.

**Bài học tổng quát:** với dữ liệu lớn (chục triệu dòng) chạy trên Spark local mode có giới hạn RAM, ưu tiên thiết kế **ít lượt quét dữ liệu nhất có thể** (gộp nhiều phép tính vào 1 `.agg()`) thay vì gọi `.cache()` rồi lặp nhiều action riêng lẻ — `.cache()` chỉ thực sự lợi khi bộ nhớ đủ lớn để giữ toàn bộ dữ liệu, ngược lại có thể phản tác dụng nặng nề như trường hợp này.

---

## Bảng tổng hợp nhanh

| # | Lỗi/Vấn đề | Nguyên nhân gốc | Fix chính |
|---|---|---|---|
| 1 | TRUNCATE bị chặn bởi FK | Postgres luôn chặn TRUNCATE bảng bị tham chiếu, bất kể data | Gộp TRUNCATE nhiều bảng trong 1 câu lệnh |
| 2 | Duplicate key khi INSERT | Hệ quả của lỗi #1 (TRUNCATE không thực sự chạy) | Cùng fix với #1 |
| 3 | Lock contention giữa 2 session | Chạy 2 lệnh ghi song song vào cùng bảng | Chỉ 1 session ghi tại 1 thời điểm; SELECT thì luôn an toàn song song |
| 4 | PowerShell không hiểu `<` | Cú pháp bash không tương thích PowerShell | Dùng `Get-Content \| pipe` |
| 5 | Mất dashboard Metabase khi restart container | Thiếu named volume trong docker-compose.yml | Thêm `volumes:` tường minh cho từng service |
| 6 | Volume tên hash lạ | Docker tự tạo anonymous volume khi image có VOLUME nội bộ chưa được map tên | Thêm named volume, prune volume cũ |
| 7 | Chart rối nhiều trục Y | Metabase tự vẽ hết các cột SQL trả về lên 1 chart | Chỉ giữ 1 metric chính mỗi chart trong phần Cài đặt |
| 8 | dbt crash `UnserializableField` | Python 3.14 chưa được dbt-core/mashumaro hỗ trợ | venv riêng với Python 3.12 |
| 9 | PowerShell chặn `Activate.ps1` | Execution Policy mặc định `Restricted` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| 10 | `UnicodeDecodeError` khi chạy dbt | Windows đọc file bằng `cp1252` thay vì UTF-8 | `$env:PYTHONUTF8 = "1"` trước khi chạy dbt |
| 11 | `dbt seed` bị lỗi TRUNCATE-FK | Bảng `fact_trips` cũ (có FK cứng) chưa được dọn khi chuyển sang dbt | `DROP TABLE dwh.fact_trips` (chỉ 1 lần khi bàn giao) |
| 12 | `bitnami/spark:3.5` không pull được | Bitnami ngừng phát hành tag miễn phí từ giữa 2025 | Đổi sang Docker Official Image `spark:python3` |
| 13 | Spark job OOM (`Java heap space`) | `.cache()` 2 bản đầy đủ 22M dòng + 28 lượt `.count()` riêng lẻ, RAM container ~1GB | Gộp thành 1 lượt `.agg()`, bỏ `.cache()`; tắt ANSI mode (Spark 4.x) để cast lỗi trả NULL thay vì crash |
