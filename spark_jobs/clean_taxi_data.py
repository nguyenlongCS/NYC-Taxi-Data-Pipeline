"""
spark_jobs/clean_taxi_data.py

Giai đoạn Spark (xem docs/roadmap.md, luồng 1 -> 2):
    Raw CSV (raw_data/) --Spark--> Parquet sạch (processed_data/)

Vai trò của bước này -- CHỈ làm "vệ sinh kỹ thuật", KHÔNG áp dụng 5 điều kiện
lọc nghiệp vụ (đó vẫn là việc của dbt trên dwh.fact_trips, xem docs/notes.md
mục 1). Cụ thể job này làm:
    1. Đọc CSV với schema tường minh, phát hiện dòng lỗi cấu trúc (FAILFAST)
       thay vì âm thầm bỏ dòng.
    2. Ép đúng kiểu dữ liệu khớp 1-1 với sql/01_create_schema.sql
       (DecimalType, không dùng Double, để tránh sai số làm tròn).
    3. Đổi tên cột theo đúng tên cột trong staging.yellow_trips
       (VendorID -> vendor_id, RatecodeID -> rate_code_id).
    4. Tự kiểm tra: nếu việc ép kiểu sinh ra giá trị NULL mới (dữ liệu gốc
       không rỗng nhưng cast thất bại) thì dừng lại và báo lỗi.
    5. In ra count + checksum (SUM total_amount / trip_distance / fare_amount)
       để đối chiếu thủ công với baseline đã đo trên staging hiện tại.
    6. Ghi kết quả ra processed_data/yellow_trips_clean/ dạng Parquet.

Bước nạp Parquet này vào Postgres KHÔNG nằm trong file này -- xem
load_parquet_to_staging.py (chạy bằng Python thường trên máy host).

Cách chạy (trong container Spark, sau khi `docker compose up -d`):
    docker compose run --rm spark /opt/spark/bin/spark-submit /opt/spark_data/spark_jobs/clean_taxi_data.py

Lưu ý về image Spark đang dùng (spark:python3, xem docker-compose.yml):
    - Đây là Spark 4.1.2 (đã xác nhận bằng `spark-submit --version`), KHÔNG phải
      3.5.x như dự tính ban đầu (bitnami/spark, image gốc không còn tag miễn phí).
    - Spark 4.x đổi mặc định spark.sql.ansi.enabled từ false -> true. Với ANSI
      bật, cast lỗi (vd. chuỗi không phải số ép sang int) sẽ làm job crash ngay
      lập tức thay vì trả về NULL như hành vi cũ (Spark 3.x). Job này CHỦ ĐỘNG
      tắt ANSI mode (xem SparkSession.builder bên dưới) để cast lỗi trả về
      NULL, khớp với thiết kế kiểm tra dữ liệu ở bước 4 phía trên.

⚠️ Lịch sử sửa lỗi (xem docs/troubleshooting.md mục 13):
Bản đầu tiên của file này dùng .cache() trên CẢ HAI DataFrame (raw_df và
clean_df), rồi kiểm tra NULL bằng vòng lặp 14 cột x 2 lần .count() (~28 job
Spark riêng biệt). Với bộ nhớ JVM mặc định của container (~1GB, local mode),
việc giữ 2 bản đầy đủ 22 triệu dòng trong RAM cùng lúc gây
`java.lang.OutOfMemoryError: Java heap space`.

Cách sửa: gộp toàn bộ việc ép kiểu + audit NULL vào MỘT lượt select duy nhất
(build_target_with_audit), rồi tính hết checksum + đếm NULL trong MỘT lệnh
.agg() duy nhất (1 job thay vì 28 job). KHÔNG dùng .cache() -- đánh đổi: CSV
sẽ được đọc lại 2 lần (1 lần kiểm tra, 1 lần ghi Parquet) thay vì 1 lần, chậm
hơn một chút nhưng an toàn tuyệt đối về bộ nhớ, không phụ thuộc cấu hình RAM
của máy chạy Docker.
"""

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DecimalType
from pyspark.sql.functions import col, to_timestamp, trim, when, sum as spark_sum

