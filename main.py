import pandas as pd

# chỉ đọc 5 dòng đầu để xem cột
df_sample = pd.read_csv("raw_data/yellow_tripdata_2015-01.csv", nrows=5)
print(df_sample.columns.tolist())
print(df_sample.dtypes)
print(df_sample.head())

# đếm số dòng thực tế mà không load hết (đọc theo chunk)
total_rows = sum(1 for _ in open("raw_data/yellow_tripdata_2015-01.csv"))
print(f"Tổng số dòng: {total_rows:,}")