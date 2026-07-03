{#
    Mặc định dbt sẽ đặt tên schema là "<schema đích trong profiles.yml>_<+schema config>"
    (ví dụ "dwh_dwh", "dwh_staging_dbt"...). Dự án này cần schema đích CHÍNH XÁC
    như khai báo trong dbt_project.yml (đặc biệt là marts phải đổ vào đúng "dwh"
    đã tồn tại sẵn, để không phải cấu hình lại kết nối Metabase).

    Override macro generate_schema_name để bỏ qua bước ghép tiền tố đó.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}

        {{ default_schema }}

    {%- else -%}

        {{ custom_schema_name | trim }}

    {%- endif -%}

{%- endmacro %}