# ---- Đường dẫn (bên trong container, khớp mount trong docker-compose.yml) ----
RAW_DATA_DIR = "/opt/spark_data/raw_data"
OUTPUT_DIR = "/opt/spark_data/processed_data/yellow_trips_clean"

# Chỉ định danh 2 file -- KHÔNG dùng wildcard, tránh nạp nhầm nếu sau này có
# thêm yellow_tripdata_2015-01.csv / 2016-03.csv trong raw_data/ (xem
# docs/dataset.md -- 2 file đó hiện là "dự phòng / mở rộng sau", chưa dùng).
INPUT_FILES = [
    f"{RAW_DATA_DIR}/yellow_tripdata_2016-01.csv",
    f"{RAW_DATA_DIR}/yellow_tripdata_2016-02.csv",
]

# ---- Schema thô -- đúng thứ tự + tên cột gốc trong header CSV ----
RAW_SCHEMA = StructType([
    StructField("VendorID", StringType(), True),
    StructField("tpep_pickup_datetime", StringType(), True),
    StructField("tpep_dropoff_datetime", StringType(), True),
    StructField("passenger_count", StringType(), True),
    StructField("trip_distance", StringType(), True),
    StructField("pickup_longitude", StringType(), True),
    StructField("pickup_latitude", StringType(), True),
    StructField("RatecodeID", StringType(), True),
    StructField("store_and_fwd_flag", StringType(), True),
    StructField("dropoff_longitude", StringType(), True),
    StructField("dropoff_latitude", StringType(), True),
    StructField("payment_type", StringType(), True),
    StructField("fare_amount", StringType(), True),
    StructField("extra", StringType(), True),
    StructField("mta_tax", StringType(), True),
    StructField("tip_amount", StringType(), True),
    StructField("tolls_amount", StringType(), True),
    StructField("improvement_surcharge", StringType(), True),
    StructField("total_amount", StringType(), True),
])

TIMESTAMP_FORMAT = "yyyy-MM-dd HH:mm:ss"

# Thứ tự cột đích -- khớp 1-1 với staging.yellow_trips (01_create_schema.sql)
TARGET_COLUMNS = [
    "vendor_id", "tpep_pickup_datetime", "tpep_dropoff_datetime",
    "passenger_count", "trip_distance", "pickup_longitude", "pickup_latitude",
    "rate_code_id", "store_and_fwd_flag", "dropoff_longitude", "dropoff_latitude",
    "payment_type", "fare_amount", "extra", "mta_tax", "tip_amount",
    "tolls_amount", "improvement_surcharge", "total_amount",
]

# Các cột cần audit NULL (loại trừ store_and_fwd_flag -- chỉ trim, không cast
# kiểu số/thời gian nên không có rủi ro sinh NULL do sai định dạng)
AUDIT_TARGETS = [c for c in TARGET_COLUMNS if c != "store_and_fwd_flag"]


def read_raw(spark):
    """Đọc CSV thô, FAILFAST nếu có dòng sai số lượng cột / không đúng schema."""
    return (
        spark.read
        .option("header", "true")
        .option("mode", "FAILFAST")
        .schema(RAW_SCHEMA)
        .csv(INPUT_FILES)
    )


