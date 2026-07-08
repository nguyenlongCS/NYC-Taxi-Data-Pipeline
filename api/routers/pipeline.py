"""
POST /api/pipeline/trigger — gọi Airflow REST API (stable API v1) để kích
hoạt thủ công DAG `taxi_pipeline` (ứng luồng 10 trong docs/roadmap.md:
RestAPI -> Airflow).

⚠️ Yêu cầu hạ tầng: Airflow webserver mặc định (Airflow 2.x) chỉ bật auth
backend `session` (dựa cookie đăng nhập UI), KHÔNG chấp nhận Basic Auth gọi
từ ngoài vào REST API -- gọi bằng Basic Auth khi chưa bật thêm sẽ nhận
403 Forbidden. Do đó docker-compose.yml (service airflow-webserver) đã
được thêm biến:
    AIRFLOW__API__AUTH_BACKENDS: airflow.api.auth.backend.basic_auth
Nếu vẫn gặp 403, kiểm tra lại biến này đã áp dụng chưa (cần restart lại
container airflow-webserver sau khi thêm).

Dùng lại thẳng AIRFLOW_ADMIN_USER/AIRFLOW_ADMIN_PASSWORD đã có sẵn trong
.env cho Airflow UI -- không cần thêm secret riêng cho API.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schemas import PipelineTriggerResponse

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# URL nội bộ trong Docker network taxi_net -- dùng để API gọi Airflow.
AIRFLOW_BASE_URL = os.environ.get("AIRFLOW_BASE_URL", "http://airflow-webserver:8080")
# URL để NGƯỜI DÙNG bấm mở Airflow UI từ trình duyệt trên máy host --
# khác AIRFLOW_BASE_URL vì "airflow-webserver" chỉ phân giải được bên
# trong Docker network, không phải từ máy host.
AIRFLOW_EXTERNAL_URL = os.environ.get("AIRFLOW_EXTERNAL_URL", "http://localhost:8080")
AIRFLOW_DAG_ID = os.environ.get("AIRFLOW_DAG_ID", "taxi_pipeline")
AIRFLOW_ADMIN_USER = os.environ.get("AIRFLOW_ADMIN_USER")
AIRFLOW_ADMIN_PASSWORD = os.environ.get("AIRFLOW_ADMIN_PASSWORD")

_REQUEST_TIMEOUT_SECONDS = 15


class TriggerPipelineRequest(BaseModel):
    # Cho phép người gọi tự đặt hậu tố dag_run_id để dễ nhận diện (tuỳ chọn).
    # Airflow yêu cầu dag_run_id là duy nhất trong toàn bộ lịch sử của DAG.
    note: Optional[str] = None


@router.post("/trigger", response_model=PipelineTriggerResponse)
def trigger_pipeline(payload: TriggerPipelineRequest = TriggerPipelineRequest()):
    """Trigger thủ công DAG taxi_pipeline (run_spark_job -> load_staging -> dbt_build)."""

    if not AIRFLOW_ADMIN_USER or not AIRFLOW_ADMIN_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="Thiếu cấu hình AIRFLOW_ADMIN_USER/AIRFLOW_ADMIN_PASSWORD cho service api.",
        )

    suffix = f"__{payload.note}" if payload.note else ""
    dag_run_id = (
        f"manual__api__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        f"__{uuid.uuid4().hex[:8]}{suffix}"
    )

    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/{AIRFLOW_DAG_ID}/dagRuns"

    try:
        resp = requests.post(
            url,
            auth=(AIRFLOW_ADMIN_USER, AIRFLOW_ADMIN_PASSWORD),
            json={"dag_run_id": dag_run_id},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Không kết nối được tới Airflow tại {AIRFLOW_BASE_URL}: {exc}",
        )

    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    data = resp.json()
    dag_run_id_returned = data.get("dag_run_id", dag_run_id)

    return PipelineTriggerResponse(
        dag_id=data.get("dag_id", AIRFLOW_DAG_ID),
        dag_run_id=dag_run_id_returned,
        state=data.get("state"),
        logical_date=data.get("logical_date") or data.get("execution_date"),
        airflow_ui_url=(
            f"{AIRFLOW_EXTERNAL_URL}/dags/{AIRFLOW_DAG_ID}/grid"
            f"?dag_run_id={dag_run_id_returned}"
        ),
    )


@router.get("/status/{dag_run_id}")
def get_pipeline_status(dag_run_id: str):
    """Xem trạng thái 1 lần chạy DAG cụ thể (theo dag_run_id trả về từ /trigger)."""

    if not AIRFLOW_ADMIN_USER or not AIRFLOW_ADMIN_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="Thiếu cấu hình AIRFLOW_ADMIN_USER/AIRFLOW_ADMIN_PASSWORD cho service api.",
        )

    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/{AIRFLOW_DAG_ID}/dagRuns/{dag_run_id}"

    try:
        resp = requests.get(
            url,
            auth=(AIRFLOW_ADMIN_USER, AIRFLOW_ADMIN_PASSWORD),
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Không kết nối được tới Airflow tại {AIRFLOW_BASE_URL}: {exc}",
        )

    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    data = resp.json()
    return {
        "dag_id": data.get("dag_id"),
        "dag_run_id": data.get("dag_run_id"),
        "state": data.get("state"),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
    }
