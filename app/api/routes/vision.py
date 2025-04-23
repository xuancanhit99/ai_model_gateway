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
        model_name: Optional[str] = Form(None, description="Optional: Specify Gemini model name"),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    # Khởi tạo service với model_name từ form
    try:
        service = GeminiService(
            api_key=x_api_key,
            model_name=model_name or settings.GEMINI_VISION_MODEL_NAME
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Gemini Service initialization failed: {e}"
        )

    # Kiểm tra loại file có được phép không
    if file.content_type not in settings.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Định dạng file không được hỗ trợ. Các định dạng cho phép: {', '.join(settings.ALLOWED_CONTENT_TYPES)}"
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
            model_used=service.model_name
        )
    finally:
        await file.close()