def build_target_with_audit(raw_df):
    """
    Ép kiểu + đổi tên cột (khớp staging.yellow_trips), ĐỒNG THỜI tính sẵn cờ
    audit "_lost_<cột>" = 1 nếu dữ liệu gốc không rỗng nhưng cast ra NULL.
    Tất cả tính trong 1 lượt .select() duy nhất -- không cần đọc/quét dữ liệu
    nhiều lần như bản trước.
    """
    vendor_id = col("VendorID").cast("int")
    pickup_ts = to_timestamp(col("tpep_pickup_datetime"), TIMESTAMP_FORMAT)
    dropoff_ts = to_timestamp(col("tpep_dropoff_datetime"), TIMESTAMP_FORMAT)
    passenger_count = col("passenger_count").cast("int")
    rate_code_id = col("RatecodeID").cast("int")
    payment_type = col("payment_type").cast("int")
    trip_distance = col("trip_distance").cast(DecimalType(10, 2))
    fare_amount = col("fare_amount").cast(DecimalType(10, 2))
    extra = col("extra").cast(DecimalType(10, 2))
    mta_tax = col("mta_tax").cast(DecimalType(10, 2))
    tip_amount = col("tip_amount").cast(DecimalType(10, 2))
    tolls_amount = col("tolls_amount").cast(DecimalType(10, 2))
    improvement_surcharge = col("improvement_surcharge").cast(DecimalType(10, 2))
    total_amount = col("total_amount").cast(DecimalType(10, 2))
    pickup_longitude = col("pickup_longitude").cast(DecimalType(11, 7))
    pickup_latitude = col("pickup_latitude").cast(DecimalType(11, 7))
    dropoff_longitude = col("dropoff_longitude").cast(DecimalType(11, 7))
    dropoff_latitude = col("dropoff_latitude").cast(DecimalType(11, 7))

    def audit(raw_col_name, casted_col):
        raw_c = col(raw_col_name)
        return when(
            raw_c.isNotNull() & (trim(raw_c) != "") & casted_col.isNull(), 1
        ).otherwise(0)

    return raw_df.select(
        # ---- cột đích (thứ tự khớp TARGET_COLUMNS) ----
        vendor_id.alias("vendor_id"),
        pickup_ts.alias("tpep_pickup_datetime"),
        dropoff_ts.alias("tpep_dropoff_datetime"),
        passenger_count.alias("passenger_count"),
        trip_distance.alias("trip_distance"),
        pickup_longitude.alias("pickup_longitude"),
        pickup_latitude.alias("pickup_latitude"),
        rate_code_id.alias("rate_code_id"),
        trim(col("store_and_fwd_flag")).alias("store_and_fwd_flag"),
        dropoff_longitude.alias("dropoff_longitude"),
        dropoff_latitude.alias("dropoff_latitude"),
        payment_type.alias("payment_type"),
        fare_amount.alias("fare_amount"),
        extra.alias("extra"),
        mta_tax.alias("mta_tax"),
        tip_amount.alias("tip_amount"),
        tolls_amount.alias("tolls_amount"),
        improvement_surcharge.alias("improvement_surcharge"),
        total_amount.alias("total_amount"),
        # ---- cờ audit NULL (dùng nội bộ, không ghi ra Parquet) ----
        audit("VendorID", vendor_id).alias("_lost_vendor_id"),
        audit("tpep_pickup_datetime", pickup_ts).alias("_lost_tpep_pickup_datetime"),
        audit("tpep_dropoff_datetime", dropoff_ts).alias("_lost_tpep_dropoff_datetime"),
        audit("passenger_count", passenger_count).alias("_lost_passenger_count"),
        audit("trip_distance", trip_distance).alias("_lost_trip_distance"),
        audit("pickup_longitude", pickup_longitude).alias("_lost_pickup_longitude"),
        audit("pickup_latitude", pickup_latitude).alias("_lost_pickup_latitude"),
        audit("RatecodeID", rate_code_id).alias("_lost_rate_code_id"),
        audit("dropoff_longitude", dropoff_longitude).alias("_lost_dropoff_longitude"),
        audit("dropoff_latitude", dropoff_latitude).alias("_lost_dropoff_latitude"),
        audit("payment_type", payment_type).alias("_lost_payment_type"),
        audit("fare_amount", fare_amount).alias("_lost_fare_amount"),
        audit("extra", extra).alias("_lost_extra"),
        audit("mta_tax", mta_tax).alias("_lost_mta_tax"),
        audit("tip_amount", tip_amount).alias("_lost_tip_amount"),
        audit("tolls_amount", tolls_amount).alias("_lost_tolls_amount"),
        audit("improvement_surcharge", improvement_surcharge).alias("_lost_improvement_surcharge"),
        audit("total_amount", total_amount).alias("_lost_total_amount"),
    )


