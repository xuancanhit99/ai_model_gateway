# app/api/routes/openai_compat.py
from fastapi import APIRouter, Depends, HTTPException, Header, status, Request
from fastapi.responses import StreamingResponse # Import StreamingResponse
from typing import Dict, Any, Optional, List
from app.core.auth import verify_api_key
from app.models.schemas import (
    ChatCompletionRequest, 
    ErrorResponse,
    ModelList,
    ModelInfo
)
from app.services.model_router import ModelRouter
import json
import logging

logging.basicConfig(level=logging.INFO)

router = APIRouter()

# Endpoint chuẩn OpenAI cho chat completions
@router.post(
    "/chat/completions",
    summary="OpenAI-compatible chat completions API",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    }
)
async def create_chat_completion(
    request: Request,
    user_info: Dict[str, Any] = Depends(verify_api_key),
    x_google_api_key: Optional[str] = Header(None, alias="X-Google-API-Key"),
):
    """
    Tạo chat completion tương thích với OpenAI.
    Đọc request body trực tiếp để đảm bảo linh hoạt tối đa.
    """
    try:
        # Đọc request body
        body = await request.json()
        model = body.get("model", "gemini-2.5-pro-exp-03-25")
        messages = body.get("messages", [])
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", None)
        stream = body.get("stream", False) # Check for stream parameter

        # Thu thập API key
        provider_api_keys = {}
        if x_google_api_key:
            provider_api_keys["google"] = x_google_api_key
            
        # Định tuyến tới mô hình phù hợp
        if stream:
            # Gọi phương thức streaming mới (sẽ tạo ở bước sau)
            async def stream_generator():
                # Placeholder: Sẽ gọi ModelRouter.stream_chat_completion ở đây
                # và yield các chunk đã được định dạng SSE
                async for chunk in ModelRouter.stream_chat_completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    provider_api_keys=provider_api_keys
                ):
                    yield chunk # ModelRouter.stream_chat_completion sẽ định dạng SSE

            # Trả về StreamingResponse
            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            # Giữ nguyên logic không streaming
            response = await ModelRouter.route_chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_api_keys=provider_api_keys
            )
            # Ghi log phản hồi JSON trước khi trả về (chỉ cho non-streaming)
            logging.info(f"API Response: {json.dumps(response, indent=2, ensure_ascii=False)}")
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

# Endpoint cũ cho tương thích ngược (REMOVED)

# Endpoint chuẩn OpenAI cho models
@router.get(
    "/models",
    response_model=ModelList,
    summary="List available models"
)
async def list_models(
    user_info: Dict[str, Any] = Depends(verify_api_key)
):
    """Liệt kê các mô hình được hỗ trợ."""
    # Danh sách mô hình được hỗ trợ - chỉ bao gồm Gemini
    models = [
        ModelInfo(
            id="gemini-2.5-pro-exp-03-25",
            created=1677610602,
            owned_by="google"
        ),
        ModelInfo(
            id="gemini-2.0-flash",
            created=1677649963,
            owned_by="google"
        ),
        ModelInfo(
            id="gemini-1.5-pro-latest",
            created=1677610602,
            owned_by="google"
        )
    ]
    
    return ModelList(data=models)