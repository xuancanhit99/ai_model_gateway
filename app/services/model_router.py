# app/services/model_router.py
from typing import Dict, Any, Tuple, List, Optional, AsyncGenerator
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
from app.core.log_utils import log_activity_db # Import hàm log activity (đã đổi tên)
from app.core.auth import get_encryption_key # Import only existing helper
from cryptography.fernet import Fernet # Import Fernet for decryption
import base64 # Import base64 for Fernet key encoding

settings = get_settings()

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
            logging.error(f"Could not determine provider for model: {model}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not determine the provider for the requested model '{model}'. Supported models contain 'gemini', 'grok', 'gigachat', or 'sonar'."
            )

    @staticmethod
    async def route_vision_extraction(
        model: str,
        image_file: UploadFile,
        prompt: Optional[str],
        provider_api_keys: Dict[str, str] = None
    ) -> Tuple[str, str]:
        """
        Routes vision extraction requests to the appropriate model (Gemini or Grok).

        Args:
            model: The requested model name (e.g., 'google/gemini-pro-vision', 'x-ai/grok-vision').
            image_file: The uploaded image file.
            prompt: Optional custom prompt for extraction.
            provider_api_keys: Dictionary containing API keys ('google', 'grok').

        Returns:
            Tuple of (extracted_text, model_used)
        """
        provider_api_keys = provider_api_keys or {}
        logging.info(f"Routing vision extraction request for model: {model}")

        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)
        provider = ModelRouter._determine_provider(model)

        if provider not in ["google", "x-ai"]:
            logging.error(f"Provider '{provider}' determined for model '{model}' does not support vision tasks.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{model}' belongs to provider '{provider}' which does not support vision extraction."
            )

        if provider == "google":
            api_key = provider_api_keys.get("google")
            try:
                image_bytes = await image_file.read()
                await image_file.seek(0)

                mime_type = image_file.content_type
                if mime_type not in settings.GEMINI_ALLOWED_CONTENT_TYPES:
                    guessed_type, _ = mimetypes.guess_type(image_file.filename or "image.bin")
                    if guessed_type in settings.GEMINI_ALLOWED_CONTENT_TYPES:
                        mime_type = guessed_type
                    else:
                        logging.error(f"Unsupported image type '{mime_type}' for Gemini.")
                        raise HTTPException(
                            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail=f"Unsupported image type '{mime_type}' for Gemini. Allowed: {', '.join(settings.GEMINI_ALLOWED_CONTENT_TYPES)}"
                        )

                service = GeminiService(api_key=api_key, model=base_model_name)
                extracted_text, model_used_by_service = await service.extract_text(
                    image_data=image_bytes,  # Changed keyword argument name
                    content_type=mime_type,
                    prompt=prompt
                )
                return extracted_text, original_model_name

            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing Gemini vision request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing vision request with Gemini: {e}")

        elif provider == "x-ai":
            api_key = provider_api_keys.get("xai") # Changed "grok" to "xai"
            try:
                service = GrokService(api_key=api_key)
                extracted_text, model_used_by_service = await service.extract_text_from_image(
                    image_file=image_file,
                    model=base_model_name,
                    prompt=prompt
                )
                return extracted_text, original_model_name

            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Grok API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing Grok vision request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing vision request with Grok: {e}")

        logging.error(f"Internal vision routing error: Unhandled provider '{provider}' for model '{original_model_name}'")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during vision model routing.")

    @staticmethod
    async def route_chat_completion(
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        provider_api_keys: Dict[str, str] = None,
        # Thêm các tham số cần thiết cho failover
        supabase: Optional[Client] = None,
        auth_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Định tuyến yêu cầu chat completion tới mô hình AI thích hợp,
        hỗ trợ tự động failover API key.

        Args:
            model: Tên mô hình (ví dụ: "google/gemini-2.5-pro-exp-03-25")
            messages: Danh sách các tin nhắn từ request
            temperature: Nhiệt độ cho quá trình sinh văn bản
            max_tokens: Số lượng token tối đa cho phản hồi
            provider_api_keys: Dict chứa API key ban đầu (đã được chọn is_selected=True).
            supabase: Supabase client instance.
            auth_info: Dict chứa thông tin xác thực ('user_id', 'key_prefix', 'provider_keys', 'token').

        Returns:
            Phản hồi theo định dạng OpenAI.

        Raises:
            HTTPException: 503 nếu tất cả các key của provider đều lỗi.
                           Các lỗi khác nếu có vấn đề không liên quan đến key.
        """
        if supabase is None or auth_info is None:
             # Cần có supabase và auth_info để thực hiện failover
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                 detail="Internal configuration error: Supabase client or Auth info missing for failover.")

        user_id = auth_info.get("user_id")
        auth_token = auth_info.get("token") # Lấy token từ auth_info
        if not user_id or not auth_token:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                 detail="Internal configuration error: User ID or Auth token missing for failover.")

        provider_api_keys = provider_api_keys or {}
        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)
        provider_map = {"google": "google", "x-ai": "xai", "sber": "gigachat", "perplexity": "perplexity"} # Changed "grok" to "xai"
        provider_key_name = provider_map.get(ModelRouter._determine_provider(model)) # Tên key trong dict (google, xai, gigachat, perplexity)

        if not provider_key_name:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Could not map provider for model '{model}'")

        logging.info(f"Routing chat completion for model: {original_model_name} (Provider Key Name: {provider_key_name}, Base Model: {base_model_name})")

        # --- Lấy ID của key ban đầu ---
        initial_key_id: Optional[str] = None
        try:
            # Cần lấy ID của key đang is_selected=True cho provider này
            # Xóa await ở đây
            key_res = supabase.table("user_provider_keys").select("id") \
                .eq("user_id", user_id) \
                .eq("provider_name", provider_key_name) \
                .eq("is_selected", True) \
                .limit(1) \
                .maybe_single() \
                .execute()
            if key_res.data:
                initial_key_id = str(key_res.data['id'])
            else:
                logging.warning(f"No initial selected key found for user {user_id}, provider {provider_key_name}. Using provided key without failover ID.")
                # Nếu không có key nào được chọn, failover sẽ không hoạt động đúng cách
                # nhưng vẫn thử gọi API với key được cung cấp (nếu có)
        except Exception as e:
            logging.exception(f"Error fetching initial key ID for user {user_id}, provider {provider_key_name}: {e}")
            # Không thể lấy ID key ban đầu, không thể thực hiện failover chính xác
            # Ném lỗi hoặc tiếp tục mà không có failover? -> Ném lỗi để rõ ràng
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve initial key information.")

        # --- Logic Gọi API và Failover ---
        current_api_key = provider_api_keys.get(provider_key_name)
        current_key_id = initial_key_id

        if not current_api_key:
             # Nếu không có key nào được chọn ban đầu và truyền vào
             logging.error(f"No initial API key provided or selected for provider {provider_key_name}")
             # Thử gọi failover ngay lập tức để tìm key khác nếu có
             if initial_key_id: # Chỉ gọi failover nếu biết key nào (không) được chọn
                 new_key_info = await attempt_automatic_failover(
                     user_id, provider_key_name, initial_key_id, 404, "No initial key selected", supabase
                 )
                 if new_key_info:
                     current_key_id = new_key_info['id']
                     current_api_key = new_key_info['api_key']
                     logging.info(f"Failover selected initial key: {current_key_id}")
                 else:
                     raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"No API key available for provider {provider_key_name}.")
             else:
                  raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No API key configured for provider {provider_key_name}.")


        max_retries = 1 # Thử lại 1 lần sau failover
        for attempt in range(max_retries + 1):
            try:
                logging.info(f"Attempt {attempt + 1}: Calling provider {provider_key_name} with key_id {current_key_id}")
                # --- Gọi Service tương ứng ---
                if provider_key_name == "google":
                    prompt, history = ModelRouter._convert_messages(messages)
                    service = GeminiService(api_key=current_api_key, model=base_model_name)
                    response_text, _ = await service.generate_text_response(message=prompt, history=history, model=base_model_name)
                    if response_text is None: response_text = ""
                    elif not isinstance(response_text, str): response_text = str(response_text)
                    prompt_tokens = sum(len(msg.get("content", "").split()) for msg in messages if isinstance(msg.get("content"), str)) * 4
                    completion_tokens = len(response_text.split()) * 4
                    response_payload = {
                        "id": f"chatcmpl-gemini-{uuid.uuid4().hex}", "object": "chat.completion", "created": int(time.time()),
                        "model": original_model_name,
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
                    }
                    return response_payload

                elif provider_key_name == "xai": # Changed "grok" to "xai"
                    service = GrokService(api_key=current_api_key)
                    response_payload = await service.create_chat_completion(
                        model=base_model_name, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=False
                    )
                    response_payload["model"] = original_model_name
                    return response_payload

                elif provider_key_name == "gigachat":
                    service = GigaChatService(auth_key=current_api_key)
                    response_payload = await service.create_chat_completion(
                        model=base_model_name, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=False
                    )
                    response_payload["model"] = original_model_name
                    return response_payload

                elif provider_key_name == "perplexity":
                    service = SonarService(api_key=current_api_key, model=base_model_name)
                    response_payload = await service.create_chat_completion(
                        messages=messages, model=base_model_name, temperature=temperature, max_tokens=max_tokens, stream=False
                    )
                    response_payload["model"] = original_model_name
                    return response_payload

                else:
                    # Trường hợp này không nên xảy ra nếu _determine_provider hoạt động đúng
                    logging.error(f"Internal routing error: Unhandled provider key name '{provider_key_name}'")
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during model routing.")

            except HTTPException as e:
                # Kiểm tra xem có phải lỗi liên quan đến key không
                error_code = e.status_code
                error_message = e.detail
                is_key_error = error_code in [401, 403, 429] or \
                               (error_code == 400 and "API key" in error_message.lower()) # Ví dụ kiểm tra message cho lỗi 400

                if is_key_error and current_key_id and attempt < max_retries:
                    logging.warning(f"Key error detected (Status: {error_code}). Attempting failover...")
                    new_key_info = await attempt_automatic_failover(
                        user_id, provider_key_name, current_key_id, error_code, error_message, supabase
                    )
                    if new_key_info:
                        current_key_id = new_key_info['id']
                        current_api_key = new_key_info['api_key']
                        logging.info(f"Failover successful. Retrying with new key_id: {current_key_id}")
                        continue # Vòng lặp sẽ thử lại với key mới
                    else:
                        # Failover không tìm được key mới
                        logging.error(f"Failover failed for user {user_id}, provider {provider_key_name}. All keys exhausted.")
                        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="All provider keys failed or are temporarily disabled.")
                else:
                    # Lỗi không phải do key, hoặc đã hết lượt retry, hoặc không có initial_key_id
                    if attempt == max_retries and is_key_error:
                         logging.error(f"Retry attempt failed with key error (Status: {error_code}) for key_id {current_key_id}.")
                         # Ghi log retry failed
                         await log_activity_db(
                             user_id=user_id, provider_name=provider_key_name, key_id=current_key_id,
                             action="RETRY_FAILED", details=f"Retry failed with error {error_code} after failover.",
                             supabase=supabase
                         )
                         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Provider key failover attempt failed.")
                    else:
                         # Ném lại lỗi gốc nếu không phải lỗi key hoặc không thể failover/retry
                         logging.exception(f"Unhandled exception during API call attempt {attempt + 1}: {e}")
                         raise e

            except Exception as e:
                 # Bắt các lỗi không mong muốn khác từ service
                 logging.exception(f"Unexpected error during API call attempt {attempt + 1} for provider {provider_key_name}: {e}")
                 # Nếu đây là lần thử lại và vẫn lỗi, coi như failover thất bại
                 if attempt == max_retries:
                      await log_activity_db(
                          user_id=user_id, provider_name=provider_key_name, key_id=current_key_id,
                          action="RETRY_FAILED", details=f"Retry failed with unexpected error: {str(e)}",
                          supabase=supabase
                      )
                      raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Provider key failover attempt failed with unexpected error: {e}")
                 else:
                      # Nếu là lỗi ở lần đầu, có thể thử failover nếu có vẻ liên quan đến key (khó xác định)
                      # Hoặc đơn giản là ném lỗi 500
                      raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error processing request with {provider_key_name}: {e}")

        # Nếu vòng lặp kết thúc mà không return (trường hợp không nên xảy ra nếu logic đúng)
        logging.error("Reached end of failover loop unexpectedly.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during failover process.")

    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]) -> Tuple[str, List[ChatMessage]]:
        """
        Chuyển đổi từ định dạng tin nhắn OpenAI sang định dạng Gemini.

        Returns:
            Tuple gồm (prompt hiện tại, lịch sử trò chuyện)
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
        provider_api_keys: Dict[str, str] = None
    ) -> Tuple[str, str]:
        """Routes simple chat requests (message + history) to the appropriate model."""
        provider_api_keys = provider_api_keys or {}
        logging.info(f"Routing simple chat request for model: {model}")

        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)
        provider = ModelRouter._determine_provider(model)

        if provider == "google":
            api_key = provider_api_keys.get("google")
            try:
                service = GeminiService(api_key=api_key, model=base_model_name)
                response_text, model_used_by_service = await service.generate_text_response(
                    message=message,
                    history=history,
                    model=base_model_name
                )
                if response_text is None: response_text = ""
                elif not isinstance(response_text, str): response_text = str(response_text)
                return response_text, original_model_name
            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing simple Gemini chat request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating chat response with Gemini: {e}")

        elif provider == "x-ai":
            api_key = provider_api_keys.get("xai") # Changed "grok" to "xai"
            try:
                service = GrokService(api_key=api_key)
                openai_messages = ModelRouter._convert_simple_to_openai(message, history)
                response_payload = await service.create_chat_completion(
                    model=base_model_name,
                    messages=openai_messages,
                    stream=False
                )
                response_text = response_payload.get("choices", [{}])[0].get("message", {}).get("content", "")
                return response_text, original_model_name
            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Grok API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing simple Grok chat request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating chat response with Grok: {e}")

        elif provider == "gigachat":
            auth_key = provider_api_keys.get("gigachat")
            # Removed key existence check since GigaChatService handles fallback
            try:
                # Initialize service and let it handle fallback
                service = GigaChatService(auth_key=auth_key)
                openai_messages = ModelRouter._convert_simple_to_openai(message, history)
                response_payload = await service.create_chat_completion(
                    model=base_model_name,
                    messages=openai_messages,
                    stream=False
                )
                response_text = response_payload.get("choices", [{}])[0].get("message", {}).get("content", "")
                return response_text, original_model_name
            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"GigaChat Auth Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing simple GigaChat chat request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating chat response with GigaChat: {e}")

        elif provider == "perplexity":
            api_key = provider_api_keys.get("perplexity")
            try:
                service = SonarService(api_key=api_key, model=base_model_name)
                response_text, model_used = await service.generate_text_response(
                    message=message,
                    history=history,
                    model=base_model_name
                )
                if response_text is None: response_text = ""
                elif not isinstance(response_text, str): response_text = str(response_text)
                return response_text, original_model_name
            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Perplexity API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing simple Perplexity chat request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating chat response with Perplexity Sonar: {e}")

        logging.error(f"Internal routing error: Unhandled provider '{provider}' for model '{original_model_name}'")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during model routing.")

    @staticmethod
    async def stream_chat_completion(
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        provider_api_keys: Dict[str, str] = None,
        # Thêm các tham số cần thiết cho failover
        supabase: Optional[Client] = None,
        auth_info: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Định tuyến và stream yêu cầu chat completion, hỗ trợ failover.
        Yields Server-Sent Events (SSE) formatted strings.
        """
        # --- Phần kiểm tra và lấy thông tin ban đầu (tương tự route_chat_completion) ---
        if supabase is None or auth_info is None:
             error_payload = {"error": {"message": "Internal configuration error: Supabase client or Auth info missing for failover.", "type": "internal_server_error", "code": 500}}
             yield f"data: {json.dumps(error_payload)}\n\n"
             yield "data: [DONE]\n\n"
             return

        user_id = auth_info.get("user_id")
        auth_token = auth_info.get("token")
        if not user_id or not auth_token:
             error_payload = {"error": {"message": "Internal configuration error: User ID or Auth token missing for failover.", "type": "internal_server_error", "code": 500}}
             yield f"data: {json.dumps(error_payload)}\n\n"
             yield "data: [DONE]\n\n"
             return

        provider_api_keys = provider_api_keys or {}
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_time = int(time.time())
        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)

        try:
            provider_map = {"google": "google", "x-ai": "xai", "sber": "gigachat", "perplexity": "perplexity"} # Changed "grok" to "xai"
            provider_key_name = provider_map.get(ModelRouter._determine_provider(model))
            if not provider_key_name:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Could not map provider for model '{model}'")
        except HTTPException as e:
            logging.warning(f"Streaming requested for model with unknown provider: {model} - Error: {e.detail}")
            error_payload = {"error": {"message": e.detail, "type": "invalid_request_error", "code": e.status_code}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
            return

        logging.info(f"Routing stream request for model: {original_model_name} (Provider Key Name: {provider_key_name}, Base Model: {base_model_name})")

        # --- Lấy ID của key ban đầu ---
        initial_key_id: Optional[str] = None
        try:
            # Xóa await ở đây
            key_res = supabase.table("user_provider_keys").select("id") \
                .eq("user_id", user_id) \
                .eq("provider_name", provider_key_name) \
                .eq("is_selected", True) \
                .limit(1) \
                .maybe_single() \
                .execute()
            # Kiểm tra xem key_res có tồn tại không TRƯỚC KHI truy cập .data
            if key_res:
                if key_res.data:
                    initial_key_id = str(key_res.data['id'])
                else:
                    # Trường hợp key_res tồn tại nhưng data rỗng (ít khả năng với maybe_single)
                    logging.warning(f"No initial selected key found (empty data) for stream: user {user_id}, provider {provider_key_name}.")
            else:
                # Trường hợp key_res là None (do lỗi execute, ví dụ 406)
                logging.error(f"Supabase query for initial key failed for stream: user {user_id}, provider {provider_key_name}. Response was None.")
                # Gửi lỗi SSE cho client
                error_payload = {"error": {"message": f"Failed to query initial key for provider {provider_key_name}. Check Supabase connection/permissions.", "type": "internal_server_error", "code": 500}}
                yield f"data: {json.dumps(error_payload)}\n\n"
                yield "data: [DONE]\n\n"
                return # Thoát khỏi hàm vì không thể tiếp tục
        except Exception as e:
            logging.exception(f"Error fetching initial key ID for stream: user {user_id}, provider {provider_key_name}: {e}")
            error_payload = {"error": {"message": "Failed to retrieve initial key information.", "type": "internal_server_error", "code": 500}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # --- Logic Gọi API Stream và Failover ---
        current_api_key = provider_api_keys.get(provider_key_name)
        current_key_id = initial_key_id

        if not current_api_key:
            logging.warning(f"No API key found in initial request dict for provider {provider_key_name}. Checking DB for selected key ID: {initial_key_id}")
            if initial_key_id:
                # Try to fetch the selected key directly from DB since it wasn't provided
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
                                # Decrypt the key fetched from DB using Fernet
                                encryption_key = get_encryption_key()
                                f = Fernet(base64.urlsafe_b64encode(encryption_key))
                                current_api_key = f.decrypt(encrypted_key.encode()).decode()
                                logging.info(f"Successfully fetched and decrypted selected key {initial_key_id} from DB.")
                                # Now current_api_key is set, proceed to the API call attempt
                            except Exception as decrypt_e:
                                logging.exception(f"Failed to decrypt the selected key {initial_key_id} from DB: {decrypt_e}")
                                error_payload = {"error": {"message": f"Failed to decrypt stored API key for {provider_key_name}.", "type": "internal_server_error", "code": 500}}
                                yield f"data: {json.dumps(error_payload)}\n\n"
                                yield "data: [DONE]\n\n"
                                return
                        else:
                            logging.error(f"Selected key {initial_key_id} found in DB but has no encrypted key data.")
                            error_payload = {"error": {"message": f"Stored API key data is missing for {provider_key_name}.", "type": "internal_server_error", "code": 500}}
                            yield f"data: {json.dumps(error_payload)}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                    else:
                        logging.error(f"Could not fetch the selected key {initial_key_id} details from DB despite having its ID.")
                        error_payload = {"error": {"message": f"Failed to retrieve stored API key details for {provider_key_name}.", "type": "internal_server_error", "code": 500}}
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                except Exception as fetch_e:
                    logging.exception(f"Error fetching selected key {initial_key_id} details from DB: {fetch_e}")
                    error_payload = {"error": {"message": f"Database error retrieving API key for {provider_key_name}.", "type": "internal_server_error", "code": 500}}
                    yield f"data: {json.dumps(error_payload)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
            else:
                 # No initial_key_id found AND no key provided in dict -> No key configured
                 logging.error(f"No initial API key provided and no key selected in DB for provider {provider_key_name}.")
                 error_payload = {"error": {"message": f"No API key configured or selected for provider {provider_key_name}.", "type": "invalid_request_error", "code": 400}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
                 yield "data: [DONE]\n\n"
                 return
        # If current_api_key was provided initially OR successfully fetched/decrypted above, continue to the loop

        stream_successful = False # Cờ đánh dấu stream thành công
        attempt = 0
        while True: # Loop indefinitely until success or exhaustion
            attempt += 1
            logging.info(f"--- Starting attempt {attempt} ---")
            service_stream: Optional[AsyncGenerator[str, None]] = None
            stream_successful = False # Reset success flag for each attempt

            try:
                # Ensure we have a key to try for this attempt
                if not current_api_key or not current_key_id:
                     logging.error(f"Attempt {attempt}: No valid key available. Provider: {provider_key_name}")
                     error_payload = {"error": {"message": f"No API key available for provider {provider_key_name}.", "type": "service_unavailable", "code": 503}}
                     yield f"data: {json.dumps(error_payload)}\n\n"
                     yield "data: [DONE]\n\n"
                     return

                logging.info(f"Stream Attempt {attempt}: Calling provider {provider_key_name} with key_id {current_key_id}")

                # --- Setup Service Stream ---
                logging.info(f"Attempt {attempt}: Setting up service stream...")
                if provider_key_name == "google":
                    prompt, history = ModelRouter._convert_messages(messages)
                    service = GeminiService(api_key=current_api_key, model=base_model_name)
                    first_chunk = True
                    async def google_sse_wrapper():
                        nonlocal first_chunk
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
                        except HTTPException as gemini_e:
                             logging.error(f"HTTPException within Gemini stream wrapper: {gemini_e.status_code} - {gemini_e.detail}")
                             raise gemini_e
                        except Exception as gemini_e:
                             logging.exception("Unexpected error within Gemini stream wrapper")
                             raise HTTPException(status_code=500, detail=f"Unexpected Gemini stream error: {gemini_e}")
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
                     logging.error(f"Internal streaming routing error: Unhandled provider key name '{provider_key_name}'")
                     error_payload = {"error": {"message": "Internal server error during streaming model routing.", "type": "internal_server_error", "code": 500}}
                     yield f"data: {json.dumps(error_payload)}\n\n"
                     yield "data: [DONE]\n\n"
                     return

                logging.info(f"Attempt {attempt}: Service stream setup done.")

                # --- Iterate through the stream ---
                if not service_stream:
                     # Should not happen if setup was successful, but check anyway
                     logging.error(f"Attempt {attempt}: Failed to initialize service stream (service_stream is None).")
                     raise HTTPException(status_code=500, detail="Failed to initialize provider service stream.")

                logging.info(f"Attempt {attempt}: Entering stream iteration...")
                async for chunk in service_stream:
                    yield chunk

                # If the loop completes without raising an exception, it was successful
                logging.info(f"Attempt {attempt}: Stream iteration finished successfully.")
                stream_successful = True
                break # Exit the while loop on success

            # --- Exception Handling for the entire attempt (setup + iteration) ---
            except HTTPException as e:
                logging.error(f"Attempt {attempt}: Caught HTTPException: {e.status_code} - {e.detail}")
                error_code = e.status_code
                error_message = e.detail
                # Updated check for key-related errors
                is_key_error = error_code in [401, 403, 429] or \
                               (error_code == 400 and ("API key" in str(error_message).lower() or "permission denied" in str(error_message).lower() or "Incorrect API key" in str(error_message)))

                if is_key_error and current_key_id:
                    logging.warning(f"Stream Key error detected (Status: {error_code}) on key {current_key_id}. Attempting failover...")
                    # --- Failover Logic ---
                    new_key_info = await attempt_automatic_failover(
                        user_id, provider_key_name, current_key_id, error_code, error_message, supabase
                    )
                    if new_key_info:
                        current_key_id = new_key_info['id']
                        current_api_key = new_key_info['api_key']
                        logging.info(f"Stream Failover successful. Continuing loop with new key_id: {current_key_id}")
                        continue # Go to the next iteration of the while loop
                    else:
                        # Failover failed - no more keys
                        logging.error(f"Stream Failover failed for user {user_id}, provider {provider_key_name}. All keys exhausted after key {current_key_id} failed.")
                        await log_activity_db(
                            user_id=user_id, provider_name=provider_key_name, key_id=current_key_id,
                            action="FAILOVER_EXHAUSTED",
                            description=f"All keys failed for provider {provider_key_name}. Last error: {error_code}",
                            supabase=supabase
                        )
                        error_payload = {"error": {"message": f"All provider keys failed or are temporarily disabled for {provider_key_name}. Last error: {error_code}", "type": "service_unavailable", "code": 503}}
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        yield "data: [DONE]\n\n"
                        return # Exit generator
                else:
                    # Error is not a key error, or failover is not possible/applicable
                    logging.error(f"Attempt {attempt}: Non-key HTTPException occurred ({error_code}) or failover not applicable. Yielding error and stopping.")
                    logging.exception(f"Unhandled HTTPException details during stream attempt {attempt}: {e}") # Log stack trace
                    error_payload = {"error": {"message": f"Error during streaming: {error_message}", "type": "api_error", "code": error_code}}
                    yield f"data: {json.dumps(error_payload)}\n\n"
                    yield "data: [DONE]\n\n"
                    return # Exit generator

            except Exception as e:
                 # Catch any other unexpected errors during the attempt
                 logging.exception(f"Attempt {attempt}: Caught unexpected Exception.")
                 error_type = "internal_server_error"
                 error_code = 500
                 error_message = f"Unexpected error processing stream with {provider_key_name} on attempt {attempt}: {e}"
                 error_payload = {"error": {"message": error_message, "type": error_type, "code": error_code}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
                 yield "data: [DONE]\n\n"
                 return # Exit generator

        # --- End of while loop ---
        # This part is only reached if the loop was exited via 'break' (i.e., success)
        if stream_successful:
            logging.info(f"--- Stream completed successfully after {attempt} attempt(s). ---")
            yield "data: [DONE]\n\n"
        else:
             # Should not happen if logic is correct, but as a safeguard
             logging.error("Stream loop exited without success flag set and without returning an error.")
             error_payload = {"error": {"message": "Internal server error: Stream ended unexpectedly.", "type": "internal_server_error", "code": 500}}
             yield f"data: {json.dumps(error_payload)}\n\n"
             yield "data: [DONE]\n\n"