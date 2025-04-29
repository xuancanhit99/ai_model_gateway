# app/services/model_router.py
from typing import Dict, Any, Tuple, List, Optional, AsyncGenerator, Set
import json
import re
from fastapi import HTTPException, status, UploadFile
import mimetypes
from supabase import Client # Thêm import Supabase Client
from app.services.gemini import GeminiService
from app.services.grok import GrokService
from app.services.gigachat import GigaChatService
from app.services.sonar import SonarService
from app.models.schemas import ChatMessage
import time
import uuid
import logging
from app.core.config import get_settings
from app.core.failover_utils import attempt_automatic_failover # Import hàm failover
from app.core.log_utils import log_activity_db # Import hàm log activity
from app.core.auth import get_encryption_key # Import only existing helper
from cryptography.fernet import Fernet # Import Fernet for decryption
import base64 # Import base64 for Fernet key encoding

settings = get_settings()
logger = logging.getLogger(__name__) # Thêm logger

class ModelRouter:
    """Lớp chịu trách nhiệm định tuyến các yêu cầu đến mô hình AI thích hợp."""

    @staticmethod
    def _strip_provider_prefix(model_id: str) -> str:
        """Removes provider prefix (e.g., 'google/', 'x-ai/', 'sber/', 'perplexity/') from model ID."""
        return re.sub(r"^(google|x-ai|sber|perplexity)/", "", model_id)

    @staticmethod
    def _determine_provider(model: str) -> str:
        """Determines the provider ('google', 'x-ai', 'gigachat', or 'perplexity') based on model name/prefix."""
        if not model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name must be specified.")

        if model.startswith("google/") or "gemini" in model.lower():
            return "google"
        elif model.startswith("x-ai/") or "grok" in model.lower():
            return "x-ai"
        elif model.startswith("sber/") or "gigachat" in model.lower():
            return "gigachat"
        elif model.startswith("perplexity/") or "sonar" in model.lower() or "r1-1776" in model.lower():
            return "perplexity"
        else:
            logger.error(f"Could not determine provider for model: {model}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not determine the provider for the requested model '{model}'. Supported models contain 'gemini', 'grok', 'gigachat', or 'sonar'."
            )

    @staticmethod
    async def route_vision_extraction(
        model: str,
        image_file: UploadFile,
        prompt: Optional[str],
        provider_api_keys: Dict[str, str] = None,
        supabase: Optional[Client] = None,
        auth_info: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Định tuyến yêu cầu vision extraction, hỗ trợ tự động failover API key liên tục.
        """
        if supabase is None or auth_info is None:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                 detail="Internal configuration error: Supabase client or Auth info missing for failover.")

        user_id = auth_info.get("user_id")
        if not user_id:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                 detail="Internal configuration error: User ID missing for failover.")

        provider_api_keys = provider_api_keys or {}
        logger.info(f"Routing vision extraction request for model: {model} with continuous failover")

        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)
        provider_name = ModelRouter._determine_provider(model) # google, x-ai
        provider_map = {"google": "google", "x-ai": "xai"} # Map logical name to key name
        provider_key_name = provider_map.get(provider_name)

        if not provider_key_name:
            logger.error(f"Provider '{provider_name}' determined for model '{model}' does not support vision tasks or mapping failed.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{model}' belongs to provider '{provider_name}' which does not support vision extraction or is not configured for failover."
            )

        # --- Lấy ID của key ban đầu ---
        initial_key_id: Optional[str] = None
        try:
            key_res = supabase.table("user_provider_keys").select("id") \
                .eq("user_id", user_id) \
                .eq("provider_name", provider_key_name) \
                .eq("is_selected", True) \
                .limit(1) \
                .maybe_single() \
                .execute()
            if key_res and key_res.data:
                initial_key_id = str(key_res.data['id'])
            else:
                logger.warning(f"Vision: No initial selected key found for user {user_id}, provider {provider_key_name}.")
        except Exception as e:
            logger.exception(f"Vision: Error fetching initial key ID for user {user_id}, provider {provider_key_name}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve initial key information for vision.")

        # --- Logic Gọi API và Failover ---
        current_api_key = provider_api_keys.get(provider_key_name)
        current_key_id = initial_key_id
        tried_key_ids: Set[str] = set()
        if current_key_id:
            tried_key_ids.add(current_key_id)

        if not current_api_key and initial_key_id:
             try:
                 key_db_res = supabase.table("user_provider_keys") \
                     .select("api_key_encrypted") \
                     .eq("id", initial_key_id) \
                     .eq("user_id", user_id) \
                     .maybe_single() \
                     .execute()
                 if key_db_res and key_db_res.data:
                     encrypted_key = key_db_res.data.get("api_key_encrypted")
                     if encrypted_key:
                         encryption_key = get_encryption_key()
                         f = Fernet(base64.urlsafe_b64encode(encryption_key))
                         current_api_key = f.decrypt(encrypted_key.encode()).decode()
                         logger.info(f"Vision: Successfully fetched and decrypted selected key {initial_key_id} from DB.")
                     else:
                         logger.error(f"Vision: Selected key {initial_key_id} found but has no encrypted key data.")
                 else:
                     logger.error(f"Vision: Could not fetch selected key {initial_key_id} details from DB.")
             except Exception as fetch_e:
                 logger.exception(f"Vision: Error fetching/decrypting selected key {initial_key_id}: {fetch_e}")

        # Vòng lặp failover liên tục
        while True:
            if not current_api_key or not current_key_id:
                logger.warning(f"Vision: No API key available at the start of this attempt. Attempting failover.")
                failover_start_key_id = current_key_id if current_key_id else f"no-key-yet-{uuid.uuid4()}"
                error_code = 400
                error_message = "Missing or failed to load API key"

                new_key_info = await attempt_automatic_failover(
                    user_id, provider_key_name, failover_start_key_id, error_code, error_message, supabase
                )

                if new_key_info:
                    next_key_id = new_key_info['id']
                    if next_key_id in tried_key_ids:
                        logger.error(f"Vision: Failover returned an already tried key ({next_key_id}). Exhausted.")
                        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="All available provider keys failed or are temporarily disabled (cycle detected).")
                    else:
                        current_key_id = next_key_id
                        current_api_key = new_key_info['api_key']
                        tried_key_ids.add(current_key_id)
                        logger.info(f"Vision: Failover selected initial/next key: {current_key_id}")
                else:
                    logger.error(f"Vision: Failover could not find any usable key for provider {provider_key_name}.")
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"No usable API key available for provider {provider_key_name}.")

            # --- Thực hiện gọi API với key hiện tại ---
            display_key_id = current_key_id if current_key_id else "unknown" # Sửa đổi để xử lý None
            logger.info(f"Vision Attempt: Calling provider {provider_key_name} with key_id {display_key_id}")
            try:
                await image_file.seek(0)
                image_bytes = await image_file.read()
                await image_file.seek(0)

                if provider_key_name == "google":
                    mime_type = image_file.content_type
                    if mime_type not in settings.GEMINI_ALLOWED_CONTENT_TYPES:
                        guessed_type, _ = mimetypes.guess_type(image_file.filename or "image.bin")
                        if guessed_type in settings.GEMINI_ALLOWED_CONTENT_TYPES:
                            mime_type = guessed_type
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                detail=f"Unsupported image type '{mime_type}' for Gemini. Allowed: {', '.join(settings.GEMINI_ALLOWED_CONTENT_TYPES)}"
                            )
                    service = GeminiService(api_key=current_api_key, model=base_model_name)
                    extracted_text, _ = await service.extract_text(image_data=image_bytes, content_type=mime_type, prompt=prompt)
                    logger.info(f"Vision: Successfully extracted text using key {display_key_id}")
                    return extracted_text, original_model_name

                elif provider_key_name == "xai":
                    service = GrokService(api_key=current_api_key)
                    await image_file.seek(0)
                    extracted_text, _ = await service.extract_text_from_image(image_file=image_file, model=base_model_name, prompt=prompt)
                    logger.info(f"Vision: Successfully extracted text using key {display_key_id}")
                    return extracted_text, original_model_name

                logger.error(f"Internal vision routing error after check: Unhandled provider '{provider_key_name}'")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during vision model routing.")

            # --- Xử lý lỗi và Failover ---
            except (HTTPException, ValueError) as e:
                logger.warning(f"Vision Attempt with key {display_key_id} failed - Type: {type(e).__name__}, Detail: {e}")
                error_code = 500
                error_message = str(e)
                is_key_error = False

                if isinstance(e, HTTPException):
                    error_code = e.status_code
                    error_message = e.detail
                    # Sửa đổi: Coi 400 từ 'xai' là lỗi key
                    is_key_error = error_code in [401, 403, 429] or \
                                   (error_code == 400 and ("API key" in str(error_message).lower() or "api key not valid" in str(error_message).lower())) or \
                                   (error_code == 415 and "API key" in str(error_message).lower()) or \
                                   (provider_key_name == "xai" and error_code == 400) # Thêm điều kiện cho Grok 400
                elif isinstance(e, ValueError):
                    if "API key not valid" in error_message.lower() or "invalid api key" in error_message.lower():
                        is_key_error = True
                        error_code = 401
                        logger.warning(f"Vision: Caught ValueError indicating invalid API key: {error_message}")
                    else:
                         logger.exception(f"Vision: Caught non-key ValueError: {e}")
                         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid value encountered: {e}")

                if is_key_error:
                    logger.warning(f"Vision Key error detected (Status: {error_code}) with key {display_key_id}. Attempting failover...")

                    # Cần ID của key vừa lỗi để failover_utils tìm key tiếp theo
                    failover_start_key_id_for_attempt = current_key_id # Có thể là None nếu key ban đầu lỗi và không có ID
                    if not failover_start_key_id_for_attempt:
                         logger.error(f"Vision: Cannot perform failover because the ID of the failed key is unknown (was likely missing initially).")
                         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Initial API key failed, and no key ID was available to initiate failover. Error: {error_code} - {error_message}")


                    new_key_info = await attempt_automatic_failover(
                        user_id, provider_key_name, failover_start_key_id_for_attempt, error_code, error_message, supabase
                    )

                    if new_key_info:
                        next_key_id = new_key_info['id']
                        if next_key_id in tried_key_ids:
                            logger.error(f"Vision: Failover returned an already tried key ({next_key_id}). Exhausted.")
                            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="All available provider keys failed or are temporarily disabled (cycle detected).")
                        else:
                            current_key_id = next_key_id
                            current_api_key = new_key_info['api_key']
                            tried_key_ids.add(current_key_id)
                            logger.info(f"Vision Failover successful. Trying next key_id: {current_key_id}")
                            continue # Quay lại đầu vòng lặp while để thử key mới
                    else:
                        logger.error(f"Vision Failover failed for user {user_id}, provider {provider_key_name}. All keys exhausted.")
                        log_key_id_on_exhaust = current_key_id # Log ID của key cuối cùng gây lỗi
                        if log_key_id_on_exhaust: # Chỉ log nếu có key ID
                            await log_activity_db(
                                user_id=user_id, provider_name=provider_key_name, key_id=log_key_id_on_exhaust,
                                action="FAILOVER_EXHAUSTED", details=f"All keys failed. Last error on this key: {error_code}",
                                supabase=supabase
                            )
                        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"All provider keys failed or are temporarily disabled. Last error: {error_code} - {error_message}")
                else:
                    logger.error(f"Vision: Non-key error encountered. Raising.")
                    raise e # Ném lỗi không phải key ra ngoài

            except Exception as e:
                 logger.exception(f"Vision: Unexpected error during API call with key {display_key_id}: {e}")
                 raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

        logger.error("Vision: Exited failover loop unexpectedly.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during vision failover process.")


    @staticmethod
    async def route_chat_completion(
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        provider_api_keys: Dict[str, str] = None,
        supabase: Optional[Client] = None,
        auth_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Định tuyến yêu cầu chat completion tới mô hình AI thích hợp,
        hỗ trợ tự động failover API key liên tục.
        """
        if supabase is None or auth_info is None:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                 detail="Internal configuration error: Supabase client or Auth info missing for failover.")

        user_id = auth_info.get("user_id")
        if not user_id:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                 detail="Internal configuration error: User ID missing for failover.")

        provider_api_keys = provider_api_keys or {}
        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)
        provider_name = ModelRouter._determine_provider(model)
        provider_map = {"google": "google", "x-ai": "xai", "gigachat": "gigachat", "perplexity": "perplexity"}
        provider_key_name = provider_map.get(provider_name)

        if not provider_key_name:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Could not map provider '{provider_name}' for model '{model}'")

        logger.info(f"Routing chat completion for model: {original_model_name} (Provider Key Name: {provider_key_name}, Base Model: {base_model_name})")

        # --- Lấy ID của key ban đầu ---
        initial_key_id: Optional[str] = None
        try:
            key_res = supabase.table("user_provider_keys").select("id") \
                .eq("user_id", user_id) \
                .eq("provider_name", provider_key_name) \
                .eq("is_selected", True) \
                .limit(1) \
                .maybe_single() \
                .execute()
            if key_res and key_res.data:
                initial_key_id = str(key_res.data['id'])
            else:
                logger.warning(f"Chat Completion: No initial selected key found for user {user_id}, provider {provider_key_name}.")
        except Exception as e:
            logger.exception(f"Chat Completion: Error fetching initial key ID for user {user_id}, provider {provider_key_name}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve initial key information.")

        # --- Logic Gọi API và Failover ---
        current_api_key = provider_api_keys.get(provider_key_name)
        current_key_id = initial_key_id
        tried_key_ids: Set[str] = set()
        if current_key_id:
            tried_key_ids.add(current_key_id)

        if not current_api_key and initial_key_id:
             try:
                 key_db_res = supabase.table("user_provider_keys") \
                     .select("api_key_encrypted") \
                     .eq("id", initial_key_id) \
                     .eq("user_id", user_id) \
                     .maybe_single() \
                     .execute()
                 if key_db_res and key_db_res.data:
                     encrypted_key = key_db_res.data.get("api_key_encrypted")
                     if encrypted_key:
                         encryption_key = get_encryption_key()
                         f = Fernet(base64.urlsafe_b64encode(encryption_key))
                         current_api_key = f.decrypt(encrypted_key.encode()).decode()
                         logger.info(f"Chat Completion: Successfully fetched and decrypted selected key {initial_key_id} from DB.")
                     else:
                         logger.error(f"Chat Completion: Selected key {initial_key_id} found but has no encrypted key data.")
                 else:
                     logger.error(f"Chat Completion: Could not fetch selected key {initial_key_id} details from DB.")
             except Exception as fetch_e:
                 logger.exception(f"Chat Completion: Error fetching/decrypting selected key {initial_key_id}: {fetch_e}")

        # Vòng lặp failover liên tục
        while True:
            if not current_api_key or not current_key_id:
                logger.warning(f"Chat Completion: No API key available at the start of this attempt. Attempting failover.")
                failover_start_key_id = current_key_id if current_key_id else f"no-key-yet-chat-{uuid.uuid4()}"
                error_code = 400
                error_message = "Missing or failed to load API key"

                new_key_info = await attempt_automatic_failover(
                    user_id, provider_key_name, failover_start_key_id, error_code, error_message, supabase
                )

                if new_key_info:
                    next_key_id = new_key_info['id']
                    if next_key_id in tried_key_ids:
                        logger.error(f"Chat Completion: Failover returned an already tried key ({next_key_id}). Exhausted.")
                        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="All available provider keys failed or are temporarily disabled (cycle detected).")
                    else:
                        current_key_id = next_key_id
                        current_api_key = new_key_info['api_key']
                        tried_key_ids.add(current_key_id)
                        logger.info(f"Chat Completion: Failover selected initial/next key: {current_key_id}")
                else:
                    logger.error(f"Chat Completion: Failover could not find any usable key for provider {provider_key_name}.")
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"No usable API key available for provider {provider_key_name}.")

            # --- Thực hiện gọi API ---
            display_key_id = current_key_id if current_key_id else "unknown"
            logger.info(f"Chat Completion Attempt: Calling provider {provider_key_name} with key_id {display_key_id}")
            try:
                if provider_key_name == "google":
                    prompt, history = ModelRouter._convert_messages(messages)
                    service = GeminiService(api_key=current_api_key, model=base_model_name)
                    response_text, _ = await service.generate_text_response(message=prompt, history=history, model=base_model_name)
                    if response_text is None: response_text = ""
                    elif not isinstance(response_text, str): response_text = str(response_text)
                    prompt_tokens = sum(len(msg.get("content", "").split()) for msg in messages if isinstance(msg.get("content"), str)) * 4 # Rough estimate
                    completion_tokens = len(response_text.split()) * 4 # Rough estimate
                    response_payload = {
                        "id": f"chatcmpl-gemini-{uuid.uuid4().hex}", "object": "chat.completion", "created": int(time.time()),
                        "model": original_model_name,
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
                    }
                    logger.info(f"Chat Completion: Success with key {display_key_id}")
                    return response_payload

                elif provider_key_name == "xai":
                    service = GrokService(api_key=current_api_key)
                    response_payload = await service.create_chat_completion(
                        model=base_model_name, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=False
                    )
                    response_payload["model"] = original_model_name
                    logger.info(f"Chat Completion: Success with key {display_key_id}")
                    return response_payload

                elif provider_key_name == "gigachat":
                    service = GigaChatService(auth_key=current_api_key)
                    response_payload = await service.create_chat_completion(
                        model=base_model_name, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=False
                    )
                    response_payload["model"] = original_model_name
                    logger.info(f"Chat Completion: Success with key {display_key_id}")
                    return response_payload

                elif provider_key_name == "perplexity":
                    service = SonarService(api_key=current_api_key, model=base_model_name)
                    response_payload = await service.create_chat_completion(
                        messages=messages, model=base_model_name, temperature=temperature, max_tokens=max_tokens, stream=False
                    )
                    response_payload["model"] = original_model_name
                    logger.info(f"Chat Completion: Success with key {display_key_id}")
                    return response_payload

                else:
                    logger.error(f"Internal routing error: Unhandled provider key name '{provider_key_name}'")
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during model routing.")

            # --- Xử lý lỗi và Failover ---
            except (HTTPException, ValueError) as e:
                logger.warning(f"Chat Completion Attempt with key {display_key_id} failed - Type: {type(e).__name__}, Detail: {e}")
                error_code = 500
                error_message = str(e)
                is_key_error = False

                if isinstance(e, HTTPException):
                    error_code = e.status_code
                    error_message = e.detail
                    # Sửa đổi: Coi 400 từ 'xai' là lỗi key
                    is_key_error = error_code in [401, 403, 429] or \
                                   (error_code == 400 and ("API key" in str(error_message).lower() or "api key not valid" in str(error_message).lower())) or \
                                   (provider_key_name == "xai" and error_code == 400) # Thêm điều kiện cho Grok 400
                elif isinstance(e, ValueError):
                    if "API key not valid" in error_message.lower() or "invalid api key" in error_message.lower():
                        is_key_error = True
                        error_code = 401
                        logger.warning(f"Chat Completion: Caught ValueError indicating invalid API key: {error_message}")
                    else:
                         logger.exception(f"Chat Completion: Caught non-key ValueError: {e}")
                         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid value encountered: {e}")

                if is_key_error:
                    logger.warning(f"Chat Completion Key error detected (Status: {error_code}) with key {display_key_id}. Attempting failover...")

                    failover_start_key_id_for_attempt = current_key_id
                    if not failover_start_key_id_for_attempt:
                         logger.error(f"Chat Completion: Cannot perform failover because the ID of the failed key is unknown.")
                         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Initial API key failed, and no key ID was available to initiate failover. Error: {error_code} - {error_message}")

                    new_key_info = await attempt_automatic_failover(
                        user_id, provider_key_name, failover_start_key_id_for_attempt, error_code, error_message, supabase
                    )

                    if new_key_info:
                        next_key_id = new_key_info['id']
                        if next_key_id in tried_key_ids:
                            logger.error(f"Chat Completion: Failover returned an already tried key ({next_key_id}). Exhausted.")
                            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="All available provider keys failed or are temporarily disabled (cycle detected).")
                        else:
                            current_key_id = next_key_id
                            current_api_key = new_key_info['api_key']
                            tried_key_ids.add(current_key_id)
                            logger.info(f"Chat Completion Failover successful. Trying next key_id: {current_key_id}")
                            continue
                    else:
                        logger.error(f"Chat Completion Failover failed for user {user_id}, provider {provider_key_name}. All keys exhausted.")
                        log_key_id_on_exhaust = current_key_id
                        if log_key_id_on_exhaust:
                            await log_activity_db(
                                user_id=user_id, provider_name=provider_key_name, key_id=log_key_id_on_exhaust,
                                action="FAILOVER_EXHAUSTED", details=f"All keys failed. Last error on this key: {error_code}",
                                supabase=supabase
                            )
                        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"All provider keys failed or are temporarily disabled. Last error: {error_code} - {error_message}")
                else:
                    logger.error(f"Chat Completion: Non-key error encountered. Raising.")
                    raise e

            except Exception as e:
                 logger.exception(f"Chat Completion: Unexpected error during API call with key {display_key_id}: {e}")
                 raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

        logger.error("Chat Completion: Exited failover loop unexpectedly.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during chat completion failover process.")


    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]) -> Tuple[str, List[ChatMessage]]:
        """
        Chuyển đổi từ định dạng tin nhắn OpenAI sang định dạng Gemini.
        """
        history = []
        system_message = None

        if not messages:
            return "", []

        valid_messages = [m for m in messages if isinstance(m.get("content"), str) and m.get("role")]

        if not valid_messages:
            return "", []

        for msg in valid_messages:
            if msg["role"] == "system":
                system_message = msg["content"]
                break

        processed_indices = set()
        if system_message:
            for i, msg in enumerate(valid_messages):
                if msg["role"] == "system":
                    processed_indices.add(i)
                    break

        last_user_message_index = -1
        for i in range(len(valid_messages) - 1, -1, -1):
            if valid_messages[i]["role"] == "user":
                last_user_message_index = i
                break

        if last_user_message_index == -1:
            logger.warning("No user message found to form the prompt for Gemini.")
            return "", []

        prompt: str
        last_user_msg = valid_messages[last_user_message_index]
        prompt_content = last_user_msg["content"]
        if system_message:
            prompt = f"{system_message}\n\n{prompt_content}"
        else:
            prompt = prompt_content
        processed_indices.add(last_user_message_index)

        for i, msg in enumerate(valid_messages):
            if i not in processed_indices and msg["role"] != "system":
                gemini_role = "user" if msg["role"] == "user" else "model"
                history.append(ChatMessage(role=gemini_role, content=msg["content"]))

        final_history = []
        last_role = None
        for h_msg in history:
            if h_msg.role != last_role:
                final_history.append(h_msg)
                last_role = h_msg.role
            else:
                logger.warning(f"Skipping message due to consecutive roles in history for Gemini: {h_msg.role}")

        return prompt, final_history

    @staticmethod
    def _convert_simple_to_openai(message: str, history: List[ChatMessage]) -> List[Dict[str, str]]:
        """Converts simple message/history to OpenAI message list."""
        openai_messages = []
        for msg in history:
            role = "assistant" if msg.role == "model" else msg.role
            openai_messages.append({"role": role, "content": msg.content})
        openai_messages.append({"role": "user", "content": message})
        return openai_messages

    @staticmethod
    async def route_simple_chat(
        model: str,
        message: str,
        history: List[ChatMessage],
        provider_api_keys: Dict[str, str] = None,
        supabase: Optional[Client] = None,
        auth_info: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """Định tuyến yêu cầu simple chat, hỗ trợ tự động failover API key liên tục."""
        if supabase is None or auth_info is None:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                 detail="Internal configuration error: Supabase client or Auth info missing for failover.")

        user_id = auth_info.get("user_id")
        if not user_id:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                 detail="Internal configuration error: User ID missing for failover.")

        provider_api_keys = provider_api_keys or {}
        logger.info(f"Routing simple chat request for model: {model} with continuous failover")

        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)
        provider_name = ModelRouter._determine_provider(model)
        provider_map = {"google": "google", "x-ai": "xai", "gigachat": "gigachat", "perplexity": "perplexity"}
        provider_key_name = provider_map.get(provider_name)

        if not provider_key_name:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Could not map provider '{provider_name}' for simple chat model '{model}'")

        # --- Lấy ID của key ban đầu ---
        initial_key_id: Optional[str] = None
        try:
            key_res = supabase.table("user_provider_keys").select("id") \
                .eq("user_id", user_id) \
                .eq("provider_name", provider_key_name) \
                .eq("is_selected", True) \
                .limit(1) \
                .maybe_single() \
                .execute()
            if key_res and key_res.data:
                initial_key_id = str(key_res.data['id'])
            else:
                logger.warning(f"Simple Chat: No initial selected key found for user {user_id}, provider {provider_key_name}.")
        except Exception as e:
            logger.exception(f"Simple Chat: Error fetching initial key ID for user {user_id}, provider {provider_key_name}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve initial key information for simple chat.")

        # --- Logic Gọi API và Failover ---
        current_api_key = provider_api_keys.get(provider_key_name)
        current_key_id = initial_key_id
        tried_key_ids: Set[str] = set()
        if current_key_id:
            tried_key_ids.add(current_key_id)

        if not current_api_key and initial_key_id:
             try:
                 key_db_res = supabase.table("user_provider_keys") \
                     .select("api_key_encrypted") \
                     .eq("id", initial_key_id) \
                     .eq("user_id", user_id) \
                     .maybe_single() \
                     .execute()
                 if key_db_res and key_db_res.data:
                     encrypted_key = key_db_res.data.get("api_key_encrypted")
                     if encrypted_key:
                         encryption_key = get_encryption_key()
                         f = Fernet(base64.urlsafe_b64encode(encryption_key))
                         current_api_key = f.decrypt(encrypted_key.encode()).decode()
                         logger.info(f"Simple Chat: Successfully fetched and decrypted selected key {initial_key_id} from DB.")
                     else:
                         logger.error(f"Simple Chat: Selected key {initial_key_id} found but has no encrypted key data.")
                 else:
                     logger.error(f"Simple Chat: Could not fetch selected key {initial_key_id} details from DB.")
             except Exception as fetch_e:
                 logger.exception(f"Simple Chat: Error fetching/decrypting selected key {initial_key_id}: {fetch_e}")

        # Vòng lặp failover liên tục
        while True:
            if not current_api_key or not current_key_id:
                logger.warning(f"Simple Chat: No API key available at the start of this attempt. Attempting failover.")
                failover_start_key_id = current_key_id if current_key_id else f"no-key-yet-simple-{uuid.uuid4()}"
                error_code = 400
                error_message = "Missing or failed to load API key"

                new_key_info = await attempt_automatic_failover(
                    user_id, provider_key_name, failover_start_key_id, error_code, error_message, supabase
                )

                if new_key_info:
                    next_key_id = new_key_info['id']
                    if next_key_id in tried_key_ids:
                        logger.error(f"Simple Chat: Failover returned an already tried key ({next_key_id}). Exhausted.")
                        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="All available provider keys failed or are temporarily disabled (cycle detected).")
                    else:
                        current_key_id = next_key_id
                        current_api_key = new_key_info['api_key']
                        tried_key_ids.add(current_key_id)
                        logger.info(f"Simple Chat: Failover selected initial/next key: {current_key_id}")
                else:
                    logger.error(f"Simple Chat: Failover could not find any usable key for provider {provider_key_name}.")
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"No usable API key available for provider {provider_key_name}.")

            # --- Thực hiện gọi API ---
            display_key_id = current_key_id if current_key_id else "unknown"
            logger.info(f"Simple Chat Attempt: Calling provider {provider_key_name} with key_id {display_key_id}")
            try:
                if provider_key_name == "google":
                    service = GeminiService(api_key=current_api_key, model=base_model_name)
                    response_text, _ = await service.generate_text_response(message=message, history=history, model=base_model_name)
                    if response_text is None: response_text = ""
                    elif not isinstance(response_text, str): response_text = str(response_text)
                    logger.info(f"Simple Chat: Success with key {display_key_id}")
                    return response_text, original_model_name

                elif provider_key_name == "xai":
                    service = GrokService(api_key=current_api_key)
                    openai_messages = ModelRouter._convert_simple_to_openai(message, history)
                    response_payload = await service.create_chat_completion(model=base_model_name, messages=openai_messages, stream=False)
                    response_text = response_payload.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.info(f"Simple Chat: Success with key {display_key_id}")
                    return response_text, original_model_name

                elif provider_key_name == "gigachat":
                    service = GigaChatService(auth_key=current_api_key)
                    openai_messages = ModelRouter._convert_simple_to_openai(message, history)
                    response_payload = await service.create_chat_completion(model=base_model_name, messages=openai_messages, stream=False)
                    response_text = response_payload.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.info(f"Simple Chat: Success with key {display_key_id}")
                    return response_text, original_model_name

                elif provider_key_name == "perplexity":
                    service = SonarService(api_key=current_api_key, model=base_model_name)
                    response_text, _ = await service.generate_text_response(message=message, history=history, model=base_model_name)
                    if response_text is None: response_text = ""
                    elif not isinstance(response_text, str): response_text = str(response_text)
                    logger.info(f"Simple Chat: Success with key {display_key_id}")
                    return response_text, original_model_name

                logger.error(f"Internal simple chat routing error after check: Unhandled provider '{provider_key_name}'")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during simple chat model routing.")

            # --- Xử lý lỗi và Failover ---
            except (HTTPException, ValueError) as e:
                logger.warning(f"Simple Chat Attempt with key {display_key_id} failed - Type: {type(e).__name__}, Detail: {e}")
                error_code = 500
                error_message = str(e)
                is_key_error = False

                if isinstance(e, HTTPException):
                    error_code = e.status_code
                    error_message = e.detail
                    # Sửa đổi: Coi 400 từ 'xai' là lỗi key
                    is_key_error = error_code in [401, 403, 429] or \
                                   (error_code == 400 and ("API key" in str(error_message).lower() or "api key not valid" in str(error_message).lower())) or \
                                   (provider_key_name == "xai" and error_code == 400) # Thêm điều kiện cho Grok 400
                elif isinstance(e, ValueError):
                    if "API key not valid" in error_message.lower() or "invalid api key" in error_message.lower():
                        is_key_error = True
                        error_code = 401
                        logger.warning(f"Simple Chat: Caught ValueError indicating invalid API key: {error_message}")
                    else:
                         logger.exception(f"Simple Chat: Caught non-key ValueError: {e}")
                         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid value encountered: {e}")

                if is_key_error:
                    logger.warning(f"Simple Chat Key error detected (Status: {error_code}) with key {display_key_id}. Attempting failover...")

                    failover_start_key_id_for_attempt = current_key_id
                    if not failover_start_key_id_for_attempt:
                         logger.error(f"Simple Chat: Cannot perform failover because the ID of the failed key is unknown.")
                         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Initial API key failed, and no key ID was available to initiate failover. Error: {error_code} - {error_message}")

                    new_key_info = await attempt_automatic_failover(
                        user_id, provider_key_name, failover_start_key_id_for_attempt, error_code, error_message, supabase
                    )

                    if new_key_info:
                        next_key_id = new_key_info['id']
                        if next_key_id in tried_key_ids:
                            logger.error(f"Simple Chat: Failover returned an already tried key ({next_key_id}). Exhausted.")
                            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="All available provider keys failed or are temporarily disabled (cycle detected).")
                        else:
                            current_key_id = next_key_id
                            current_api_key = new_key_info['api_key']
                            tried_key_ids.add(current_key_id)
                            logger.info(f"Simple Chat Failover successful. Trying next key_id: {current_key_id}")
                            continue
                    else:
                        logger.error(f"Simple Chat Failover failed for user {user_id}, provider {provider_key_name}. All keys exhausted.")
                        log_key_id_on_exhaust = current_key_id
                        if log_key_id_on_exhaust:
                            await log_activity_db(
                                user_id=user_id, provider_name=provider_key_name, key_id=log_key_id_on_exhaust,
                                action="FAILOVER_EXHAUSTED", details=f"All keys failed. Last error on this key: {error_code}",
                                supabase=supabase
                            )
                        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"All provider keys failed or are temporarily disabled. Last error: {error_code} - {error_message}")
                else:
                    logger.error(f"Simple Chat: Non-key error encountered. Raising.")
                    raise e

            except Exception as e:
                 logger.exception(f"Simple Chat: Unexpected error during API call with key {display_key_id}: {e}")
                 raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

        logger.error("Simple Chat: Exited failover loop unexpectedly.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during simple chat failover process.")


    @staticmethod
    async def stream_chat_completion(
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        provider_api_keys: Dict[str, str] = None,
        supabase: Optional[Client] = None,
        auth_info: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Định tuyến và stream yêu cầu chat completion, hỗ trợ failover liên tục.
        Yields Server-Sent Events (SSE) formatted strings.
        """
        if supabase is None or auth_info is None:
             error_payload = {"error": {"message": "Internal configuration error: Supabase client or Auth info missing for failover.", "type": "internal_server_error", "code": 500}}
             yield f"data: {json.dumps(error_payload)}\n\n"
             yield "data: [DONE]\n\n"
             return

        user_id = auth_info.get("user_id")
        if not user_id:
             error_payload = {"error": {"message": "Internal configuration error: User ID missing for failover.", "type": "internal_server_error", "code": 500}}
             yield f"data: {json.dumps(error_payload)}\n\n"
             yield "data: [DONE]\n\n"
             return

        provider_api_keys = provider_api_keys or {}
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_time = int(time.time())
        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)

        try:
            provider_name = ModelRouter._determine_provider(model)
            provider_map = {"google": "google", "x-ai": "xai", "gigachat": "gigachat", "perplexity": "perplexity"}
            provider_key_name = provider_map.get(provider_name)
            if not provider_key_name:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Could not map provider '{provider_name}' for model '{model}'")
        except HTTPException as e:
            logger.warning(f"Streaming requested for model with unknown provider: {model} - Error: {e.detail}")
            error_payload = {"error": {"message": e.detail, "type": "invalid_request_error", "code": e.status_code}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
            return

        logger.info(f"Routing stream request for model: {original_model_name} (Provider Key Name: {provider_key_name}, Base Model: {base_model_name})")

        # --- Lấy ID của key ban đầu ---
        initial_key_id: Optional[str] = None
        try:
            key_res = supabase.table("user_provider_keys").select("id") \
                .eq("user_id", user_id) \
                .eq("provider_name", provider_key_name) \
                .eq("is_selected", True) \
                .limit(1) \
                .maybe_single() \
                .execute()
            if key_res and key_res.data:
                initial_key_id = str(key_res.data['id'])
            else:
                logger.warning(f"Stream: No initial selected key found for user {user_id}, provider {provider_key_name}.")
        except Exception as e:
            logger.exception(f"Stream: Error fetching initial key ID for user {user_id}, provider {provider_key_name}: {e}")
            error_payload = {"error": {"message": "Failed to retrieve initial key information.", "type": "internal_server_error", "code": 500}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # --- Logic Gọi API Stream và Failover ---
        current_api_key = provider_api_keys.get(provider_key_name)
        current_key_id = initial_key_id
        tried_key_ids: Set[str] = set()
        if current_key_id:
            tried_key_ids.add(current_key_id)

        if not current_api_key and initial_key_id:
            logger.warning(f"Stream: No API key found in initial request dict for provider {provider_key_name}. Checking DB for selected key ID: {initial_key_id}")
            try:
                key_db_res = supabase.table("user_provider_keys") \
                    .select("api_key_encrypted") \
                    .eq("id", initial_key_id) \
                    .eq("user_id", user_id) \
                    .maybe_single() \
                    .execute()
                if key_db_res and key_db_res.data:
                    encrypted_key = key_db_res.data.get("api_key_encrypted")
                    if encrypted_key:
                        try:
                            encryption_key = get_encryption_key()
                            f = Fernet(base64.urlsafe_b64encode(encryption_key))
                            current_api_key = f.decrypt(encrypted_key.encode()).decode()
                            logger.info(f"Stream: Successfully fetched and decrypted selected key {initial_key_id} from DB.")
                        except Exception as decrypt_e:
                            logger.exception(f"Stream: Failed to decrypt the selected key {initial_key_id} from DB: {decrypt_e}")
                    else:
                        logger.error(f"Stream: Selected key {initial_key_id} found in DB but has no encrypted key data.")
                else:
                    logger.error(f"Stream: Could not fetch the selected key {initial_key_id} details from DB.")
            except Exception as fetch_e:
                logger.exception(f"Stream: Error fetching selected key {initial_key_id} details from DB: {fetch_e}")

        # Vòng lặp failover liên tục
        stream_successful = False
        while True:
            service_stream: Optional[AsyncGenerator[str, None]] = None
            stream_error = None

            if not current_api_key or not current_key_id:
                logger.warning(f"Stream: No API key available at the start of this attempt. Attempting failover.")
                failover_start_key_id = current_key_id if current_key_id else f"no-key-yet-stream-{uuid.uuid4()}"
                error_code = 400
                error_message = "Missing or failed to load API key"

                new_key_info = await attempt_automatic_failover(
                    user_id, provider_key_name, failover_start_key_id, error_code, error_message, supabase
                )

                if new_key_info:
                    next_key_id = new_key_info['id']
                    if next_key_id in tried_key_ids:
                        logger.error(f"Stream: Failover returned an already tried key ({next_key_id}). Exhausted.")
                        error_payload = {"error": {"message": "All available provider keys failed or are temporarily disabled (cycle detected).", "type": "service_unavailable", "code": 503}}
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    else:
                        current_key_id = next_key_id
                        current_api_key = new_key_info['api_key']
                        tried_key_ids.add(current_key_id)
                        logger.info(f"Stream: Failover selected initial/next key: {current_key_id}")
                else:
                    logger.error(f"Stream: Failover could not find any usable key for provider {provider_key_name}.")
                    error_payload = {"error": {"message": f"No usable API key available for provider {provider_key_name}.", "type": "service_unavailable", "code": 503}}
                    yield f"data: {json.dumps(error_payload)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            # --- Thực hiện gọi API Stream ---
            display_key_id = current_key_id if current_key_id else "unknown"
            logger.info(f"Stream Attempt: Calling provider {provider_key_name} with key_id {display_key_id}")
            try:
                # --- Setup Service Stream ---
                if provider_key_name == "google":
                    prompt, history = ModelRouter._convert_messages(messages)
                    service = GeminiService(api_key=current_api_key, model=base_model_name)
                    first_chunk = True
                    async def google_sse_wrapper():
                        nonlocal first_chunk, stream_error
                        try:
                            async for chunk_text in service.stream_text_response(message=prompt, history=history, model=base_model_name):
                                if chunk_text is None: continue
                                chunk_payload = {
                                    "id": request_id, "object": "chat.completion.chunk", "created": created_time,
                                    "model": original_model_name,
                                    "choices": [{"index": 0, "delta": {}, "finish_reason": None}]
                                }
                                if first_chunk:
                                    chunk_payload["choices"][0]["delta"]["role"] = "assistant"
                                    first_chunk = False
                                chunk_payload["choices"][0]["delta"]["content"] = chunk_text
                                yield f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n"
                            final_chunk_payload = {
                                "id": request_id, "object": "chat.completion.chunk", "created": created_time,
                                "model": original_model_name,
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                            }
                            yield f"data: {json.dumps(final_chunk_payload, ensure_ascii=False)}\n\n"
                        except (HTTPException, ValueError) as gemini_e:
                             logger.error(f"Error within Gemini stream wrapper: {type(gemini_e).__name__} - {gemini_e}")
                             stream_error = gemini_e
                        except Exception as gemini_e:
                             logger.exception("Unexpected error within Gemini stream wrapper")
                             stream_error = HTTPException(status_code=500, detail=f"Unexpected Gemini stream error: {gemini_e}")
                    service_stream = google_sse_wrapper()

                elif provider_key_name == "xai":
                    service = GrokService(api_key=current_api_key)
                    service_stream = service.stream_chat_completion(model=base_model_name, messages=messages, temperature=temperature, max_tokens=max_tokens)

                elif provider_key_name == "gigachat":
                    service = GigaChatService(auth_key=current_api_key)
                    service_stream = service.stream_chat_completion(model=base_model_name, messages=messages, temperature=temperature, max_tokens=max_tokens)

                elif provider_key_name == "perplexity":
                    service = SonarService(api_key=current_api_key, model=base_model_name)
                    service_stream = service.stream_chat_completion(messages=messages, model=base_model_name, temperature=temperature, max_tokens=max_tokens)

                else:
                     logger.error(f"Internal streaming routing error: Unhandled provider key name '{provider_key_name}'")
                     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during streaming model routing.")

                # --- Iterate through the stream ---
                if not service_stream:
                     raise HTTPException(status_code=500, detail="Failed to initialize provider service stream.")

                logger.info(f"Stream Attempt: Entering stream iteration...")
                async for chunk in service_stream:
                    yield chunk
                logger.info(f"Stream Attempt: Stream iteration finished.")

                if stream_error:
                     raise stream_error

                stream_successful = True
                logger.info(f"--- Stream completed successfully with key {display_key_id}. ---")
                yield "data: [DONE]\n\n"
                return

            # --- Xử lý lỗi và Failover ---
            except (HTTPException, ValueError) as e:
                logger.warning(f"Stream Attempt with key {display_key_id} failed - Type: {type(e).__name__}, Detail: {e}")
                error_code = 500
                error_message = str(e)
                is_key_error = False

                if isinstance(e, HTTPException):
                    error_code = e.status_code
                    error_message = e.detail
                    # Sửa đổi: Coi 400 từ 'xai' là lỗi key
                    is_key_error = error_code in [401, 403, 429] or \
                                   (error_code == 400 and ("API key" in str(error_message).lower() or "api key not valid" in str(error_message).lower())) or \
                                   (provider_key_name == "xai" and error_code == 400) # Thêm điều kiện cho Grok 400
                elif isinstance(e, ValueError):
                    if "API key not valid" in error_message.lower() or "invalid api key" in error_message.lower():
                        is_key_error = True
                        error_code = 401
                        logger.warning(f"Stream: Caught ValueError indicating invalid API key: {error_message}")
                    else:
                        logger.exception(f"Stream: Caught non-key ValueError: {e}")
                        error_payload = {"error": {"message": f"Invalid value encountered during stream: {e}", "type": "invalid_request_error", "code": 400}}
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                if is_key_error:
                    logger.warning(f"Stream Key error detected (Status: {error_code}) with key {display_key_id}. Attempting failover...")

                    failover_start_key_id_for_attempt = current_key_id
                    if not failover_start_key_id_for_attempt:
                         logger.error(f"Stream: Cannot perform failover because the ID of the failed key is unknown.")
                         error_payload = {"error": {"message": f"Initial API key failed, and no key ID was available to initiate failover. Error: {error_code} - {error_message}", "type": "service_unavailable", "code": 503}}
                         yield f"data: {json.dumps(error_payload)}\n\n"
                         yield "data: [DONE]\n\n"
                         return

                    new_key_info = await attempt_automatic_failover(
                        user_id, provider_key_name, failover_start_key_id_for_attempt, error_code, error_message, supabase
                    )

                    if new_key_info:
                        next_key_id = new_key_info['id']
                        if next_key_id in tried_key_ids:
                            logger.error(f"Stream: Failover returned an already tried key ({next_key_id}). Exhausted.")
                            error_payload = {"error": {"message": "All available provider keys failed or are temporarily disabled (cycle detected).", "type": "service_unavailable", "code": 503}}
                            yield f"data: {json.dumps(error_payload)}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        else:
                            current_key_id = next_key_id
                            current_api_key = new_key_info['api_key']
                            tried_key_ids.add(current_key_id)
                            logger.info(f"Stream Failover successful. Trying next key_id: {current_key_id}")
                            continue
                    else:
                        logger.error(f"Stream Failover failed for user {user_id}, provider {provider_key_name}. All keys exhausted.")
                        log_key_id_on_exhaust = current_key_id
                        if log_key_id_on_exhaust:
                            await log_activity_db(
                                user_id=user_id, provider_name=provider_key_name, key_id=log_key_id_on_exhaust,
                                action="FAILOVER_EXHAUSTED", details=f"All keys failed. Last error on this key: {error_code}",
                                supabase=supabase
                            )
                        error_payload = {"error": {"message": f"All provider keys failed or are temporarily disabled for {provider_key_name}. Last error: {error_code} - {error_message}", "type": "service_unavailable", "code": 503}}
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                else:
                    logger.error(f"Stream: Non-key error encountered. Sending error event.")
                    final_error_code = error_code if error_code != 500 else 503
                    error_payload = {"error": {"message": f"Error during streaming: {error_message}", "type": "api_error", "code": final_error_code}}
                    yield f"data: {json.dumps(error_payload)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            except Exception as e:
                 logger.exception(f"Stream: Unexpected error during API call with key {display_key_id}: {e}")
                 error_payload = {"error": {"message": f"An unexpected error occurred during stream: {e}", "type": "internal_server_error", "code": 500}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
                 yield "data: [DONE]\n\n"
                 return

        logger.error("Stream loop exited without success flag set and without returning an error.")
        error_payload = {"error": {"message": "Internal server error: Stream ended unexpectedly.", "type": "internal_server_error", "code": 500}}
        yield f"data: {json.dumps(error_payload)}\n\n"
        yield "data: [DONE]\n\n"