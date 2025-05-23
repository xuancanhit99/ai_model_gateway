import httpx
import json
import uuid
import time
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from fastapi import HTTPException, status
from app.core.config import get_settings

settings = get_settings()
logging.basicConfig(level=logging.INFO)

class GigaChatService:
    """Service for interacting with the GigaChat API."""

    def __init__(self, auth_key: Optional[str] = None):
        """Initializes the GigaChat service.

        Args:
            auth_key: Optional GigaChat authorization key. If not provided,
                      will fall back to settings.GIGACHAT_AUTH_KEY.
        """
        self.scope = settings.GIGACHAT_SCOPE
        self._default_auth_key = auth_key or settings.GIGACHAT_AUTH_KEY
        self._access_token = None
        self._token_expires_at = 0

    async def _get_access_token(self, auth_key: Optional[str] = None) -> str:
        """Retrieves or renews the access token using the provided auth_key or the default one."""
        # Use provided auth_key if available, otherwise fall back to the default
        key_to_use = auth_key or self._default_auth_key
        
        # Check if the key_to_use is valid
        if not key_to_use or len(key_to_use) < 10:  # Basic check
            raise ValueError("Invalid GigaChat Authorization Key provided.")

        current_time = time.time()
        logging.info("Requesting new GigaChat access token.")
        token_url = settings.GIGACHAT_TOKEN_URL  # Use the full token URL from settings
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
            'Authorization': f'Bearer {key_to_use}'
        }
        payload = {'scope': self.scope}

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(token_url, headers=headers, data=payload, timeout=30.0)
                response.raise_for_status()
                token_data = response.json()
                self._access_token = token_data['access_token']
                # expires_at is in milliseconds, convert to seconds
                self._token_expires_at = current_time + (token_data['expires_at'] / 1000)
                logging.info("Successfully obtained new GigaChat access token.")
                return self._access_token
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = f"GigaChat token request failed (Status: {status_code})"
            try:
                error_data = e.response.json()
                api_err_msg = error_data.get("message") or error_data.get("error_description")
                if api_err_msg:
                    error_detail = f"GigaChat Token Error: {api_err_msg}"
            except Exception:
                pass
            logging.error(f"GigaChat Token Error: {error_detail} (Status: {status_code})")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_detail) from e
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logging.error(f"Could not connect to GigaChat for token: {e}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to GigaChat authentication service.") from e
        except (KeyError, TypeError) as e:
            logging.error(f"Failed to parse GigaChat token response: {e}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid response from GigaChat authentication service.") from e

    async def _make_request(
        self,
        auth_key: Optional[str] = None,
        payload: Dict[str, Any] = None,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """Helper function to make requests to the GigaChat API."""
        # Use provided auth_key or default
        key_to_use = auth_key or self._default_auth_key
        
        if not key_to_use:
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="GigaChat Authorization Key was not provided or found.")

        try:
            access_token = await self._get_access_token(key_to_use)
        except ValueError as e:
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
        except HTTPException as e:
            raise e

        chat_url = settings.GIGACHAT_CHAT_URL  # Use the full chat URL from settings
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json' if not stream else 'text/event-stream',
            'Authorization': f'Bearer {access_token}'
        }

        try:
            if stream:
                logging.debug(f"GigaChat Request Payload (stream): {payload}")
                # Return the request info for streaming, don't create client here
                return {
                    "chat_url": chat_url,
                    "headers": headers,
                    "payload": payload
                }
            else:
                # For non-streaming, continue with current logic
                async with httpx.AsyncClient(verify=False) as client:
                    logging.debug(f"GigaChat Request Payload (non-stream): {payload}")
                    response = await client.post(chat_url, json=payload, headers=headers, timeout=90.0)
                    response.raise_for_status()
                    response_data = response.json()
                    logging.debug(f"GigaChat Response Data (non-stream): {response_data}")
                    return response_data

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = f"GigaChat API request failed (Status: {status_code})"
            try:
                error_data = e.response.json()
                api_err_msg = error_data.get("message")
                if api_err_msg:
                    error_detail = f"GigaChat API Error: {api_err_msg}"
                    if status_code == 401:
                        error_detail = "GigaChat request failed: Authentication error (check token/key)."
                    elif status_code == 429:
                        status_code = status.HTTP_429_TOO_MANY_REQUESTS
                        error_detail = "GigaChat service rate limited. Please try again later."
                    elif status_code == 400:
                        status_code = status.HTTP_400_BAD_REQUEST
                        error_detail = f"GigaChat API rejected input: {api_err_msg}"
                    else:
                        status_code = status.HTTP_502_BAD_GATEWAY
            except Exception:
                 if status_code == 401: status_code = status.HTTP_401_UNAUTHORIZED; error_detail = "GigaChat request failed: Authentication error."
                 elif status_code == 429: status_code = status.HTTP_429_TOO_MANY_REQUESTS; error_detail = "GigaChat service rate limited."
                 elif status_code == 400: status_code = status.HTTP_400_BAD_REQUEST; error_detail = "GigaChat API rejected input."
                 else: status_code = status.HTTP_502_BAD_GATEWAY; error_detail = "Bad Gateway connecting to GigaChat API."

            logging.error(f"GigaChat API Error: {error_detail} (Status: {status_code})")
            raise HTTPException(status_code=status_code, detail=error_detail) from e
        except httpx.TimeoutException as e:
             logging.error("Request to GigaChat API timed out.")
             raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request to GigaChat API timed out.") from e
        except httpx.RequestError as e:
             logging.error(f"Could not connect to GigaChat API: {e}")
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the backend GigaChat service.") from e
        except (KeyError, IndexError, TypeError) as parse_error:
             logging.error(f"Failed to parse GigaChat API response: {parse_error}")
             raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to parse expected data from GigaChat API response.") from parse_error
        except Exception as e:
             logging.exception("An unexpected error occurred in GigaChat service request.")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected internal error occurred.") from e

    async def create_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        auth_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Generates a chat completion using the GigaChat API, mimicking OpenAI structure.
        Uses provided auth_key or falls back to default.
        """
        processed_messages = messages

        payload = {
            "model": model,
            "messages": processed_messages,
            "temperature": temperature,
            "stream": stream
        }

        # Use provided auth_key or default
        giga_response = await self._make_request(auth_key=auth_key, payload=payload, stream=stream)

        if stream:
            return self.stream_chat_completion(model, messages, auth_key, temperature, max_tokens)
        else:
            try:
                finish_reason = giga_response.get("choices", [{}])[0].get("finish_reason", "stop")
                response_message = giga_response.get("choices", [{}])[0].get("message", {"role": "assistant", "content": ""})
                prompt_tokens = giga_response.get("usage", {}).get("prompt_tokens")
                completion_tokens = giga_response.get("usage", {}).get("completion_tokens")
                total_tokens = giga_response.get("usage", {}).get("total_tokens")

                openai_formatted_response = {
                    "id": giga_response.get("id", f"gigachat-cmpl-{uuid.uuid4().hex}"),
                    "object": "chat.completion",
                    "created": giga_response.get("created", int(time.time())),
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
                    if "usage" in openai_formatted_response:
                         del openai_formatted_response["usage"]

                return openai_formatted_response

            except (KeyError, IndexError, TypeError) as e:
                logging.error(f"Failed to transform GigaChat response to OpenAI format: {e}. Response: {giga_response}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to parse or transform response from GigaChat API."
                ) from e

    async def stream_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        auth_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Generates and streams chat completions from GigaChat using SSE, formatted for OpenAI."""
        request_info = await self._make_request(
            auth_key=auth_key, 
            payload={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True
            }, 
            stream=True
        )
        
        # Use the request info to create a stream and format it
        request_id = f"chatcmpl-giga-{uuid.uuid4().hex}"
        created_time = int(time.time())
        first_chunk = True

        try:
           # Create a new client within this method for streaming
           async with httpx.AsyncClient(verify=False) as client:
               async with client.stream(
                   "POST",
                   request_info["chat_url"],
                   json=request_info["payload"],
                   headers=request_info["headers"],
                   timeout=90.0
               ) as response:
                   # Check for HTTP errors *before* iterating
                   if response.status_code >= 400:
                       error_body = await response.aread()
                       status_code = response.status_code
                       error_detail = f"GigaChat API stream request failed (Status: {status_code})"
                       try:
                           error_data = json.loads(error_body.decode())
                           api_err_msg = error_data.get("message")
                           if api_err_msg:
                               error_detail = f"GigaChat API Error: {api_err_msg}"
                       except Exception:
                           error_detail += f" - Body: {error_body.decode()[:200]}"

                       # Map specific errors for failover
                       if status_code == 401: status_code = status.HTTP_401_UNAUTHORIZED
                       elif status_code == 429: status_code = status.HTTP_429_TOO_MANY_REQUESTS

                       logging.error(f"GigaChat Stream Error: {error_detail} (Status: {status_code})")
                       # RAISE HTTPException instead of yielding SSE error
                       raise HTTPException(status_code=status_code, detail=error_detail)
                   else:
                       # If status is OK, proceed with streaming
                       async for line in response.aiter_lines():
                           if not line:
                               continue

                           if line.strip() == "data: [DONE]":
                               yield line
                               break

                           if line.startswith("data:"):
                               try:
                                   chunk_data_str = line.strip()[len("data: "):]
                                   chunk_data = json.loads(chunk_data_str)

                                   if "error" in chunk_data:
                                       logging.error(f"GigaChat stream returned an error: {chunk_data['error']}")
                                       error_payload = {"error": chunk_data["error"]}
                                       yield f"data: {json.dumps(error_payload)}\n\n"
                                       continue

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

                                   giga_delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                                   giga_content = giga_delta.get("content")
                                   giga_role = giga_delta.get("role")
                                   finish_reason = chunk_data.get("choices", [{}])[0].get("finish_reason")

                                   if first_chunk and not giga_role:
                                       openai_chunk["choices"][0]["delta"]["role"] = "assistant"
                                       first_chunk = False
                                   elif giga_role:
                                       openai_chunk["choices"][0]["delta"]["role"] = giga_role
                                       first_chunk = False

                                   if giga_content is not None:
                                       openai_chunk["choices"][0]["delta"]["content"] = giga_content
                                       first_chunk = False

                                   if finish_reason:
                                       openai_chunk["choices"][0]["finish_reason"] = finish_reason

                                   if openai_chunk["choices"][0]["delta"] or openai_chunk["choices"][0]["finish_reason"]:
                                       yield f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"

                               except json.JSONDecodeError:
                                   logging.warning(f"Received non-JSON data line from GigaChat stream: {line.strip()}")
                               except Exception as e:
                                   logging.error(f"Error processing GigaChat stream chunk: {e} - Line: {line.strip()}")
                           elif line.strip():
                               logging.warning(f"Received unexpected line from GigaChat stream: {line.strip()}")

        except httpx.HTTPStatusError as e: # Should be less likely now
            status_code = e.response.status_code if hasattr(e, 'response') else 500
            error_detail = f"GigaChat Stream Error: {e}"
            # Map specific errors for failover
            if status_code == 401: status_code = status.HTTP_401_UNAUTHORIZED
            elif status_code == 429: status_code = status.HTTP_429_TOO_MANY_REQUESTS
            logging.error(f"GigaChat Stream HTTPStatusError: {error_detail} (Status: {status_code})")
            # RAISE HTTPException
            raise HTTPException(status_code=status_code, detail=error_detail) from e
        except HTTPException as e: # Catch exceptions from _make_request (e.g., token error)
            logging.error(f"GigaChat Stream Setup Error: {e.detail} (Status: {e.status_code})")
            # RAISE HTTPException (re-raise)
            raise e
        except Exception as e:
            logging.exception(f"Unexpected error during GigaChat streaming setup for model {model}")
            # RAISE HTTPException
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error during GigaChat streaming setup: {e}") from e

        yield "data: [DONE]\n\n"

