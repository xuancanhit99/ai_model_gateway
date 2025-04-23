# app/services/model_router.py
from typing import Dict, Any, Tuple, List, Optional
from app.services.gemini import GeminiService
# Trong tương lai: from app.services.grok import GrokService
from app.models.schemas import ChatMessage, ChatCompletionMessage
import time
import uuid

class ModelRouter:
    """Lớp chịu trách nhiệm xác định và gọi mô hình phù hợp dựa trên tên mô hình."""
    
    @staticmethod
    async def route_chat_completion(
        model: str,
        messages: List[ChatCompletionMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        provider_api_keys: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Định tuyến yêu cầu chat completion tới mô hình phù hợp.
        
        Args:
            model: Tên mô hình theo định dạng "provider/model_name"
            messages: Danh sách các tin nhắn
            temperature: Nhiệt độ cho quá trình sinh văn bản
            max_tokens: Số lượng token tối đa cho phản hồi
            provider_api_keys: Dict chứa API key cho từng nhà cung cấp
        
        Returns:
            Phản hồi theo định dạng OpenAI
        """
        provider_api_keys = provider_api_keys or {}
        
        if "/" not in model:
            # Mô hình mặc định nếu không có định dạng provider/model
            provider = "google"
            model_name = model
        else:
            # Tách thành provider và model_name
            provider, model_name = model.split("/", 1)
        
        # Chuyển đổi messages thành định dạng phù hợp
        prompt, history = ModelRouter._convert_messages(messages)
        
        # Lấy API key cho provider cụ thể
        provider_api_key = provider_api_keys.get(provider)
        
        # Định tuyến tới service phù hợp
        if provider.lower() == "google":
            service = GeminiService(api_key=provider_api_key, model_name=model_name)
            response_text, model_used = await service.generate_text_response(
                message=prompt,
                history=history,
                model_name_override=model_name
            )
        # elif provider.lower() == "x-ai":
        #     # Trong tương lai khi thêm Grok
        #     service = GrokService(api_key=provider_api_key, model_name=model_name)
        #     response_text, model_used = await service.generate_text_response(
        #         message=prompt,
        #         history=history
        #     )
        else:
            raise ValueError(f"Provider không được hỗ trợ: {provider}")
        
        # Mô phỏng việc tính toán token (trong thực tế cần tính chính xác hơn)
        prompt_tokens = sum(len(msg.content.split()) * 4 for msg in messages)
        completion_tokens = len(response_text.split()) * 4
        total_tokens = prompt_tokens + completion_tokens
        
        # Tạo phản hồi theo định dạng OpenAI
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:10]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        }
    
    @staticmethod
    def _convert_messages(messages: List[ChatCompletionMessage]) -> Tuple[str, List[Dict[str, str]]]:
        """
        Chuyển đổi từ định dạng tin nhắn OpenAI sang định dạng của Gemini.
        
        Returns:
            Tuple gồm (prompt hiện tại, lịch sử trò chuyện)
        """
        history = []
        prompt = ""
        system_message = None
        
        # Đầu tiên, kiểm tra nếu có tin nhắn system và lưu lại
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
                break
        
        for i, msg in enumerate(messages):
            if msg.role == "system":
                # Bỏ qua tin nhắn system trong history
                continue
            elif i == len(messages) - 1 and msg.role == "user":
                # Tin nhắn cuối cùng từ người dùng sẽ là prompt
                if system_message:
                    # Nếu có system message, kết hợp với prompt người dùng
                    prompt = f"{system_message}\n\n{msg.content}"
                else:
                    prompt = msg.content
            else:
                # Chỉ thêm vào history nếu không phải là system message
                history.append({
                    "role": "user" if msg.role == "user" else "assistant",
                    "content": msg.content
                })
        
        # Chuyển đổi history sang dạng ChatMessage
        converted_history = []
        for msg in history:
            converted_history.append(ChatMessage(
                role=msg["role"],
                content=msg["content"]
            ))
        
        return prompt, converted_history