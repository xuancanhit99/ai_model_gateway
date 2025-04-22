from fastapi import APIRouter, status
from app.services.gemini import GeminiService
from pydantic import BaseModel
from datetime import datetime
import psutil
import time

router = APIRouter()
start_time = time.time()


class HealthResponse(BaseModel):
    status: str
    uptime: str
    gemini_api: bool
    system_stats: dict


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"]
)
async def health_check():
    # Check Gemini API connection
    try:
        gemini_service = GeminiService()
        gemini_status = True
    except Exception:
        gemini_status = False

    # Calculate uptime
    uptime = str(datetime.fromtimestamp(time.time() - start_time).strftime('%H:%M:%S'))

    # Get system stats
    system_stats = {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent
    }

    return HealthResponse(
        status="healthy",
        uptime=uptime,
        gemini_api=gemini_status,
        system_stats=system_stats
    )