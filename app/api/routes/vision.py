# app/api/routes/vision.py
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Header, Form, Depends
from typing import Optional, Dict, Any
from app.core.db import PostgresCompatClient as Client # Đảm bảo Client được import
from app.models.schemas import VisionResponse, ErrorResponse
from app.services.model_router import ModelRouter
from app.core.auth import verify_api_key_with_provider_keys  # Sử dụng phiên bản nâng cao
from app.core.config import get_settings
from app.core.db import get_db_client # PostgreSQL DB dependency

router = APIRouter()
settings = get_settings()

@router.post(
    "/extract-text",
    response_model=VisionResponse,
    summary="Extract text from an image using the specified model (Gemini or Grok) with failover",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}, # Thêm 503 cho failover exhausted
    }
)
async def extract_text_from_image(
        file: UploadFile = File(..., description="Image file to process (JPEG, PNG, etc. - check model support)"),
        prompt: Optional[str] = Form(None, description="Optional: Custom prompt for extraction"),
        model: Optional[str] = Form(settings.GEMINI_VISION_MODEL_NAME, description="Model ID (e.g., 'google/gemini-pro-vision', 'x-ai/grok-vision')"),
        x_google_api_key: Optional[str] = Header(None, alias="X-Google-API-Key"),
        x_xai_api_key: Optional[str] = Header(None, alias="X-xAI-API-Key"),
        auth_info: Dict[str, Any] = Depends(verify_api_key_with_provider_keys),
        supabase: Client = Depends(get_db_client) # Thêm dependency injection cho supabase
    ):
    """
    Receives an image file and routes the text extraction request
    to the appropriate vision model (Gemini or Grok) via ModelRouter,
    with API key failover support.
    """
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No upload file sent.")

    # Lấy provider keys từ DB (đã được giải mã)
    # Lưu ý: ModelRouter sẽ tự lấy key được chọn và thực hiện failover
    # Chúng ta chỉ cần truyền auth_info và supabase
    db_provider_keys = auth_info.get("provider_keys", {})

    # Chuẩn bị API keys dictionary ban đầu (ưu tiên header, sau đó DB)
    # ModelRouter sẽ sử dụng key này cho lần thử đầu tiên
    provider_api_keys: Dict[str, str] = {}
    google_key = x_google_api_key or db_provider_keys.get("google")
    grok_key = x_xai_api_key or db_provider_keys.get("xai") # Sử dụng 'xai' như trong ModelRouter

    if google_key:
        provider_api_keys["google"] = google_key
    if grok_key:
        # Đảm bảo key trong dict khớp với provider_key_name trong ModelRouter
        provider_api_keys["xai"] = grok_key # Sử dụng 'xai'

    # Ensure a model is specified (using default from Form if None)
    if not model:
        model = settings.GEMINI_VISION_MODEL_NAME

    try:
        # Route the request using ModelRouter, passing supabase and auth_info
        extracted_text, model_used = await ModelRouter.route_vision_extraction(
            model=model,
            image_file=file,
            prompt=prompt,
            provider_api_keys=provider_api_keys, # Truyền key ban đầu (nếu có)
            supabase=supabase, # Truyền supabase client
            auth_info=auth_info # Truyền thông tin xác thực
        )

        # Determine content type for response (use original or default)
        content_type = file.content_type or "application/octet-stream"

        return VisionResponse(
            filename=file.filename or "uploaded_image",
            content_type=content_type,
            extracted_text=extracted_text,
            model_used=model_used
        )

    except HTTPException as http_exc:
        # Bắt lại các lỗi HTTPException từ ModelRouter (bao gồm 503 từ failover)
        raise http_exc
    except Exception as e:
        # Bắt các lỗi không mong muốn khác
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during vision processing: {e}"
        )
    finally:
        # Đảm bảo file được đóng
        await file.close()