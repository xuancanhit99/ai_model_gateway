# app/api/routes/openai_compat.py
from fastapi import APIRouter, Depends, HTTPException, Header, status, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List
from supabase import Client # Thêm import Supabase Client
from app.core.supabase_client import get_supabase_client # Import dependency lấy Supabase client
from app.core.auth import verify_api_key_with_provider_keys  # Sử dụng phiên bản nâng cao
from app.models.schemas import (
    ChatCompletionRequest,
    ErrorResponse,
    ModelList,
    ModelInfo
)
from app.services.model_router import ModelRouter
from app.core.config import get_settings
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
    auth_info: Dict[str, Any] = Depends(verify_api_key_with_provider_keys),  # auth_info giờ chứa cả token
    supabase: Client = Depends(get_supabase_client), # Inject Supabase client
    x_google_api_key: Optional[str] = Header(None, alias="X-Google-API-Key"),
    x_xai_api_key: Optional[str] = Header(None, alias="X-xAI-API-Key"),
    x_gigachat_api_key: Optional[str] = Header(None, alias="X-GigaChat-API-Key"),
    x_perplexity_api_key: Optional[str] = Header(None, alias="X-Perplexity-API-Key"),
):
    """
    Tạo chat completion tương thích với OpenAI, hỗ trợ tự động failover.
    Đọc request body trực tiếp.
    """
    try:
        # Đọc request body
        body = await request.json()
        model = body.get("model", "gemini-2.5-pro-exp-03-25")
        messages = body.get("messages", [])
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", None)
        stream = body.get("stream", False)

        # Lấy provider keys từ DB (đã được giải mã)
        db_provider_keys = auth_info.get("provider_keys", {})
        
        # Chuẩn bị API keys dictionary với thứ tự ưu tiên:
        # 1. Từ header
        # 2. Từ DB (provider keys của người dùng)
        # 3. Từ settings (mặc định)
        provider_api_keys = {}
        
        # Google key
        google_key = x_google_api_key or db_provider_keys.get("google") or get_settings().GOOGLE_AI_STUDIO_API_KEY
        
        # Grok key
        grok_key = x_xai_api_key or db_provider_keys.get("xai") or get_settings().XAI_API_KEY
        
        # GigaChat key
        gigachat_key = x_gigachat_api_key or db_provider_keys.get("gigachat") or get_settings().GIGACHAT_AUTH_KEY
        
        # Perplexity key
        perplexity_key = x_perplexity_api_key or db_provider_keys.get("perplexity") or get_settings().PERPLEXITY_API_KEY

        # Thêm key vào dictionary nếu có
        if google_key:
            provider_api_keys["google"] = google_key
        if grok_key:
            provider_api_keys["grok"] = grok_key
        if gigachat_key:
            provider_api_keys["gigachat"] = gigachat_key
        if perplexity_key:
            provider_api_keys["perplexity"] = perplexity_key

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
                    provider_api_keys=provider_api_keys,
                    supabase=supabase, # Truyền supabase client
                    auth_info=auth_info # Truyền auth_info đầy đủ (chứa token)
                ):
                    yield chunk

            # Trả về StreamingResponse
            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            # Giữ nguyên logic không streaming
            response = await ModelRouter.route_chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_api_keys=provider_api_keys,
                supabase=supabase, # Truyền supabase client
                auth_info=auth_info # Truyền auth_info đầy đủ (chứa token)
            )
            # Ghi log phản hồi JSON trước khi trả về (chỉ cho non-streaming)
            # Có thể di chuyển log này vào trong ModelRouter nếu muốn log cả trường hợp failover
            logging.info(f"Final API Response: {json.dumps(response, indent=2, ensure_ascii=False)}")
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
    auth_info: Dict[str, Any] = Depends(verify_api_key_with_provider_keys)  # Sử dụng phiên bản nâng cao
):
    """Liệt kê các mô hình được hỗ trợ (Gemini, Grok, GigaChat, Perplexity Sonar) với tiền tố provider."""
    # Lấy settings để truy cập model names nếu cần (hoặc hardcode như hiện tại)
    # settings = get_settings() # Uncomment if using settings for model IDs

    # Định nghĩa context window dựa trên bảng người dùng cung cấp
    # Sử dụng giá trị chính xác hoặc giá trị được giả định/ước tính từ bảng
    GEMINI_1_5_PRO_CONTEXT = 1048576
    GEMINI_2_0_FLASH_CONTEXT = 1000000 # Bảng ghi 1M
    GEMINI_2_5_PRO_PREVIEW_CONTEXT = 1048576
    GEMINI_2_5_PRO_EXP_CONTEXT = 1048576 # Giả định theo bảng
    GEMINI_2_5_FLASH_PREVIEW_CONTEXT = 1000000 # Giả định theo bảng (>= 1M)
    GROK_2_CONTEXT = 131072
    GROK_VISION_CONTEXT = 8192 # Theo bảng cho grok-2-vision và grok-vision-beta
    GIGACHAT_V1_CONTEXT = 32768
    GIGACHAT_V2_CONTEXT = 128000
    SONAR_DEFAULT_CONTEXT = 128000
    SONAR_PRO_CONTEXT = 200000
    R1_CONTEXT = 128000

    raw_models = [
        # Gemini Models
        ModelInfo(id="gemini-1.5-pro", created=1707000000, owned_by="google", context_window=GEMINI_1_5_PRO_CONTEXT),
        ModelInfo(id="gemini-2.0-flash", created=1709000000, owned_by="google", context_window=GEMINI_2_0_FLASH_CONTEXT),
        ModelInfo(id="gemini-2.0-flash-lite", created=1709000001, owned_by="google", context_window=GEMINI_2_0_FLASH_CONTEXT), # Giả định giống 2.0 flash
        ModelInfo(id="gemini-2.0-flash-live-001", created=1716000000, owned_by="google", context_window=GEMINI_2_0_FLASH_CONTEXT), # Giả định giống 2.0 flash
        ModelInfo(id="gemini-2.5-pro-preview-03-25", created=1711000000, owned_by="google", context_window=GEMINI_2_5_PRO_PREVIEW_CONTEXT),
        ModelInfo(id="gemini-2.5-pro-exp-03-25", created=1711000100, owned_by="google", context_window=GEMINI_2_5_PRO_EXP_CONTEXT), # Model của bạn
        ModelInfo(id="gemini-2.5-flash-preview-04-17", created=1713000000, owned_by="google", context_window=GEMINI_2_5_FLASH_PREVIEW_CONTEXT),
        ModelInfo(id="imagen-3.0-generate-002", created=1714000000, owned_by="google"), # Image model

        # Grok Models
        ModelInfo(id="grok-beta", created=1710000006, owned_by="xai", context_window=GROK_2_CONTEXT), # Giả định theo grok-2
        ModelInfo(id="grok-vision-beta", created=1710000007, owned_by="xai", context_window=GROK_VISION_CONTEXT),
        ModelInfo(id="grok-2-1212", created=1710000000, owned_by="xai", context_window=GROK_2_CONTEXT),
        ModelInfo(id="grok-2-vision-1212", created=1710000001, owned_by="xai", context_window=GROK_VISION_CONTEXT),
        ModelInfo(id="grok-3-beta", created=1710000002, owned_by="xai", context_window=GROK_2_CONTEXT), # Giả định theo grok-2
        ModelInfo(id="grok-3-fast-beta", created=1710000003, owned_by="xai", context_window=GROK_2_CONTEXT), # Giả định theo grok-2
        ModelInfo(id="grok-3-mini-beta", created=1710000004, owned_by="xai", context_window=GROK_2_CONTEXT), # Giả định theo grok-2
        ModelInfo(id="grok-3-mini-fast-beta", created=1710000005, owned_by="xai", context_window=GROK_2_CONTEXT), # Giả định theo grok-2

        # GigaChat Models (v1)
        ModelInfo(id="GigaChat", created=1700000000, owned_by="salutedevices", context_window=GIGACHAT_V1_CONTEXT),
        ModelInfo(id="GigaChat-Pro", created=1700000011, owned_by="salutedevices", context_window=GIGACHAT_V1_CONTEXT),
        ModelInfo(id="GigaChat-Max", created=1700000007, owned_by="salutedevices", context_window=GIGACHAT_V1_CONTEXT),
        ModelInfo(id="GigaChat-Plus", created=1700000009, owned_by="salutedevices"), # Không có context trong bảng
        ModelInfo(id="GigaChat-preview", created=1700000013, owned_by="salutedevices", context_window=GIGACHAT_V1_CONTEXT), # Giả định
        ModelInfo(id="GigaChat-Pro-preview", created=1700000012, owned_by="salutedevices", context_window=GIGACHAT_V1_CONTEXT), # Giả định
        ModelInfo(id="GigaChat-Max-preview", created=1700000008, owned_by="salutedevices", context_window=GIGACHAT_V1_CONTEXT), # Giả định
        ModelInfo(id="GigaChat-Plus-preview", created=1700000010, owned_by="salutedevices"), # Không có context trong bảng

        # GigaChat Models (v2)
        ModelInfo(id="GigaChat-2", created=1700000001, owned_by="salutedevices", context_window=GIGACHAT_V2_CONTEXT),
        ModelInfo(id="GigaChat-2-Pro", created=1700000004, owned_by="salutedevices", context_window=GIGACHAT_V2_CONTEXT),
        ModelInfo(id="GigaChat-2-Max", created=1700000002, owned_by="salutedevices", context_window=GIGACHAT_V2_CONTEXT),
        ModelInfo(id="GigaChat-2-preview", created=1700000006, owned_by="salutedevices", context_window=GIGACHAT_V2_CONTEXT), # Giả định
        ModelInfo(id="GigaChat-2-Pro-preview", created=1700000005, owned_by="salutedevices", context_window=GIGACHAT_V2_CONTEXT), # Giả định
        ModelInfo(id="GigaChat-2-Max-preview", created=1700000003, owned_by="salutedevices", context_window=GIGACHAT_V2_CONTEXT), # Giả định

        # Perplexity Sonar Models
        ModelInfo(id="sonar", created=1717000000, owned_by="perplexity", context_window=SONAR_DEFAULT_CONTEXT),
        ModelInfo(id="sonar-pro", created=1717000001, owned_by="perplexity", context_window=SONAR_PRO_CONTEXT),
        ModelInfo(id="sonar-reasoning", created=1717000002, owned_by="perplexity", context_window=SONAR_DEFAULT_CONTEXT),
        ModelInfo(id="sonar-reasoning-pro", created=1717000003, owned_by="perplexity", context_window=SONAR_DEFAULT_CONTEXT),
        ModelInfo(id="sonar-deep-research", created=1717000004, owned_by="perplexity", context_window=SONAR_DEFAULT_CONTEXT),
        ModelInfo(id="r1-1776", created=1717000005, owned_by="perplexity", context_window=R1_CONTEXT),
    ]

    # Add provider prefix and context window to the model ID for display purposes
    display_models = []
    for model in raw_models:
        prefix = ""
        if model.owned_by == "google":
            prefix = "google/"
        elif model.owned_by == "xai":
            prefix = "x-ai/"
        elif model.owned_by == "salutedevices":
            prefix = "sber/" # Changed prefix to sber/
        elif model.owned_by == "perplexity":
            prefix = "perplexity/"
        display_models.append(
            ModelInfo(
                id=f"{prefix}{model.id}", # Giữ nguyên ID có prefix
                created=model.created,
                owned_by=model.owned_by,
                context_window=model.context_window # Thêm context_window vào response
            )
        )

    return ModelList(data=display_models)