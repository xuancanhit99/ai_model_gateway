import httpx
import uuid
import time
import logging
import json
import asyncio
from cachetools import TTLCache
from fastapi import HTTPException, status

# Correct imports for settings and logger within the main gateway structure
from app.core.config import get_settings # Import the function to get settings
# Assuming logger is configured in config.py or main app setup
# If not, configure standard logging here:
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)
# For now, let's assume a logger instance is available via app setup or config
logger = logging.getLogger(__name__) # Use standard logging for now

# Get settings instance
settings = get_settings()

from app.models.schemas import (
    GigaChatCompletionRequest, GigaChatCompletionResponse,
    TokenResponse, GigaChatMessageInput
)

# Cache for the access token (TTL slightly less than 30 mins, e.g., 29 mins = 1740 secs)
token_cache = TTLCache(maxsize=1, ttl=1740)
CACHE_KEY = "gigachat_access_token"
_token_lock = asyncio.Lock() # Lock for fetching token

async def _fetch_new_access_token() -> str:
    """Fetches a new access token from the GigaChat OAuth endpoint."""
    if not settings.GIGACHAT_AUTH_KEY:
        logger.error("GIGACHAT_AUTH_KEY is not configured.")
        raise ValueError("GigaChat Authorization Key (GIGACHAT_AUTH_KEY) is missing in settings.")

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {settings.GIGACHAT_AUTH_KEY}'
    }
    data = {'scope': settings.GIGACHAT_SCOPE}
    request_url = settings.GIGACHAT_TOKEN_URL

    logger.info(f"Requesting new GigaChat access token from {request_url} with scope {settings.GIGACHAT_SCOPE}")

    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(request_url, headers=headers, data=data)
            response.raise_for_status()

            token_data = response.json()
            if "access_token" not in token_data or "expires_at" not in token_data:
                logger.error(f"Invalid token response structure received: {token_data}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid token response from GigaChat auth service.")

            token_response = TokenResponse(**token_data)
            logger.info(f"Successfully obtained new GigaChat access token, expires at {token_response.expires_at}")
            return token_response.access_token

        except httpx.RequestError as exc:
            logger.error(f"HTTP request error while fetching GigaChat token: {exc}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=f"Error connecting to GigaChat auth service: {exc}")
        except httpx.HTTPStatusError as exc:
            logger.error(f"HTTP status error while fetching GigaChat token: {exc.response.status_code} - {exc.response.text}")
            raise HTTPException(status_code=exc.response.status_code,
                                detail=f"GigaChat auth service returned error: {exc.response.text}")
        except Exception as exc:
            logger.exception(f"Unexpected error fetching GigaChat token: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"An unexpected error occurred while fetching the GigaChat token: {exc}")

async def get_access_token() -> str:
    """Gets the access token, utilizing the cache manually and handling async."""
    logger.info("Attempting to get GigaChat access token (checking cache first)...")
    
    try:
        cached_token = token_cache[CACHE_KEY]
        logger.info("Found valid token in cache.")
        return cached_token
    except KeyError:
        logger.info("Token not found in cache or expired, attempting to fetch new token.")

    async with _token_lock:
        try:
            cached_token = token_cache[CACHE_KEY]
            logger.info("Found valid token in cache after acquiring lock.")
            return cached_token
        except KeyError:
            logger.info("Fetching new token under lock.")
            try:
                token = await _fetch_new_access_token()
                if not token:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                        detail="_fetch_new_access_token returned empty token.")
                token_cache[CACHE_KEY] = token
                logger.info("Successfully fetched and cached new token.")
                return token
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
            except Exception as e:
                logger.exception("Unexpected error during token fetch within lock.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error fetching token: {e}")

class GigaChatService:
    """Service class to interact with GigaChat API."""
    def __init__(self, auth_key: str = None):
        if auth_key and not settings.GIGACHAT_AUTH_KEY:
            logger.warning("Auth key provided to GigaChatService init, but token fetching uses GIGACHAT_AUTH_KEY from settings.")
        elif not settings.GIGACHAT_AUTH_KEY:
            logger.warning("GigaChatService initialized without an auth key provided or found in settings.")

    async def create_chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False
    ) -> dict:
        if stream:
            raise NotImplementedError("Use stream_chat_completion for streaming requests.")

        access_token = await get_access_token()

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        giga_messages = [GigaChatMessageInput(**msg) for msg in messages]

        payload = GigaChatCompletionRequest(
            model=model,
            messages=giga_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ).model_dump(exclude_none=True)

        request_url = settings.GIGACHAT_CHAT_URL
        logger.info(f"Sending chat completion request to GigaChat ({model}) at {request_url}")

        async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
            try:
                response = await client.post(request_url, headers=headers, json=payload)
                response.raise_for_status()
                response_data = response.json()
                logger.info("Successfully received chat completion response from GigaChat.")

                giga_response = GigaChatCompletionResponse(**response_data)

                response_content = ""
                if giga_response.choices and giga_response.choices[0].message:
                    response_content = giga_response.choices[0].message.content

                finish_reason = "stop"
                if giga_response.choices and giga_response.choices[0].finish_reason:
                    finish_reason = giga_response.choices[0].finish_reason

                prompt_tokens = giga_response.usage.prompt_tokens if giga_response.usage else 0
                completion_tokens = giga_response.usage.completion_tokens if giga_response.usage else 0
                total_tokens = giga_response.usage.total_tokens if giga_response.usage else prompt_tokens + completion_tokens

                openai_payload = {
                    "id": f"chatcmpl-gigachat-{uuid.uuid4().hex}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": response_content},
                        "finish_reason": finish_reason
                    }],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    },
                }
                return openai_payload

            except httpx.RequestError as exc:
                logger.error(f"HTTP request error during GigaChat chat completion: {exc}")
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                    detail=f"Error connecting to GigaChat chat service: {exc}")
            except httpx.HTTPStatusError as exc:
                logger.error(f"HTTP status error during GigaChat chat completion: {exc.response.status_code} - {exc.response.text}")
                error_detail = f"GigaChat chat service returned error: Status {exc.response.status_code}"
                try:
                    error_json = exc.response.json()
                    error_detail += f" - {error_json}"
                except Exception:
                    error_detail += f" - {exc.response.text}"
                raise HTTPException(status_code=exc.response.status_code, detail=error_detail)
            except Exception as exc:
                logger.exception(f"Unexpected error during GigaChat chat completion: {exc}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail=f"An unexpected error occurred during GigaChat chat completion: {exc}")

    async def stream_chat_completion(self, model: str, messages: list[dict[str, str]], temperature: float = 0.7, max_tokens: int | None = None):
        access_token = await get_access_token()

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            'Authorization': f'Bearer {access_token}'
        }

        giga_messages = [GigaChatMessageInput(**msg) for msg in messages]
        payload = GigaChatCompletionRequest(
            model=model,
            messages=giga_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        ).model_dump(exclude_none=True)

        request_url = settings.GIGACHAT_CHAT_URL
        request_id = f"chatcmpl-gigachat-stream-{uuid.uuid4().hex}"
        created_time = int(time.time())

        logger.info(f"Sending stream chat completion request to GigaChat ({model}) at {request_url}")

        try:
            async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
                async with client.stream("POST", request_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error(f"GigaChat stream request failed: Status {response.status_code} - Body: {error_body.decode()}")
                        error_detail = f"GigaChat stream service returned error: Status {response.status_code}"
                        try:
                            error_json = json.loads(error_body.decode())
                            error_detail += f" - {error_json}"
                        except Exception:
                            error_detail += f" - {error_body.decode()}"
                        error_payload = {"error": {"message": error_detail, "type": "api_error", "code": response.status_code}}
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        return
                    
                    first_chunk = True
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data_str = line[len("data:"):].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                giga_chunk = json.loads(data_str)
                                openai_chunk_payload = {
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

                                if first_chunk:
                                    openai_chunk_payload["choices"][0]["delta"]["role"] = "assistant"
                                    first_chunk = False

                                content_delta = ""
                                if giga_chunk.get("choices") and giga_chunk["choices"][0].get("delta"):
                                    content_delta = giga_chunk["choices"][0]["delta"].get("content", "")
                                
                                if content_delta:
                                    openai_chunk_payload["choices"][0]["delta"]["content"] = content_delta
                                
                                finish_reason = None
                                if giga_chunk.get("choices") and giga_chunk["choices"][0].get("finish_reason"):
                                    finish_reason = giga_chunk["choices"][0]["finish_reason"]
                                    openai_chunk_payload["choices"][0]["finish_reason"] = finish_reason

                                if content_delta or finish_reason:
                                    yield f"data: {json.dumps(openai_chunk_payload, ensure_ascii=False)}\n\n"

                            except json.JSONDecodeError:
                                logger.warning(f"Failed to decode JSON from GigaChat stream line: {data_str}")
                            except Exception as e:
                                logger.exception(f"Error processing GigaChat stream chunk: {e}")
                                error_payload = {"error": {"message": f"Error processing stream chunk: {e}", "type": "internal_server_error", "code": 500}}
                                yield f"data: {json.dumps(error_payload)}\n\n"

        except httpx.RequestError as exc:
            logger.error(f"HTTP request error during GigaChat stream: {exc}")
            error_payload = {"error": {"message": f"Error connecting to GigaChat stream service: {exc}", "type": "connection_error", "code": 503}}
            yield f"data: {json.dumps(error_payload)}\n\n"
        except Exception as exc:
            logger.exception(f"Unexpected error during GigaChat stream setup or processing: {exc}")
            error_payload = {"error": {"message": f"An unexpected error occurred during GigaChat stream: {exc}", "type": "internal_server_error", "code": 500}}
            yield f"data: {json.dumps(error_payload)}\n\n"

