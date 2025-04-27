# app/api/routes/vision.py
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Header, Form, Depends
from typing import Optional, Dict, Any
from app.models.schemas import VisionResponse, ErrorResponse
from app.services.model_router import ModelRouter
from app.core.auth import verify_api_key_with_provider_keys  # Sử dụng phiên bản nâng cao
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

@router.post(
    "/extract-text",
    response_model=VisionResponse,
    summary="Extract text from an image using the specified model (Gemini or Grok)",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    }
)
async def extract_text_from_image(
        file: UploadFile = File(..., description="Image file to process (JPEG, PNG, etc. - check model support)"),
        prompt: Optional[str] = Form(None, description="Optional: Custom prompt for extraction"),
        model: Optional[str] = Form(settings.GEMINI_VISION_MODEL_NAME, description="Model ID (e.g., 'google/gemini-pro-vision', 'x-ai/grok-vision')"),
        x_google_api_key: Optional[str] = Header(None, alias="X-Google-API-Key"),
        x_xai_api_key: Optional[str] = Header(None, alias="X-xAI-API-Key"),
        auth_info: Dict[str, Any] = Depends(verify_api_key_with_provider_keys)  # Sử dụng verify_api_key_with_provider_keys
    ):
    """
    Receives an image file and routes the text extraction request
    to the appropriate vision model (Gemini or Grok) via ModelRouter.
    """
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No upload file sent.")

    # Lấy provider keys từ DB (đã được giải mã)
    db_provider_keys = auth_info.get("provider_keys", {})
    
    # Chuẩn bị API keys dictionary với thứ tự ưu tiên:
    # 1. Từ header
    # 2. Từ DB (provider keys của người dùng)
    # 3. Từ settings (mặc định)
    provider_api_keys: Dict[str, str] = {}
    
    # Google key
    google_key = x_google_api_key or db_provider_keys.get("google") or settings.GOOGLE_AI_STUDIO_API_KEY
    
    # Grok key
    grok_key = x_xai_api_key or db_provider_keys.get("xai") or settings.XAI_API_KEY

    if google_key:
        provider_api_keys["google"] = google_key
    if grok_key:
        provider_api_keys["grok"] = grok_key

    # Ensure a model is specified (using default from Form if None)
    if not model:
        model = settings.GEMINI_VISION_MODEL_NAME

    try:
        # Route the request using ModelRouter
        extracted_text, model_used = await ModelRouter.route_vision_extraction(
            model=model,
            image_file=file,
            prompt=prompt,
            provider_api_keys=provider_api_keys
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
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during vision processing: {e}"
        )
    finally:
        await file.close()