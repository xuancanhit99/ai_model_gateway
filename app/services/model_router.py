# app/services/model_router.py
from typing import Dict, Any, Tuple, List, Optional, AsyncGenerator # Add AsyncGenerator
import json # Add json import
from app.services.gemini import GeminiService
from app.models.schemas import ChatMessage
import time
import uuid

class ModelRouter:
    """Lớp chịu trách nhiệm định tuyến các yêu cầu đến mô hình AI thích hợp."""
    
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
        
        # Xử lý tên model
        if not model or model == "":
            model = "gemini-2.0-flash"
        
        # Chuyển đổi messages thành định dạng phù hợp
        prompt, history = ModelRouter._convert_messages(messages)
        
        # Lấy API key cho provider
        api_key = provider_api_keys.get("google")
        
        try:
            # Xử lý request với Gemini
            service = GeminiService(api_key=api_key, model_name=model)
            response_text, model_used = await service.generate_text_response(
                message=prompt,
                history=history,
                model_name_override=model
            )
        except Exception as e:
            # Log lỗi chi tiết hơn
            error_message = f"Error calling underlying model service: {str(e)}"
            print(error_message) # Hoặc sử dụng logging

            # Trả về cấu trúc lỗi giống OpenAI
            error_payload = {
                "error": {
                    "message": error_message,
                    "type": "api_error", # Hoặc một type phù hợp hơn nếu biết
                    "param": None,
                    "code": None # Có thể thêm mã lỗi cụ thể nếu có
                }
            }
            # Quan trọng: Trả về ngay lập tức từ khối except
            return error_payload

        # --- Phần code dưới đây chỉ thực thi nếu không có exception ---

        # Đảm bảo response_text LUÔN LUÔN là string
        if response_text is None:
            response_text = "" # Nếu None, trả về chuỗi rỗng
        elif not isinstance(response_text, str):
            response_text = str(response_text) # Cố gắng ép kiểu sang string

        # Tính toán token (giữ nguyên ước tính đơn giản)
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        try:
            for msg in messages:
                content = msg.get("content")
                if isinstance(content, str):
                    prompt_tokens += len(content.split()) * 4 # Ước tính đơn giản
            completion_tokens = len(response_text.split()) * 4
            total_tokens = prompt_tokens + completion_tokens
        except Exception as token_error:
            print(f"Token calculation error: {token_error}") # Log lỗi tính token
            # Có thể xem xét trả về lỗi ở đây thay vì giá trị mặc định
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

        # Tạo phản hồi JSON CHÍNH XÁC theo chuẩn OpenAI (cho trường hợp thành công)
        response_payload = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_used,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                        "tool_calls": [] # Change from None to empty list
                    },
                    "logprobs": None,
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            },
            # Thêm system_fingerprint nếu cần
            # "system_fingerprint": "fp_xxxxxxxxxx" # REMOVED
        }

        return response_payload
    
    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]) -> Tuple[str, List[ChatMessage]]:
        """
        Chuyển đổi từ định dạng tin nhắn OpenAI sang định dạng Gemini.
        
        Returns:
            Tuple gồm (prompt hiện tại, lịch sử trò chuyện)
        """
        history = []
        prompt = ""
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

        # Xử lý tên model
        if not model or model == "":
            model = "gemini-2.5-pro-exp-03-25" # Default model

        # Chuyển đổi messages thành định dạng phù hợp
        prompt, history = ModelRouter._convert_messages(messages)

        # Lấy API key cho provider
        api_key = provider_api_keys.get("google")

        try:
            # Khởi tạo service
            service = GeminiService(api_key=api_key, model_name=model)

            model_used_for_stream = model # Tạm thời, sẽ cập nhật từ GeminiService
            first_chunk = True
            async for chunk_text in service.stream_text_response(
                message=prompt,
                history=history,
                model_name_override=model
                # Thêm các tham số khác nếu cần (temp, max_tokens)
            ):
                if chunk_text is None: # Bỏ qua nếu chunk rỗng
                    continue

                # Tạo chunk JSON theo chuẩn OpenAI
                chunk_payload = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": model_used_for_stream,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": None # Sẽ cập nhật ở chunk cuối nếu cần
                        }
                    ]
                }

                # Chunk đầu tiên có thể chứa role
                if first_chunk:
                    chunk_payload["choices"][0]["delta"]["role"] = "assistant"
                    first_chunk = False

                # Thêm content vào delta
                chunk_payload["choices"][0]["delta"]["content"] = chunk_text

                # Định dạng SSE: "data: <json_string>\n\n"
                sse_formatted_chunk = f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n"
                yield sse_formatted_chunk

            # Gửi chunk cuối cùng với finish_reason (nếu cần)
            # Hiện tại Gemini stream không cung cấp finish_reason rõ ràng từng chunk
            # Nên ta gửi một chunk cuối cùng chỉ để đánh dấu kết thúc logic ở đây
            # Hoặc có thể gửi finish_reason="stop" trong chunk cuối cùng nếu Gemini API hỗ trợ
            final_chunk_payload = {
                 "id": request_id,
                 "object": "chat.completion.chunk",
                 "created": created_time,
                 "model": model_used_for_stream,
                 "choices": [
                     {
                         "index": 0,
                         "delta": {}, # Delta rỗng
                         "finish_reason": "stop" # Đánh dấu kết thúc
                     }
                 ]
            }
            yield f"data: {json.dumps(final_chunk_payload, ensure_ascii=False)}\n\n"


        except Exception as e:
            # Log lỗi và có thể yield một thông báo lỗi SSE
            error_message = f"Error during streaming from model service: {str(e)}"
            print(error_message)
            error_payload = {
                "error": {
                    "message": error_message,
                    "type": "api_error",
                    "param": None,
                    "code": None
                }
            }
            # Gửi lỗi dưới dạng SSE (không chắc client sẽ xử lý đúng chuẩn không)
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

        finally:
            # Gửi tín hiệu kết thúc stream [DONE] theo chuẩn OpenAI SSE
            yield "data: [DONE]\n\n"