def run_audit_and_checksum(df):
    """
    MỘT lượt .agg() duy nhất: vừa đếm số dòng bị mất do cast lỗi (từng cột),
    vừa tính checksum (SUM total_amount / trip_distance / fare_amount) --
    thay cho 28 lượt .count() riêng lẻ ở bản trước (nguyên nhân gây OOM).
    Trả về 1 dict kết quả (Row đã collect về driver, rất nhẹ).
    """
    agg_exprs = [spark_sum(f"_lost_{c}").alias(f"lost_{c}") for c in AUDIT_TARGETS]
    agg_exprs += [
        spark_sum("total_amount").alias("sum_total_amount"),
        spark_sum("trip_distance").alias("sum_trip_distance"),
        spark_sum("fare_amount").alias("sum_fare_amount"),
    ]
    from pyspark.sql.functions import count as spark_count
    agg_exprs.append(spark_count("*").alias("row_count"))

    result = df.agg(*agg_exprs).collect()[0].asDict()
    return result


def main():
    spark = (
        SparkSession.builder
        .appName("nyc_taxi_clean")
        .master("local[*]")
        # Tắt ANSI mode (mặc định=true từ Spark 4.0) -- xem ghi chú đầu file.
        # Cần "false" để cast lỗi trả về NULL (hành vi Spark 3.x) thay vì
        # crash ngay lập tức, khớp với thiết kế audit ở build_target_with_audit().
        .config("spark.sql.ansi.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    print(f"Đang đọc {len(INPUT_FILES)} file CSV...")
    raw_df = read_raw(spark)

    print("Đang ép kiểu dữ liệu + chuẩn bị audit NULL (chưa thực thi, lazy)...")
    combined_df = build_target_with_audit(raw_df)

    print("Đang chạy 1 lượt quét duy nhất: kiểm tra NULL + tính checksum "
          "(có thể mất vài phút cho 22 triệu dòng)...")
    result = run_audit_and_checksum(combined_df)

    lost_errors = [
        f"  - Cột '{c}': {result[f'lost_{c}']:,} giá trị bị cast thành NULL "
        f"(dữ liệu gốc không rỗng nhưng không parse được)."
        for c in AUDIT_TARGETS
        if result[f"lost_{c}"] and result[f"lost_{c}"] > 0
    ]
    if lost_errors:
        raise ValueError(
            "Phát hiện dữ liệu bị hỏng khi ép kiểu (Spark cast tạo NULL mới):\n"
            + "\n".join(lost_errors)
            + "\n=> Dừng job. Kiểm tra lại dữ liệu gốc trước khi tiếp tục."
        )
    print("Không phát hiện dữ liệu bị hỏng khi ép kiểu.")

    print(f"\n=== Checksum ===")
    print(f"count               : {result['row_count']:,}")
    print(f"SUM(total_amount)   : {result['sum_total_amount']}")
    print(f"SUM(trip_distance)  : {result['sum_trip_distance']}")
    print(f"SUM(fare_amount)    : {result['sum_fare_amount']}")
    print("So sánh 4 số trên với baseline đã đo trên staging.yellow_trips hiện tại.\n")

    print(f"Đang ghi Parquet ra {OUTPUT_DIR} ...")
    (
        combined_df
        .select(*TARGET_COLUMNS)  # bỏ các cột audit "_lost_*", chỉ giữ cột đích
        .coalesce(8)  # gộp thành 8 file Parquet, đủ nhỏ để đọc lại nhanh ở bước load
        .write
        .mode("overwrite")  # ghi đè -- an toàn để chạy lại nhiều lần (idempotent)
        .parquet(OUTPUT_DIR)
    )
    print("Hoàn tất.")

    spark.stop()


if __name__ == "__main__":
    main()