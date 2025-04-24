# app/services/grok.py
import httpx
import base64
import mimetypes
import logging
import time
import json
import uuid
from fastapi import HTTPException, status, UploadFile
from typing import List, Dict, Any, Optional, Tuple, Union, AsyncGenerator
from app.core.config import get_settings
from app.models.schemas import ChatMessage

settings = get_settings()
logging.basicConfig(level=logging.INFO)

class GrokService:
    """
    Service for interacting with the xAI Grok API for chat and vision tasks.
    Uses the standard /chat/completions endpoint for both.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_endpoint = f"{settings.XAI_API_BASE_URL}/chat/completions"
        self.api_key = api_key or settings.XAI_API_KEY
        self.default_vision_prompt = "Extract all visible text from this image. Returns only the text content."

        if not self.api_key:
            raise ValueError("Grok service requires an API key (XAI_API_KEY).")

    async def _make_request(
        self,
        payload: Dict[str, Any],
        timeout: float = 90.0
    ) -> Dict[str, Any]:
        """Helper function to make requests to the Grok API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        async with httpx.AsyncClient() as client:
            try:
                logging.debug(f"Grok Request Payload (non-stream): {payload}")
                response = await client.post(self.api_endpoint, json=payload, headers=headers, timeout=timeout)
                response.raise_for_status()
                response_data = response.json()
                logging.debug(f"Grok Response Data (non-stream): {response_data}")
                return response_data

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                error_detail = f"Grok API request failed (Status: {status_code})"
                try:
                    error_data = e.response.json()
                    api_err_msg = error_data.get("error", {}).get("message") or error_data.get("detail")
                    if api_err_msg:
                        error_detail = f"Grok API Error: {api_err_msg}"
                        if "authentication" in api_err_msg.lower() or status_code == 401:
                            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                            error_detail = "Grok service failed: Invalid API Key configured or provided."
                        elif "rate limit" in api_err_msg.lower() or status_code == 429:
                            status_code = status.HTTP_429_TOO_MANY_REQUESTS
                            error_detail = "Grok service rate limited by API. Please try again later."
                        elif "invalid input" in api_err_msg.lower() or status_code == 400:
                            status_code = status.HTTP_400_BAD_REQUEST
                            error_detail = f"Grok API rejected input: {api_err_msg}"
                        else:
                            status_code = status.HTTP_502_BAD_GATEWAY
                    else:
                        if status_code == 401: status_code = status.HTTP_500_INTERNAL_SERVER_ERROR; error_detail = "Grok service failed: Invalid API Key."
                        elif status_code == 429: status_code = status.HTTP_429_TOO_MANY_REQUESTS; error_detail = "Grok service rate limited."
                        elif status_code == 400: status_code = status.HTTP_400_BAD_REQUEST; error_detail = "Grok API rejected input."
                        else: status_code = status.HTTP_502_BAD_GATEWAY; error_detail = "Bad Gateway connecting to Grok API."

                except Exception:
                    if status_code == 401: status_code = status.HTTP_500_INTERNAL_SERVER_ERROR; error_detail = "Grok service failed: Invalid API Key."
                    elif status_code == 429: status_code = status.HTTP_429_TOO_MANY_REQUESTS; error_detail = "Grok service rate limited."
                    elif status_code == 400: status_code = status.HTTP_400_BAD_REQUEST; error_detail = "Grok API rejected input."
                    else: status_code = status.HTTP_502_BAD_GATEWAY; error_detail = "Bad Gateway connecting to Grok API."

                logging.error(f"Grok API Error: {error_detail} (Status: {status_code})")
                raise HTTPException(status_code=status_code, detail=error_detail) from e

            except httpx.TimeoutException as e:
                logging.error("Request to Grok API timed out.")
                raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request to Grok API timed out.") from e
            except httpx.RequestError as e:
                logging.error(f"Could not connect to Grok API: {e}")
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the backend Grok service.") from e
            except (KeyError, IndexError, TypeError) as parse_error:
                logging.error(f"Failed to parse Grok API response: {parse_error}")
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to parse expected data from Grok API response.") from parse_error
            except Exception as e:
                logging.exception("An unexpected error occurred in Grok service request.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected internal error occurred.") from e

    async def extract_text_from_image(
        self,
        image_file: UploadFile,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Sends the image to the Grok Vision API and returns extracted text.
        Uses the standard /chat/completions endpoint.
        """
        selected_model = model or settings.GROK_VISION_MODEL_NAME
        used_prompt = prompt or self.default_vision_prompt

        try:
            image_content = await image_file.read()
            mime_type, _ = mimetypes.guess_type(image_file.filename or "image.bin")
            if mime_type not in settings.GROK_ALLOWED_CONTENT_TYPES:
                mime_type = image_file.content_type
                if mime_type not in settings.GROK_ALLOWED_CONTENT_TYPES:
                    logging.error(f"Unsupported image type '{mime_type}' for Grok.")
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail=f"Unsupported image type '{mime_type}' for Grok. Allowed: {', '.join(settings.GROK_ALLOWED_CONTENT_TYPES)}"
                    )

            image_base64 = base64.b64encode(image_content).decode('utf-8')
            data_url = f"data:{mime_type};base64,{image_base64}"

            payload = {
                "model": selected_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url, "detail": "high"}
                            },
                            {"type": "text", "text": used_prompt}
                        ]
                    }
                ],
                "max_tokens": 3000,
                "temperature": 0.1,
            }

            grok_response = await self._make_request(payload)

            response_message = grok_response.get("choices", [{}])[0].get("message", {"content": ""})
            extracted_text = response_message.get("content", "").strip()

            refusal_phrases = ["unable to process", "cannot fulfill this request", "cannot extract text", "i cannot process images"]
            if any(phrase in extracted_text.lower() for phrase in refusal_phrases):
                logging.warning(f"Grok model {selected_model} refused OCR task.")
                extracted_text = "Model indicated it could not perform the OCR task on this image."

            return extracted_text, selected_model

        except HTTPException as http_exc:
            raise http_exc
        except ValueError as e:
            logging.error(f"GrokService configuration error: {e}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Grok Service Error: {e}") from e
        except Exception as e:
            logging.exception("An unexpected error occurred during Grok image extraction.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected internal error occurred during Grok image extraction."
            ) from e

    async def create_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = 3000,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Generates a chat completion using the Grok API, mimicking OpenAI structure.
        Handles both text-only and vision requests based on message content.
        Supports streaming.
        """
        if stream:
            return self.stream_chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            is_vision_request = False
            processed_messages = []
            for msg in messages:
                if isinstance(msg.get("content"), list):
                    image_items = [item for item in msg["content"] if item.get("type") == "image_url"]
                    if image_items:
                        is_vision_request = True
                        for item in image_items:
                            image_url_data = item.get("image_url", {}).get("url", "")
                            if image_url_data.startswith("data:"):
                                try:
                                    mime_type = image_url_data.split(':')[1].split(';')[0]
                                    if mime_type not in settings.GROK_ALLOWED_CONTENT_TYPES:
                                        logging.error(f"Unsupported image type '{mime_type}' for Grok found in message.")
                                        raise HTTPException(
                                            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                            detail=f"Unsupported image type '{mime_type}' for Grok. Allowed: {', '.join(settings.GROK_ALLOWED_CONTENT_TYPES)}"
                                        )
                                except IndexError:
                                    logging.error(f"Could not parse mime type from image data URL: {image_url_data[:50]}...")
                                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image data URL format.")
                processed_messages.append(msg)

            if not model:
                model = settings.GROK_VISION_MODEL_NAME if is_vision_request else settings.GROK_CHAT_MODEL_NAME
            elif "vision" in model and not is_vision_request:
                logging.warning(f"Vision model '{model}' requested for text-only chat.")
            elif "vision" not in model and is_vision_request:
                logging.warning(f"Text model '{model}' requested for vision chat. Grok might not support this.")

            payload = {
                "model": model,
                "messages": processed_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if max_tokens is None:
                del payload["max_tokens"]

            grok_response = await self._make_request(payload)

            try:
                finish_reason = grok_response.get("choices", [{}])[0].get("finish_reason", "stop")
                response_message = grok_response.get("choices", [{}])[0].get("message", {"role": "assistant", "content": ""})
                prompt_tokens = grok_response.get("usage", {}).get("prompt_tokens")
                completion_tokens = grok_response.get("usage", {}).get("completion_tokens")
                total_tokens = grok_response.get("usage", {}).get("total_tokens")

                if is_vision_request:
                    response_content = response_message.get("content", "")
                    refusal_phrases = ["unable to process", "cannot fulfill this request", "cannot extract text", "i cannot process images"]
                    if any(phrase in response_content.lower() for phrase in refusal_phrases):
                        logging.warning(f"Grok model refused OCR task for model {model}.")

                openai_formatted_response = {
                    "id": grok_response.get("id", f"grok-cmpl-{base64.b64encode(str(payload).encode()).decode()}"),
                    "object": "chat.completion",
                    "created": grok_response.get("created", int(time.time())),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": response_message,
                            "finish_reason": finish_reason,
                        }
                    ],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                }
                if prompt_tokens is None and completion_tokens is None and total_tokens is None:
                    del openai_formatted_response["usage"]

                return openai_formatted_response

            except (KeyError, IndexError, TypeError) as e:
                logging.error(f"Failed to transform Grok response to OpenAI format: {e}. Response: {grok_response}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to parse or transform response from Grok API."
                ) from e

    async def _stream_request(
        self,
        payload: Dict[str, Any],
        timeout: float = 90.0
    ) -> AsyncGenerator[str, None]:
        """Helper function to make streaming requests to the Grok API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        async with httpx.AsyncClient() as client:
            try:
                logging.debug(f"Grok Request Payload (stream): {payload}")
                async with client.stream("POST", self.api_endpoint, json=payload, headers=headers, timeout=timeout) as response:
                    if response.status_code >= 400:
                        error_body = await response.aread()
                        error_detail = f"Grok API stream request failed (Status: {response.status_code})"
                        try:
                            error_data = json.loads(error_body.decode())
                            api_err_msg = error_data.get("error", {}).get("message") or error_data.get("detail")
                            if api_err_msg:
                                error_detail = f"Grok API Error: {api_err_msg}"
                        except Exception:
                            error_detail += f" - Body: {error_body.decode()[:200]}"

                        logging.error(f"Grok API Stream Error: {error_detail} (Status: {response.status_code})")
                        error_payload = {"error": {"message": error_detail, "type": "api_error", "code": response.status_code}}
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if line:
                            yield line + "\n\n"

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                error_detail = f"Grok API stream request failed (Status: {status_code})"
                logging.error(f"Grok API Stream HTTPStatusError: {error_detail}")
                error_payload = {"error": {"message": error_detail, "type": "api_error", "code": status_code}}
                yield f"data: {json.dumps(error_payload)}\n\n"
            except httpx.TimeoutException:
                logging.error("Stream request to Grok API timed out.")
                error_payload = {"error": {"message": "Request to Grok API timed out.", "type": "timeout_error", "code": 504}}
                yield f"data: {json.dumps(error_payload)}\n\n"
            except httpx.RequestError as e:
                logging.error(f"Could not connect to Grok API for streaming: {e}")
                error_payload = {"error": {"message": "Could not connect to the backend Grok service.", "type": "connection_error", "code": 503}}
                yield f"data: {json.dumps(error_payload)}\n\n"
            except Exception as e:
                logging.exception("An unexpected error occurred during Grok stream request.")
                error_payload = {"error": {"message": "An unexpected internal error occurred during streaming.", "type": "internal_server_error", "code": 500}}
                yield f"data: {json.dumps(error_payload)}\n\n"

    async def stream_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = 3000,
    ) -> AsyncGenerator[str, None]:
        """Generates and streams chat completions from Grok using SSE."""
        request_id = f"chatcmpl-grok-{uuid.uuid4().hex}"
        created_time = int(time.time())

        is_vision_request = False
        processed_messages = []
        for msg in messages:
            if isinstance(msg.get("content"), list):
                image_items = [item for item in msg["content"] if item.get("type") == "image_url"]
                if image_items:
                    is_vision_request = True
                    for item in image_items:
                        image_url_data = item.get("image_url", {}).get("url", "")
                        if image_url_data.startswith("data:"):
                            try:
                                mime_type = image_url_data.split(':')[1].split(';')[0]
                                if mime_type not in settings.GROK_ALLOWED_CONTENT_TYPES:
                                    raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Unsupported image type '{mime_type}' for Grok.")
                            except IndexError:
                                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image data URL format.")
            processed_messages.append(msg)

        if not model:
            model = settings.GROK_VISION_MODEL_NAME if is_vision_request else settings.GROK_CHAT_MODEL_NAME

        payload = {
            "model": model,
            "messages": processed_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        if max_tokens is None:
            del payload["max_tokens"]

        first_chunk = True
        try:
            async for line in self._stream_request(payload):
                if line.strip() == "data: [DONE]":
                    yield line
                    break
                elif line.startswith("data:"):
                    try:
                        chunk_data_str = line.strip()[len("data: "):]
                        chunk_data = json.loads(chunk_data_str)

                        openai_chunk = {
                            "id": request_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "finish_reason": None
                            }]
                        }

                        grok_delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                        grok_content = grok_delta.get("content")
                        grok_role = grok_delta.get("role")
                        finish_reason = chunk_data.get("choices", [{}])[0].get("finish_reason")

                        if first_chunk and not grok_role:
                            openai_chunk["choices"][0]["delta"]["role"] = "assistant"
                            first_chunk = False
                        elif grok_role:
                            openai_chunk["choices"][0]["delta"]["role"] = grok_role
                            first_chunk = False

                        if grok_content is not None:
                            openai_chunk["choices"][0]["delta"]["content"] = grok_content
                            first_chunk = False

                        if finish_reason:
                            openai_chunk["choices"][0]["finish_reason"] = finish_reason

                        if openai_chunk["choices"][0]["delta"] or openai_chunk["choices"][0]["finish_reason"]:
                            yield f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"

                    except json.JSONDecodeError:
                        logging.warning(f"Received non-JSON data line from Grok stream: {line.strip()}")
                    except Exception as e:
                        logging.error(f"Error processing Grok stream chunk: {e} - Line: {line.strip()}")
                elif line.strip():
                    logging.warning(f"Received unexpected line from Grok stream: {line.strip()}")

        except HTTPException as e:
            error_payload = {"error": {"message": f"Grok Stream Error: {e.detail}", "type": "invalid_request_error", "code": e.status_code}}
            yield f"data: {json.dumps(error_payload)}\n\n"
        except Exception as e:
            logging.exception(f"Unexpected error setting up Grok stream for model {model}")
            error_payload = {"error": {"message": f"Unexpected error setting up Grok stream: {e}", "type": "internal_server_error", "code": 500}}
            yield f"data: {json.dumps(error_payload)}\n\n"

        yield "data: [DONE]\n\n"