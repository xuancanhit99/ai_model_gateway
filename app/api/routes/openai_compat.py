# app/api/routes/openai_compat.py
from fastapi import APIRouter, Depends, HTTPException, Header, status, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List
from app.core.db import PostgresCompatClient as Client # Thêm import Supabase Client
from app.core.db import get_db_client # Import dependency lấy Supabase client
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
    supabase: Client = Depends(get_db_client), # Inject Supabase client
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
            provider_api_keys["xai"] = grok_key
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

    # Load model data from JSON file
    model_file_path = "app/core/models.json"
    try:
        with open(model_file_path, "r", encoding="utf-8") as f:
            raw_model_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading models from {model_file_path}: {e}")
        # Trả về danh sách rỗng hoặc danh sách mặc định nếu không đọc được file
        raw_model_data = []

    # Create ModelInfo objects from the loaded data
    raw_models: List[ModelInfo] = [ModelInfo(**model_data) for model_data in raw_model_data]

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
