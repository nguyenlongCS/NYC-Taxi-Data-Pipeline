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

## 14. Lỗi: BuildKit `failed to commit ... snapshot does not exist` khi build image Airflow

**Log lỗi:**
```
#16 ERROR: failed to commit 8rbueiqdwb0mbd91qwn6lp5fu to vqptgmeirso1k4blp7xkyhwyx during finalize:
failed to stat active key during commit: snapshot 8rbueiqdwb0mbd91qwn6lp5fu does not exist: not found
```

**Nguyên nhân:** lỗi hạ tầng của chính containerd snapshotter trong Docker Desktop (không liên quan tới nội dung Dockerfile) — xảy ra ngay cả khi build **từng image một, không song song**, và lặp lại y hệt ở image `apache/airflow:2.10.5-python3.12` (image gốc nhiều layer, dung lượng lớn).

**Cách xử lý:**
1. Dọn cache build hỏng: `docker builder prune -af`
2. Nếu vẫn lỗi: tắt tính năng thử nghiệm **Docker Desktop → Settings → General → "Use containerd for pulling and storing images"**, Apply & restart, build lại.
3. Nếu vẫn lỗi: build bằng legacy builder — `$env:DOCKER_BUILDKIT = "0"` trước khi `docker compose build`.

**Bài học tổng quát:** khi lỗi build không đổi dù build lẻ từng image, không phải lỗi Dockerfile — nghi ngay containerd/BuildKit của Docker Desktop, thử dọn cache trước khi sửa code.

---

## 15. Lỗi: `KeyError: 'HOST_PROJECT_DIR'` khi `airflow-init` kiểm tra DAG import

**Log lỗi:**
```
File "/opt/airflow/dags/taxi_pipeline_dag.py", line 38, in <module>
    HOST_PROJECT_DIR = os.environ["HOST_PROJECT_DIR"]
KeyError: 'HOST_PROJECT_DIR'
```

**Nguyên nhân:** DAG cần biến `HOST_PROJECT_DIR` ngay lúc **import module** (để lắp đường dẫn mount cho `DockerOperator`). Biến này chỉ được khai trong phần `environment:` của service `airflow-scheduler`, **quên khai thêm** cho `airflow-init` — mà bước "kiểm tra DAG import" (`airflow dags list-import-errors`) lại chạy ngay trong chính container `airflow-init`.

**Cách xử lý:** thêm `HOST_PROJECT_DIR` (và `TAXI_DOCKER_NETWORK`) vào `environment:` của **cả** service `airflow-init` lẫn `airflow-scheduler`, không chỉ 1 trong 2.

**Bài học tổng quát:** bất kỳ container nào có bước "parse/import DAG" (kể cả container init chỉ chạy 1 lần) đều cần đủ biến môi trường mà DAG đọc lúc import — không chỉ container thực thi task.

---

## 16. Lỗi: `could not translate host name "postgres" to address` sau khi chỉ `up` một phần service

