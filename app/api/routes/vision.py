# app/api/routes/vision.py
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Header, Form
from typing import Optional
from app.models.schemas import VisionResponse, ErrorResponse
from app.services.gemini import GeminiService
from app.core.config import get_settings
from PIL import Image
import io

router = APIRouter()
settings = get_settings()

@router.post(
    "/extract-text",
    response_model=VisionResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    }
)
async def extract_text_from_image(
        file: UploadFile = File(..., description="Image file to process"),
        prompt: Optional[str] = Form(None, description="Optional: Custom prompt for extraction"),
        model: Optional[str] = Form(None, description="Optional: Specify Gemini model ID"), # Changed model_name to model
        x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    # Khởi tạo service với model từ form
    try:
        # Pass the model parameter to GeminiService (will be renamed in service)
        service = GeminiService(
            api_key=x_api_key,
            model=model or settings.GEMINI_VISION_MODEL_NAME
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Gemini Service initialization failed: {e}"
        )

    # Kiểm tra loại file có được phép không (sử dụng danh sách cho Gemini)
    if file.content_type not in settings.GEMINI_ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Định dạng file không được hỗ trợ cho Gemini. Các định dạng cho phép: {', '.join(settings.GEMINI_ALLOWED_CONTENT_TYPES)}"
        )

    try:
        image_bytes = await file.read()
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()

        extracted_text = await service.extract_text(
            image_bytes,
            file.content_type,
            prompt=prompt
        )

        return VisionResponse(
            filename=file.filename,
            content_type=file.content_type,
            extracted_text=extracted_text,
            model_used=service.model_id # Use the renamed internal variable (will be changed in service)
        )
    finally:
        await file.close()