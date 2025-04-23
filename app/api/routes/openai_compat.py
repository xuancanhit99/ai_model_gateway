# app/api/routes/openai_compat.py
from fastapi import APIRouter, Depends, HTTPException, Header, status
from typing import Dict, Any, Optional, List
from app.core.auth import verify_api_key
from app.models.schemas import (
    ChatCompletionRequest, 
    ChatCompletionResponse, 
    ErrorResponse,
    ModelList,
    ModelInfo
)
from app.services.model_router import ModelRouter

router = APIRouter()

@router.post(
    "/completions",
    response_model=ChatCompletionResponse,
    summary="OpenAI-compatible chat completions API",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    }
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    user_info: Dict[str, Any] = Depends(verify_api_key),
    x_google_api_key: Optional[str] = Header(None, alias="X-Google-API-Key"),
    x_xai_api_key: Optional[str] = Header(None, alias="X-xAI-API-Key"),
):
    """
    Tạo chat completion tương thích với OpenAI.
    Hỗ trợ các mô hình từ nhiều nhà cung cấp.
    """
    try:
        # Thu thập API key của từng nhà cung cấp
        provider_api_keys = {}
        if x_google_api_key:
            provider_api_keys["google"] = x_google_api_key
        if x_xai_api_key:
            provider_api_keys["x-ai"] = x_xai_api_key
            
        # Định tuyến tới mô hình phù hợp
        response = await ModelRouter.route_chat_completion(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            provider_api_keys=provider_api_keys
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi tham số: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi không mong đợi: {e}"
        )

@router.get(
    "/models",
    response_model=ModelList,
    summary="List available models"
)
async def list_models(
    user_info: Dict[str, Any] = Depends(verify_api_key)
):
    """Liệt kê các mô hình được hỗ trợ."""
    # Danh sách mô hình được hỗ trợ
    models = [
        ModelInfo(
            id="google/gemini-2.5-pro-exp-03-25",
            created=1677610602,
            owned_by="google"
        ),
        ModelInfo(
            id="google/gemini-2.0-flash",
            created=1677649963,
            owned_by="google"
        )
        # Sau này sẽ thêm các mô hình khác
    ]
    
    return ModelList(data=models)