**Log lỗi:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not translate host name "postgres"
to address: Temporary failure in name resolution
```

**Nguyên nhân:** chạy `docker compose up -d airflow-scheduler airflow-webserver` (chỉ định đích danh 2 service) sau khi đã thêm cấu hình `networks: taxi_net` mới vào file — Compose **không tự "recreate"** container `postgres` đang chạy sẵn dù cấu hình của nó đã đổi, nên nó vẫn nằm trong network cũ, còn 2 container Airflow (mới tạo) join network mới → 2 bên không cùng network, không phân giải được tên nhau.

**Cách xử lý:**
```powershell
docker compose down      # KHÔNG thêm -v, để giữ nguyên volume pgdata
docker compose up -d     # tạo lại toàn bộ container theo đúng cấu hình mới nhất
```
Xác nhận lại bằng `docker network inspect taxi_net` — phải thấy đủ tất cả container liên quan trong cùng 1 network.

**Bài học tổng quát:** sau khi đổi cấu hình `networks:`/`volumes:` cấp service trong `docker-compose.yml`, `up -d` chỉ đích danh vài service **không đủ** để áp dụng thay đổi cho các service khác đang chạy sẵn — cần `down` (không `-v`) rồi `up -d` lại toàn bộ.

---

## 17. Lỗi: `DockerContainerFailedException: Docker container failed: {'StatusCode': 137}` (OOM)

**Log lỗi:**
```
airflow.providers.docker.exceptions.DockerContainerFailedException: Docker container failed: {'StatusCode': 137}
```

**Nguyên nhân:** `load_parquet_to_staging.py` (bản đầu) đọc **nguyên 1 file Parquet** (~2.7 triệu dòng) vào 1 DataFrame pandas, rồi ghi thêm **1 bản sao thứ 2** của toàn bộ dữ liệu đó ra buffer CSV trong RAM (`io.StringIO`) trước khi `COPY` vào Postgres — RAM đỉnh điểm phải chứa 2 bản đầy đủ dữ liệu cùng lúc. Container này ban đầu **không giới hạn `mem_limit`**, chạy chung máy ảo WSL2 (8GB) với Postgres + Airflow scheduler/webserver + Metabase + pgAdmin → hết RAM, hệ điều hành `SIGKILL` (`StatusCode 137`).

**Cách xử lý (triệt để, không phải chỉ tăng RAM):** viết lại `load_parquet_to_staging.py` đọc Parquet theo **từng lô nhỏ** (`pyarrow.parquet.ParquetFile.iter_batches(batch_size=200_000)`) thay vì nạp nguyên file — RAM sử dụng giờ chỉ tỉ lệ với số dòng/lô, không tỉ lệ với dung lượng file, không phụ thuộc RAM cấp cho WSL2 nữa.

**Bài học tổng quát:** khi 1 script Python trong container không giới hạn `mem_limit` xử lý dữ liệu lớn, nên mặc định thiết kế theo kiểu streaming/chunked ngay từ đầu — "nạp hết vào RAM rồi xử lý" chỉ an toàn với dữ liệu đủ nhỏ, không phải chiến lược nên dùng cho pipeline có khả năng mở rộng dữ liệu về sau (đúng tinh thần "mở rộng lên 4 file/~7.4GB" đang ghi trong `docs/roadmap.md`).

---

## 18. Vấn đề: `mem_limit` quá sát gây "page-cache thrashing" (CPU 100% nhưng gần như đứng im nhiều giờ)

**Triệu chứng:** sau khi sửa lỗi #17 (đọc theo batch), đặt `mem_limit="512m"` cho container `taxi-loader`. Task `load_staging` chạy **16+ tiếng không xong** (bình thường chỉ mất vài chục phút), nhưng **không hề bị kill** — `docker stats` cho thấy `CPU 100.48%`, `MEM 375.1MiB / 512MiB` (73%), tức đang hoạt động liên tục chứ không đứng yên.

**Nguyên nhân:** khi container đọc file Parquet qua **bind-mount từ Windows**, nhân Linux giữ "page cache" của file đó trong RAM để đọc nhanh hơn — cache này **bị tính vào `mem_limit` của cgroup**. Với giới hạn chỉ 512MB quá sát so với dung lượng file đang đọc, nhân hệ điều hành phải liên tục giải phóng rồi đọc lại cache (thrashing) để không vượt trần — CPU chạy 100% chỉ để dọn bộ nhớ, không phải xử lý dữ liệu thật. Đây là kiểu lỗi "chậm bất thường do tranh chấp bộ nhớ", khác hẳn kiểu "fail nhanh, rõ ràng" của OOM Kill ở mục #17.

**Cách xử lý:** tăng `mem_limit` lên `1536m` — đủ dư cho cả batch dữ liệu (rất nhỏ, ~200,000 dòng/lô) lẫn page cache của file, không còn phải giành giật bộ nhớ liên tục. Dừng task đang treo bằng `docker kill <container_id>` trước khi trigger lại.

**Bài học tổng quát:** `mem_limit` cho container đọc file lớn qua bind-mount cần có biên độ dư cho page cache, không chỉ tính riêng dung lượng dữ liệu Python thực sự cần — đặt giới hạn quá sát có thể gây triệu chứng "chạy cực chậm nhưng không crash", dễ nhầm là bug logic thay vì vấn đề tài nguyên.

---

## 19. Tối ưu: RAM 8GB WSL2 không đủ dư khi chạy đồng thời Airflow + pgAdmin + Metabase

**Triệu chứng:** không phải lỗi cụ thể, mà là rủi ro phát hiện khi debug lỗi #17/#18 — `docker stats` cho thấy các container không tham gia pipeline (`taxi_pgadmin`, `taxi_metabase`) vẫn chiếm RAM thường trực, làm giảm biên độ an toàn cho các container thực sự cần khi Airflow chạy DAG.

**Nguyên nhân:** `pgadmin`/`metabase` khởi động mặc định cùng `docker compose up -d`, dù chúng **không tham gia** luồng ETL — chỉ dùng để tự tay xem DB hoặc làm dashboard sau khi đã có dữ liệu.

**Cách xử lý:** gắn Compose profile `tools` cho 2 service này — mặc định `docker compose up -d` sẽ **không** khởi động chúng nữa; chỉ bật khi cần bằng `docker compose --profile tools up -d`.

**Bài học tổng quát:** trong môi trường RAM hạn chế (máy dev cá nhân), tách rõ "service lõi cần cho pipeline chạy" khỏi "service tiện ích chỉ dùng thủ công" bằng Compose profiles — tránh phải nhớ tắt/bật tay mỗi lần, giảm rủi ro quên.

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
| 14 | BuildKit `failed to commit ... snapshot does not exist` | Lỗi hạ tầng containerd snapshotter của Docker Desktop | `docker builder prune -af`; tắt "containerd image store" nếu cần |
| 15 | `KeyError: 'HOST_PROJECT_DIR'` lúc DAG import | Thiếu biến môi trường ở container `airflow-init` (chỉ khai ở scheduler) | Thêm biến vào environment của CẢ airflow-init lẫn airflow-scheduler |
| 16 | `could not translate host name "postgres"` | `up -d` chỉ định vài service không áp dụng lại network mới cho service khác đang chạy sẵn | `docker compose down` (không `-v`) rồi `up -d` lại toàn bộ |
| 17 | `DockerContainerFailedException StatusCode 137` (OOM) | Nạp nguyên file Parquet + duplicate CSV buffer trong RAM, không giới hạn mem_limit | Đọc Parquet theo batch (`pyarrow.iter_batches`) — RAM không còn tỉ lệ với dung lượng file |
| 18 | Task chạy 100% CPU nhưng gần như đứng im nhiều giờ | `mem_limit` quá sát (512m), page cache của file bind-mount bị tính vào cgroup → thrashing | Tăng `mem_limit` lên đủ dư (1536m) |
| 19 | RAM 8GB WSL2 không đủ dư khi chạy song song mọi service | pgAdmin/Metabase khởi động mặc định dù không tham gia pipeline | Compose profile `tools` — mặc định không bật, chỉ bật khi cần |

