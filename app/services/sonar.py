# app/services/sonar.py
import aiohttp
import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from fastapi import HTTPException, status
from app.core.config import get_settings
from app.models.schemas import ChatMessage

settings = get_settings()

class SonarService:
    """Service for interacting with Perplexity's Sonar models"""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize the Sonar service.
        
        Args:
            api_key: Optional Perplexity API key (will default to config if not provided)
            model: Optional model name override (will default to config if not provided)
        """
        self.api_key = api_key or settings.PERPLEXITY_API_KEY
        self.model = model or settings.SONAR_DEFAULT_MODEL
        self.api_base_url = settings.PERPLEXITY_API_BASE_URL or "https://api.perplexity.ai"
        
        if not self.api_key:
            logging.warning("Perplexity API key not set. API calls will fail.")
    
    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to the Perplexity API."""
        url = f"{self.api_base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_detail = await response.text()
                        logging.error(f"Perplexity API error: {error_detail}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Error from Perplexity API: {error_detail}"
                        )
                    
                    return await response.json()
        except aiohttp.ClientError as e:
            logging.error(f"Network error during Perplexity API request: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Connection error to Perplexity API: {e}"
            )
    
    def _prepare_chat_payload(
        self,
        messages: List[Dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        web_search_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare the payload for chat completions."""
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        # Add optional parameters if provided
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        # Default top_p for sonar models
        payload["top_p"] = 0.9
            
        # Add web search options if provided
        if web_search_options:
            payload["web_search_options"] = web_search_options
            
        return payload
    
    async def create_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        web_search_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a chat completion using Perplexity Sonar models.
        
        Args:
            messages: List of message objects (role and content)
            model: Model to use (defaults to sonar if not specified)
            temperature: Temperature for response generation (0-2)
            max_tokens: Maximum number of tokens to generate
            stream: Whether to stream the response
            web_search_options: Options for web search capabilities
            
        Returns:
            Chat completion response in OpenAI-compatible format
        """
        if stream:
            raise ValueError("For streaming, use stream_chat_completion method instead")
        
        payload = self._prepare_chat_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            web_search_options=web_search_options
        )
        
        try:
            response = await self._make_request("/chat/completions", payload)
            return response
        except (ValueError, HTTPException) as e:
            raise
        except Exception as e:
            logging.exception(f"Unexpected error in Sonar chat completion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in chat completion: {e}"
            )
    
    async def generate_text_response(
        self,
        message: str,
        history: List[ChatMessage],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        web_search_options: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Generate a text response with a simplified interface.
        
        Args:
            message: The user's message
            history: Chat history as a list of ChatMessage objects
            model: Model to use
            temperature: Temperature parameter (0-2)
            max_tokens: Maximum tokens to generate
            web_search_options: Options for web search
            
        Returns:
            Tuple of (response_text, model_used)
        """
        formatted_messages = []
        
        # Convert history to the format expected by Perplexity API
        for msg in history:
            # Convert from our schema to Perplexity format
            # Our 'model' role should be 'assistant' for Perplexity
            role = "assistant" if msg.role == "model" else msg.role
            formatted_messages.append({"role": role, "content": msg.content})
        
        # Add the user's current message
        formatted_messages.append({"role": "user", "content": message})
        
        try:
            response = await self.create_chat_completion(
                messages=formatted_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                web_search_options=web_search_options
            )
            
            response_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            model_used = response.get("model", model or self.model)
            
            return response_text, model_used
        except Exception as e:
            logging.exception(f"Error generating text response with Sonar: {e}")
            raise
    
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        web_search_options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion from Perplexity Sonar models.
        
        Args:
            messages: List of message objects
            model: Model to use
            temperature: Temperature parameter (0-2)
            max_tokens: Maximum tokens to generate
            web_search_options: Options for web search
            
        Yields:
            SSE-formatted JSON chunks
        """
        payload = self._prepare_chat_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            web_search_options=web_search_options
        )
        
        url = f"{self.api_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_detail = await response.text()
                        error_payload = {"error": {"message": f"Perplexity API Error: {error_detail}", "type": "api_error", "code": response.status}}
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        return
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            # Pass the SSE data directly to the client
                            yield f"{line}\n\n"
                            
                            # If the line indicates completion, exit
                            if line == 'data: [DONE]':
                                break
        except aiohttp.ClientError as e:
            logging.error(f"Network error during Perplexity streaming: {e}")
            error_payload = {"error": {"message": f"Connection error to Perplexity API: {e}", "type": "connection_error", "code": 503}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logging.exception(f"Unexpected error during Perplexity streaming: {e}")
            error_payload = {"error": {"message": f"Streaming error: {e}", "type": "internal_server_error", "code": 500}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"