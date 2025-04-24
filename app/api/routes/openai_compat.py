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
    x_grok_api_key: Optional[str] = Header(None, alias="X-Grok-API-Key"), # Add Grok key header
):
    """
    Tạo chat completion tương thích với OpenAI, hỗ trợ Gemini và Grok.
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
        if x_grok_api_key: # Add Grok key if provided
            provider_api_keys["grok"] = x_grok_api_key

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

# Endpoint chuẩn OpenAI cho models
@router.get(
    "/models",
    response_model=ModelList,
    summary="List available models"
)
async def list_models(
    user_info: Dict[str, Any] = Depends(verify_api_key)
):
    """Liệt kê các mô hình được hỗ trợ (Gemini, Grok, GigaChat) với tiền tố provider."""
    # Lấy settings để truy cập model names nếu cần (hoặc hardcode như hiện tại)
    # settings = get_settings() # Uncomment if using settings for model IDs

    raw_models = [
        # Gemini Models (Updated list)
        ModelInfo(id="gemini-2.5-flash-preview-04-17", created=1713000000, owned_by="google"),
        ModelInfo(id="gemini-2.5-pro-preview-03-25", created=1711000000, owned_by="google"),
        ModelInfo(id="gemini-2.0-flash", created=1709000000, owned_by="google"),
        ModelInfo(id="gemini-2.0-flash-lite", created=1709000001, owned_by="google"),
        ModelInfo(id="gemini-1.5-flash", created=1708000000, owned_by="google"),
        # ModelInfo(id="gemini-1.5-flash-8b", created=1708000001, owned_by="google"),
        ModelInfo(id="gemini-1.5-pro", created=1707000000, owned_by="google"),
        # ModelInfo(id="gemini-embedding-exp", created=1706000000, owned_by="google"),
        ModelInfo(id="imagen-3.0-generate-002", created=1714000000, owned_by="google"),
        # ModelInfo(id="veo-2.0-generate-001", created=1715000000, owned_by="google"),
        ModelInfo(id="gemini-2.0-flash-live-001", created=1716000000, owned_by="google"),
        # Grok Models (Updated list without prefix)
        ModelInfo(id="grok-2-1212", created=1710000000, owned_by="xai"),
        ModelInfo(id="grok-2-vision-1212", created=1710000001, owned_by="xai"),
        ModelInfo(id="grok-3-beta", created=1710000002, owned_by="xai"),
        ModelInfo(id="grok-3-fast-beta", created=1710000003, owned_by="xai"),
        ModelInfo(id="grok-3-mini-beta", created=1710000004, owned_by="xai"),
        ModelInfo(id="grok-3-mini-fast-beta", created=1710000005, owned_by="xai"),
        ModelInfo(id="grok-beta", created=1710000006, owned_by="xai"),
        ModelInfo(id="grok-vision-beta", created=1710000007, owned_by="xai"),
        # GigaChat Models
        ModelInfo(id="GigaChat", created=1700000000, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-2", created=1700000001, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-2-Max", created=1700000002, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-2-Max-preview", created=1700000003, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-2-Pro", created=1700000004, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-2-Pro-preview", created=1700000005, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-2-preview", created=1700000006, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-Max", created=1700000007, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-Max-preview", created=1700000008, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-Plus", created=1700000009, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-Plus-preview", created=1700000010, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-Pro", created=1700000011, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-Pro-preview", created=1700000012, owned_by="salutedevices"),
        ModelInfo(id="GigaChat-preview", created=1700000013, owned_by="salutedevices"),
    ]

    # Add provider prefix to the model ID for display purposes
    display_models = []
    for model in raw_models:
        prefix = ""
        if model.owned_by == "google":
            prefix = "google/"
        elif model.owned_by == "xai":
            prefix = "x-ai/"
        elif model.owned_by == "salutedevices":
            prefix = "sber/" # Changed prefix to sber/
        display_models.append(
            ModelInfo(
                id=f"{prefix}{model.id}",
                created=model.created,
                owned_by=model.owned_by
            )
        )

    return ModelList(data=display_models)