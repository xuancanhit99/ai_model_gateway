# app/services/model_router.py
from typing import Dict, Any, Tuple, List, Optional, AsyncGenerator # Add AsyncGenerator
import json
from app.services.gemini import GeminiService
from app.services.grok import GrokService # Import GrokService
from app.models.schemas import ChatMessage
from fastapi import HTTPException, status # Import HTTPException
import time
import uuid
import logging # Add logging

class ModelRouter:
    """Lớp chịu trách nhiệm định tuyến các yêu cầu đến mô hình AI thích hợp."""
    
    @staticmethod
    def _determine_provider(model: str) -> str:
        """Determines the provider ('google' or 'x-ai') based on model name."""
        if not model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name must be specified.")

        if "gemini" in model.lower():
            return "google"
        elif "grok" in model.lower():
            return "x-ai"
        # Add other potential provider checks here if needed
        # elif "claude" in model.lower(): return "anthropic"
        else:
            logging.error(f"Could not determine provider for model: {model}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not determine the provider for the requested model '{model}'. Supported models contain 'gemini' or 'grok'."
            )

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
        base_model_name = model # Use the full model name
        provider = ModelRouter._determine_provider(model)

        # --- Route based on provider derived from prefix ---
        if provider == "google":
            # Chuyển đổi messages thành định dạng phù hợp cho Gemini
            prompt, history = ModelRouter._convert_messages(messages)
            api_key = provider_api_keys.get("google")
            try:
                # Pass BASE model name to the service
                service = GeminiService(api_key=api_key, model=base_model_name)
                response_text, model_used_by_service = await service.generate_text_response(
                    message=prompt,
                    history=history,
                    model=base_model_name # Pass BASE model name
                )

                # --- Format Gemini response to OpenAI ---
                # Ensure response_text is a string
                if response_text is None: response_text = ""
                elif not isinstance(response_text, str): response_text = str(response_text)

                # Estimate tokens (simple) - TODO: Improve token estimation
                prompt_tokens = sum(len(msg.get("content", "").split()) for msg in messages if isinstance(msg.get("content"), str)) * 4
                completion_tokens = len(response_text.split()) * 4
                total_tokens = prompt_tokens + completion_tokens

                response_payload = {
                    "id": f"chatcmpl-gemini-{uuid.uuid4().hex}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": original_model_name, # Use the original model name in response
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": total_tokens},
                }
                return response_payload

            except ValueError as e: # Catch API key error from GeminiService init
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini API Key Error: {e}")
            except HTTPException as e: # Re-raise specific HTTP exceptions from service
                raise e
            except Exception as e:
                logging.exception(f"Error processing Gemini request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing request with Gemini: {e}")

        elif provider == "x-ai":
            api_key = provider_api_keys.get("grok") # Key name is 'grok' in dict
            try:
                service = GrokService(api_key=api_key)
                # GrokService method already returns OpenAI format
                # Pass BASE model name to the service
                response_payload = await service.create_chat_completion(
                    model=base_model_name,
                    messages=messages, # Pass OpenAI format directly
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
                # Ensure the response payload uses the original model name
                response_payload["model"] = original_model_name
                return response_payload
            except ValueError as e: # Catch API key error from GrokService init
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Grok API Key Error: {e}")
            except HTTPException as e: # Re-raise specific HTTP exceptions from service
                raise e
            except Exception as e:
                logging.exception(f"Error processing Grok request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing request with Grok: {e}")

        # Safeguard: This should not be reached if _determine_provider works correctly
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
        # prompt = "" # Initialize later
        system_message = None

        if not messages:
            return "", []

        valid_messages = [m for m in messages if isinstance(m.get("content"), str) and m.get("role")]

        if not valid_messages:
            return "", []

        # Tìm system message (chỉ lấy cái đầu tiên nếu có nhiều)
        for msg in valid_messages:
            if msg["role"] == "system":
                system_message = msg["content"]
                break

        # Xử lý tin nhắn user/assistant
        processed_indices = set()
        if system_message:
            # Tìm index của system message để bỏ qua khi tạo history
            for i, msg in enumerate(valid_messages):
                if msg["role"] == "system":
                    processed_indices.add(i)
                    break # Chỉ xử lý system message đầu tiên

        last_user_message_index = -1
        for i in range(len(valid_messages) - 1, -1, -1):
            if valid_messages[i]["role"] == "user":
                last_user_message_index = i
                break

        if last_user_message_index == -1:
            # Không có tin nhắn user nào? Trả về prompt rỗng.
            return "", []

        # Tin nhắn cuối cùng của user làm prompt
        # Initialize prompt here, closer to usage
        prompt: str
        last_user_msg = valid_messages[last_user_message_index]
        prompt_content = last_user_msg["content"]
        if system_message:
            prompt = f"{system_message}\n\n{prompt_content}"
        else:
            prompt = prompt_content
        processed_indices.add(last_user_message_index)

        # Các tin nhắn còn lại làm history
        for i, msg in enumerate(valid_messages):
            if i not in processed_indices and msg["role"] != "system":
                # Gemini dùng 'user' và 'model'
                gemini_role = "user" if msg["role"] == "user" else "model"
                history.append(ChatMessage(role=gemini_role, content=msg["content"]))

        # Gemini API yêu cầu history xen kẽ user/model, bắt đầu bằng user
        final_history = []
        last_role = None
        for h_msg in history:
            # Đơn giản hóa: Chỉ thêm nếu role khác role trước đó để tránh lỗi Gemini
            if h_msg.role != last_role:
                final_history.append(h_msg)
                last_role = h_msg.role

        return prompt, final_history

    @staticmethod
    def _convert_simple_to_openai(message: str, history: List[ChatMessage]) -> List[Dict[str, str]]:
        """Converts simple message/history to OpenAI message list."""
        openai_messages = []
        for msg in history:
            # Assuming history roles are 'user' and 'model'/'assistant'
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
        base_model_name = model # Use the full model name
        provider = ModelRouter._determine_provider(model)

        if provider == "google":
            api_key = provider_api_keys.get("google")
            try:
                # Pass BASE model name
                service = GeminiService(api_key=api_key, model=base_model_name)
                response_text, model_used_by_service = await service.generate_text_response(
                    message=message,
                    history=history,
                    model=base_model_name # Explicitly pass BASE model name
                )
                # Ensure response_text is a string
                if response_text is None: response_text = ""
                elif not isinstance(response_text, str): response_text = str(response_text)
                # Return ORIGINAL model name
                return response_text, original_model_name
            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing simple Gemini chat request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating chat response with Gemini: {e}")

        elif provider == "x-ai":
            api_key = provider_api_keys.get("grok") # Key name is 'grok' in dict
            try:
                service = GrokService(api_key=api_key)
                # Convert simple format to OpenAI messages for Grok
                openai_messages = ModelRouter._convert_simple_to_openai(message, history)
                # Call Grok's completion method with BASE model name
                response_payload = await service.create_chat_completion(
                    model=base_model_name,
                    messages=openai_messages,
                    stream=False # Simple chat doesn't stream
                )
                # Extract response text
                response_text = response_payload.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Return ORIGINAL model name
                return response_text, original_model_name
            except ValueError as e:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Grok API Key Error: {e}")
            except HTTPException as e:
                raise e
            except Exception as e:
                logging.exception(f"Error processing simple Grok chat request for model {original_model_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating chat response with Grok: {e}")

        # Safeguard: This should not be reached if _determine_provider works correctly
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
        base_model_name = model # Use the full model name
        try:
            provider = ModelRouter._determine_provider(model)
        except HTTPException as e:
            # Handle provider determination error within the stream
            logging.warning(f"Streaming requested for model with unknown provider: {model} - Error: {e.detail}")
            error_payload = {"error": {"message": e.detail, "type": "invalid_request_error", "code": e.status_code}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
            return # Stop execution

        # --- Route based on provider derived from prefix ---
        if provider == "google":
            # Chuyển đổi messages thành định dạng phù hợp cho Gemini
            prompt, history = ModelRouter._convert_messages(messages)
            api_key = provider_api_keys.get("google")
            try:
                # Pass BASE model name to the service
                service = GeminiService(api_key=api_key, model=base_model_name)
                first_chunk = True
                # Call stream_text_response with the BASE model name
                async for chunk_text in service.stream_text_response(
                    message=prompt, history=history, model=base_model_name
                ):
                    if chunk_text is None: continue

                    chunk_payload = {
                        "id": request_id, "object": "chat.completion.chunk", "created": created_time,
                        "model": original_model_name, # Use original model name in chunk
                        "choices": [{"index": 0, "delta": {}, "finish_reason": None}]
                    }
                    if first_chunk:
                        chunk_payload["choices"][0]["delta"]["role"] = "assistant"
                        first_chunk = False
                    chunk_payload["choices"][0]["delta"]["content"] = chunk_text
                    yield f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n"

                # Send final chunk with finish reason
                final_chunk_payload = {
                    "id": request_id, "object": "chat.completion.chunk", "created": created_time,
                    "model": original_model_name, # Use original model name in final chunk
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(final_chunk_payload, ensure_ascii=False)}\n\n"

            except ValueError as e:
                 error_payload = {"error": {"message": f"Gemini API Key Error: {e}", "type": "authentication_error", "code": 401}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except HTTPException as e: # Catch specific errors from service
                 error_payload = {"error": {"message": f"Gemini Error: {e.detail}", "type": "api_error", "code": e.status_code}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except Exception as e:
                logging.exception(f"Error streaming from Gemini for model {original_model_name}: {e}")
                error_payload = {"error": {"message": f"Error streaming from Gemini: {e}", "type": "internal_server_error", "code": 500}}
                yield f"data: {json.dumps(error_payload)}\n\n"

        elif provider == "x-ai": # Use provider check
            api_key = provider_api_keys.get("grok") # Key name is 'grok' in dict
            try:
                service = GrokService(api_key=api_key)
                # Call Grok's streaming method with BASE model name
                async for chunk in service.stream_chat_completion(
                    model=base_model_name,
                    messages=messages, # Pass OpenAI format directly
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                     # Assuming GrokService.stream_chat_completion yields SSE formatted strings
                     # We might need to parse the chunk, replace the model ID with original_model_name,
                     # and re-serialize if Grok doesn't return the requested model name.
                     # For now, let's assume Grok's stream includes a model field we can potentially override later if needed,
                     # or that the client uses the initial request model. Forwarding for now.
                     # TODO: Verify Grok streaming output and adjust chunk modification if necessary.
                     # Example modification (if chunk is dict):
                     # try:
                     #     chunk_data = json.loads(chunk.split("data: ", 1)[1])
                     #     chunk_data['model'] = original_model_name
                     #     yield f"data: {json.dumps(chunk_data)}\n\n"
                     # except: # If parsing fails or format is unexpected, yield original
                     #     yield chunk
                     yield chunk # Forward the SSE formatted chunk
            except ValueError as e: # Catch API key error from GrokService init
                 error_payload = {"error": {"message": f"Grok API Key Error: {e}", "type": "authentication_error", "code": 401}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except HTTPException as e: # Catch specific errors from service (like 501 Not Implemented)
                 error_payload = {"error": {"message": f"Grok Error: {e.detail}", "type": "api_error", "code": e.status_code}}
                 yield f"data: {json.dumps(error_payload)}\n\n"
            except Exception as e:
                 logging.exception(f"Error streaming from Grok for model {original_model_name}: {e}")
                 error_payload = {"error": {"message": f"Error streaming from Grok: {e}", "type": "internal_server_error", "code": 500}}
                 yield f"data: {json.dumps(error_payload)}\n\n"

        # Safeguard: This should not be reached if _determine_provider works correctly
        else:
             logging.error(f"Internal streaming routing error: Unhandled provider '{provider}' for model '{original_model_name}'")
             error_payload = {"error": {"message": "Internal server error during streaming model routing.", "type": "internal_server_error", "code": 500}}
             yield f"data: {json.dumps(error_payload)}\n\n"


        # Send the final [DONE] signal regardless of which model was used (or if error occurred before loop)
        yield "data: [DONE]\n\n"