NYC Taxi Data Pipeline/
│
├── docs/							# Chứa toàn bộ tài liệu của dự án
│   ├── dataset.md       		   	# Link tải dataset từ Kaggle, mô tả dataset
│   ├── setup.md		         	# Hướng dẫn thực hiện từng bước
│   ├── system_architecture.md 	    # Kiến trúc hệ thống, công nghệ sử dụng,...
│   ├── project_structure.md   	    # Mô tả cấu trúc thư mục và file trong dự án	
│   ├── pipeline.md
│   ├── data_dictionary.md
│   ├── troubleshooting.md
│   ├── images/
│   └── ...
│
├── raw_data/                    	# Chứa dữ liệu gốc, không đưa lên GitHub vì dung lượng lớn
│   ├── yellow_tripdata_2015-01.csv
│   ├── yellow_tripdata_2016-01.csv
│   ├── yellow_tripdata_2016-02.csv
│   └── yellow_tripdata_2016-03.csv
│
├── sql/   
│   └── 01_create_schema.sql
│
├── docker-compose.yml
├── .gitignore
├── requirements.txt
├── load_staging.py
└── main.py

Lưu ý: Dự án vẫn đang trong quá trình phát triển, vì vậy cấu trúc thư mục và tài liệu có thể được cập nhật trong các phiên bản tiếp theo.