# app/services/model_router.py
from typing import Dict, Any, Tuple, List, Optional, AsyncGenerator
import json
import re
from fastapi import HTTPException, status, UploadFile
import mimetypes
from app.services.gemini import GeminiService
from app.services.grok import GrokService
from app.services.gigachat_service import GigaChatService
from app.models.schemas import ChatMessage
import time
import uuid
import logging
from app.core.config import get_settings

settings = get_settings()

class ModelRouter:
    """Lớp chịu trách nhiệm định tuyến các yêu cầu đến mô hình AI thích hợp."""

    @staticmethod
    def _strip_provider_prefix(model_id: str) -> str:
        """Removes provider prefix (e.g., 'google/', 'x-ai/', 'sber/') from model ID."""
        return re.sub(r"^(google|x-ai|sber)/", "", model_id)

    @staticmethod
    def _determine_provider(model: str) -> str:
        """Determines the provider ('google', 'x-ai', or 'gigachat') based on model name/prefix."""
        if not model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name must be specified.")

        if model.startswith("google/") or "gemini" in model.lower():
            return "google"
        elif model.startswith("x-ai/") or "grok" in model.lower():
            return "x-ai"
        elif model.startswith("sber/") or "gigachat" in model.lower():
            return "gigachat"
        else:
            logging.error(f"Could not determine provider for model: {model}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not determine the provider for the requested model '{model}'. Supported models contain 'gemini', 'grok', or 'gigachat'."
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
            api_key = provider_api_keys.get("grok")
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
        provider_api_keys: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Định tuyến yêu cầu chat completion tới mô hình Google Gemini.
        
        Args:
            model: Tên mô hình (ví dụ: "gemini-2.5-pro-exp-03-25")
            messages: Danh sách các tin nhắn từ request
            temperature: Nhiệt độ cho quá trình sinh văn bản
            max_tokens: Số lượng token tối đa cho phản hồi
            provider_api_keys: Dict chứa API key cho provider
        
        Returns:
            Phản hồi theo định dạng OpenAI
        """
        provider_api_keys = provider_api_keys or {}
        
        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)
        provider = ModelRouter._determine_provider(model)

        logging.info(f"Routing chat completion request for model: {original_model_name} (Provider: {provider}, Base Model: {base_model_name})")

        if provider == "google":
            prompt, history = ModelRouter._convert_messages(messages)
            api_key = provider_api_keys.get("google")
            try:
                service = GeminiService(api_key=api_key, model=base_model_name)
                response_text, model_used_by_service = await service.generate_text_response(
                    message=prompt,
                    history=history,
                    model=base_model_name
                )

                if response_text is None: response_text = ""
                elif not isinstance(response_text, str): response_text = str(response_text)

                prompt_tokens = sum(len(msg.get("content", "").split()) for msg in messages if isinstance(msg.get("content"), str)) * 4
                completion_tokens = len(response_text.split()) * 4
                total_tokens = prompt_tokens + completion_tokens

                response_payload = {
                    "id": f"chatcmpl-gemini-{uuid.uuid4().hex}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": original_model_name,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": total_tokens},
                }
                return response_payload

            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing Gemini request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing request with Gemini: {e}")

        elif provider == "x-ai":
            api_key = provider_api_keys.get("grok")
            try:
                service = GrokService(api_key=api_key)
                response_payload = await service.create_chat_completion(
                    model=base_model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
                response_payload["model"] = original_model_name
                return response_payload
            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Grok API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing Grok request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing request with Grok: {e}")

        elif provider == "gigachat":
            auth_key = provider_api_keys.get("gigachat")
            try:
                service = GigaChatService(auth_key=auth_key)
                response_payload = await service.create_chat_completion(
                    model=base_model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
                response_payload["model"] = original_model_name
                return response_payload
            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"GigaChat Auth Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing GigaChat request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing request with GigaChat: {e}")

        logging.error(f"Internal routing error: Unhandled provider '{provider}' for model '{original_model_name}'")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during model routing.")
    
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
            api_key = provider_api_keys.get("grok")
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
            try:
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

        logging.error(f"Internal routing error: Unhandled provider '{provider}' for model '{original_model_name}'")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during model routing.")

    @staticmethod
    async def stream_chat_completion(
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        provider_api_keys: Dict[str, str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Định tuyến và stream yêu cầu chat completion tới mô hình Google Gemini.
        Yields Server-Sent Events (SSE) formatted strings.
        """
        provider_api_keys = provider_api_keys or {}
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_time = int(time.time())

        original_model_name = model
        base_model_name = ModelRouter._strip_provider_prefix(model)
        try:
            provider = ModelRouter._determine_provider(model)
        except HTTPException as e:
            logging.warning(f"Streaming requested for model with unknown provider: {model} - Error: {e.detail}")
            error_payload = {"error": {"message": e.detail, "type": "invalid_request_error", "code": e.status_code}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
            return

        logging.info(f"Routing stream request for model: {original_model_name} (Provider: {provider}, Base Model: {base_model_name})")

        if provider == "google":
            prompt, history = ModelRouter._convert_messages(messages)
            api_key = provider_api_keys.get("google")
            try:
                service = GeminiService(api_key=api_key, model=base_model_name)
                first_chunk = True
                async for chunk_text in service.stream_text_response(
                    message=prompt, history=history, model=base_model_name
                ):
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

            except ValueError as e:
                 error_payload = {"error": {"message": f"Gemini API Key Error: {e}", "type": "authentication_error", "code": 401}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except HTTPException as e:
                 error_payload = {"error": {"message": f"Gemini Error: {e.detail}", "type": "api_error", "code": e.status_code}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except Exception as e:
                logging.exception(f"Error streaming from Gemini for model {original_model_name}: {e}")
                error_payload = {"error": {"message": f"Error streaming from Gemini: {e}", "type": "internal_server_error", "code": 500}}
                yield f"data: {json.dumps(error_payload)}\n\n"

        elif provider == "x-ai":
            api_key = provider_api_keys.get("grok")
            try:
                service = GrokService(api_key=api_key)
                async for chunk in service.stream_chat_completion(
                    model=base_model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                     yield chunk
            except ValueError as e:
                 error_payload = {"error": {"message": f"Grok API Key Error: {e}", "type": "authentication_error", "code": 401}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except HTTPException as e:
                 error_payload = {"error": {"message": f"Grok Error: {e.detail}", "type": "api_error", "code": e.status_code}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except Exception as e:
                 logging.exception(f"Error streaming from Grok for model {original_model_name}: {e}")
                 error_payload = {"error": {"message": f"Error streaming from Grok: {e}", "type": "internal_server_error", "code": 500}}
                 yield f"data: {json.dumps(error_payload)}\n\n"

        elif provider == "gigachat":
            auth_key = provider_api_keys.get("gigachat")
            try:
                service = GigaChatService(auth_key=auth_key)
                async for chunk in service.stream_chat_completion(
                    model=base_model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                    yield chunk
            except ValueError as e:
                 error_payload = {"error": {"message": f"GigaChat Auth Key Error: {e}", "type": "authentication_error", "code": 401}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except NotImplementedError as e:
                 error_payload = {"error": {"message": f"GigaChat Error: {e}", "type": "invalid_request_error", "code": 501}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except HTTPException as e:
                 error_payload = {"error": {"message": f"GigaChat Error: {e.detail}", "type": "api_error", "code": e.status_code}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except Exception as e:
                logging.exception(f"Error streaming from GigaChat for model {original_model_name}: {e}")
                error_payload = {"error": {"message": f"Error streaming from GigaChat: {e}", "type": "internal_server_error", "code": 500}}
                yield f"data: {json.dumps(error_payload)}\n\n"

        else:
             logging.error(f"Internal streaming routing error: Unhandled provider '{provider}' for model '{original_model_name}'")
             error_payload = {"error": {"message": "Internal server error during streaming model routing.", "type": "internal_server_error", "code": 500}}
             yield f"data: {json.dumps(error_payload)}\n\n"

        yield "data: [DONE]\n\n"