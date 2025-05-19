# app/services/gemini.py
import logging
import google.generativeai as genai
import google.api_core.exceptions # Import Google API core exceptions
from google.generativeai.types import generation_types # Import specific types for error handling
from typing import AsyncGenerator, Tuple # Add Tuple
from app.core.config import get_settings
from app.models.schemas import ChatMessage # Import ChatMessage schema
from fastapi import HTTPException, status

settings = get_settings()


class GeminiService:
    def __init__(self, api_key: str | None = None, model: str | None = None): # Renamed model_name to model
        self.genai_model = None # Renamed self.model to self.genai_model to avoid confusion
        self.api_key = api_key or settings.GOOGLE_AI_STUDIO_API_KEY
        # Default to the chat model; the dependency function for vision will override if needed
        self.model_id = model or settings.GEMINI_CHAT_MODEL_NAME # Renamed self.model_name to self.model_id
        self._initialize_model()

    def _initialize_model(self):
        if not self.api_key:
            raise ValueError("Google Gemini API key is not set")

        genai.configure(api_key=self.api_key)
        try:
            # Use self.model_id to initialize
            self.genai_model = genai.GenerativeModel(self.model_id)
        except Exception as e:
            # More specific error for model initialization
            raise ValueError(f"Failed to initialize Gemini model '{self.model_id}': {e}")

    async def extract_text(self, image_data: bytes, content_type: str, prompt: str | None = None) -> Tuple[str, str]: # Update return type hint
        """Extracts text from an image using the configured Gemini vision model."""
        # Check the initialized genai_model
        if not self.genai_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini vision model not initialized"
            )

        image_part = {
            "mime_type": content_type,
            "data": image_data
        }
        # Use the vision model's default prompt if none provided
        default_prompt = "Extract all visible text from this image. Returns only the text content."
        final_prompt = prompt or default_prompt

        try:
            # Use self.genai_model
            # Note: generate_content is synchronous, consider using generate_content_async if needed
            response = self.genai_model.generate_content([final_prompt, image_part])

            if not response.parts:
                 if response.prompt_feedback.block_reason:
                     raise generation_types.BlockedPromptException(f"Prompt blocked due to {response.prompt_feedback.block_reason.name}")
                 else:
                     return "", self.model_id
            return response.text, self.model_id
        except generation_types.BlockedPromptException as e:
            # Safety filter block
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Content blocked by Gemini safety filters: {e}")
        except google.api_core.exceptions.PermissionDenied as e:
            # Map PermissionDenied (403)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Gemini Permission Denied: {e}")
        except google.api_core.exceptions.ResourceExhausted as e:
            # Map ResourceExhausted (429)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Gemini Quota/Rate Limit Exceeded: {e}")
        except google.api_core.exceptions.InvalidArgument as e:
             # Map InvalidArgument (400) - often API key issues or bad requests
             # Check if message indicates API key issue specifically
             if "api key not valid" in str(e).lower():
                  raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Gemini API Key: {e}")
             else:
                  raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid Argument to Gemini: {e}")
        except google.api_core.exceptions.Unauthenticated as e:
             # Map Unauthenticated (401)
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini Authentication Failed: {e}")
        except Exception as e:
            # Catch-all for other unexpected errors
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error processing image with Gemini: {e}")

    async def generate_text_response(
        self,
        message: str,
        history: list[ChatMessage],
        model: str | None = None # Renamed model_name_override to model
    ) -> tuple[str, str]: # Return response text and model used
        """
        Generates a text response using the specified or default Gemini text model (using model ID),
        considering chat history.
        """
        # Determine which model ID to use
        target_model_id = model or self.model_id # Use override 'model' if provided
        model_to_use = self.genai_model # Default to the initialized model

        # If an override is specified and it's different from the initialized model ID,
        # try to initialize a temporary model instance for this request.
        if model and model != self.model_id:
            try:
                if not self.api_key:
                     raise ValueError("Google Gemini API key is not configured for model override.")
                genai.configure(api_key=self.api_key)
                model_to_use = genai.GenerativeModel(target_model_id) # Use target_model_id
            except Exception as e:
                 raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to initialize requested Gemini model '{target_model_id}': {e}" # Use target_model_id
                )

        if not model_to_use:
             raise HTTPException(
                 status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                 detail=f"Gemini chat model '{target_model_id}' could not be used." # Use target_model_id
             )

        # Format history for the Gemini API
        # The API expects a list of dicts with 'role' and 'parts' (where parts is a list of strings)
        # Convert history: map 'assistant' role to 'model' for Google API
        formatted_history = [
            {"role": "model" if msg.role == "assistant" else msg.role, "parts": [msg.content]}
            for msg in history
        ]

        try:
            # Start a chat session with the provided history
            chat = model_to_use.start_chat(history=formatted_history) # Use the determined model
            response = chat.send_message(message)

            # Check for empty/blocked response similar to extract_text
            if not response.parts:
                 if response.prompt_feedback.block_reason:
                     raise generation_types.BlockedPromptException(f"Prompt blocked due to {response.prompt_feedback.block_reason.name}")
                 else:
                     return "Model did not provide a response.", target_model_id # Return target_model_id
 
             # Return both the text and the actual model ID used
            return response.text, target_model_id
        except generation_types.BlockedPromptException as e:
            # Safety filter block
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Chat content blocked by Gemini safety filters: {e}")
        except google.api_core.exceptions.PermissionDenied as e:
            # Map PermissionDenied (403)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Gemini Permission Denied: {e}")
        except google.api_core.exceptions.ResourceExhausted as e:
            # Map ResourceExhausted (429)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Gemini Quota/Rate Limit Exceeded: {e}")
        except google.api_core.exceptions.InvalidArgument as e:
             # Map InvalidArgument (400)
             if "api key not valid" in str(e).lower():
                  raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Gemini API Key: {e}")
             else:
                  raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid Argument to Gemini: {e}")
        except google.api_core.exceptions.Unauthenticated as e:
             # Map Unauthenticated (401)
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini Authentication Failed: {e}")
        except Exception as e:
            # Catch-all for other unexpected errors
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error generating chat response with Gemini: {e}")

    async def stream_text_response(
            self,
            message: str,
            history: list[ChatMessage],
            model: str | None = None # Renamed model_name_override to model
        ) -> AsyncGenerator[str, None]:
            """
            Generates and streams a text response using the specified Gemini model ID.
            Yields text chunks.
            """
            target_model_id = model or self.model_id # Use override 'model' if provided
            model_to_use = self.genai_model # Default to initialized model

            # Handle model override
            if model and model != self.model_id:
                try:
                    if not self.api_key:
                         raise ValueError("Google Gemini API key is not configured for model override.")
                    genai.configure(api_key=self.api_key)
                    model_to_use = genai.GenerativeModel(target_model_id) # Use target_model_id
                except Exception as e:
                     raise ValueError(f"Failed to initialize requested Gemini model '{target_model_id}' for streaming: {e}") # Use target_model_id

            if not model_to_use:
                 raise ValueError(f"Gemini chat model '{target_model_id}' could not be used for streaming.") # Use target_model_id

            # Format history and the current message for generate_content
            formatted_history = [
                {"role": "model" if msg.role == "assistant" else msg.role, "parts": [msg.content]}
                for msg in history
            ]
            # Combine history with the current user message
            contents = formatted_history + [{"role": "user", "parts": [message]}]

            # Use generate_content with stream=True
            # Note: Using generate_content_async for FastAPI compatibility
            try:
                response_stream = await model_to_use.generate_content_async(
                    contents,
                    stream=True
                )
            except generation_types.BlockedPromptException as e:
                # Safety filter block - Treat as 400 Bad Request
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Stream content blocked by Gemini safety filters: {e}")
            except google.api_core.exceptions.PermissionDenied as e:
                # Map PermissionDenied (403)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Gemini Permission Denied during stream setup: {e}")
            except google.api_core.exceptions.ResourceExhausted as e:
                # Map ResourceExhausted (429)
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Gemini Quota/Rate Limit Exceeded during stream setup: {e}")
            except google.api_core.exceptions.InvalidArgument as e:
                 # Map InvalidArgument (400)
                 if "api key not valid" in str(e).lower():
                      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Gemini API Key during stream setup: {e}")
                 else:
                      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid Argument to Gemini during stream setup: {e}")
            except google.api_core.exceptions.Unauthenticated as e:
                 # Map Unauthenticated (401)
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini Authentication Failed during stream setup: {e}")
            except Exception as e:
                # Catch-all for other unexpected errors during streaming setup
                logging.exception(f"Unexpected error during Gemini streaming setup: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error during Gemini streaming setup: {e}")

            try:
                async for chunk in response_stream:
                    # Check for blocked content in the chunk
                    if not chunk.parts:
                        if chunk.prompt_feedback.block_reason:
                             # Log or handle the block reason appropriately
                             print(f"Streaming chunk blocked due to {chunk.prompt_feedback.block_reason.name}")
                             # Decide whether to yield an error message or just stop
                             break # Stop streaming if blocked
                        else:
                            # Empty chunk, might happen, just continue
                            continue
                    # Yield the text part of the chunk
                    # Sometimes chunk.text might raise if parts is empty, hence the check above
                    try:
                        yield chunk.text
                    except ValueError:
                         # Handle potential issue if chunk.text is accessed when parts is empty
                         # This might indicate the end or an issue.
                         print("Warning: Encountered chunk with no text content despite having parts.")
                         continue


            # --- Error Handling for Streaming Iteration ---
            # Catch specific Google API errors and re-raise as HTTPExceptions
            # Note: Error handling within an async generator is tricky.
            # Re-raising might terminate the generator. A common pattern is to yield an error message.
            # However, for failover, we need the exception to propagate *before* streaming starts if possible,
            # or handle it within the ModelRouter's stream loop if it occurs mid-stream.
            # Let's refine the error handling here to raise exceptions that ModelRouter can catch.

            except generation_types.BlockedPromptException as e:
                # Safety filter block - Treat as 400 Bad Request
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Stream content blocked by Gemini safety filters: {e}")
            except google.api_core.exceptions.PermissionDenied as e:
                # Map PermissionDenied (403)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Gemini Permission Denied during stream iteration: {e}")
            except google.api_core.exceptions.ResourceExhausted as e:
                # Map ResourceExhausted (429)
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Gemini Quota/Rate Limit Exceeded during stream iteration: {e}")
            except google.api_core.exceptions.InvalidArgument as e:
                 # Map InvalidArgument (400)
                 if "api key not valid" in str(e).lower():
                      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Gemini API Key during stream iteration: {e}")
                 else:
                      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid Argument to Gemini during stream iteration: {e}")
            except google.api_core.exceptions.Unauthenticated as e:
                 # Map Unauthenticated (401)
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Gemini Authentication Failed during stream iteration: {e}")
            except google.api_core.exceptions.InternalServerError as e:
                 # Explicitly catch InternalServerError during iteration
                 logging.exception(f"Gemini Internal Server Error during streaming iteration: {e}")
                 raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gemini Internal Server Error during streaming iteration: {e}")
            except Exception as e:
                # Catch-all for other unexpected errors during streaming iteration
                # Log the error properly
                logging.exception(f"Unexpected error during Gemini streaming iteration: {e}")
                # Raise a 500 error that ModelRouter can potentially handle or yield as an error chunk
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error during Gemini streaming iteration: {e}")
 
    # --- Thêm phương thức đếm token ---
    def count_tokens(self, content: str | list) -> int:
        """
        Counts the number of tokens in the given content using the initialized Gemini model.

        Args:
            content: The content to count tokens for. Can be a string or a list
                     of content parts compatible with the Gemini API (e.g., history format).

        Returns:
            The number of tokens.

        Raises:
            ValueError: If the model is not initialized or token counting fails.
        """
        if not self.genai_model:
            raise ValueError("Gemini model not initialized for token counting.")

        try:
            # count_tokens can accept a string, dict, or list of dicts
            token_count = self.genai_model.count_tokens(content)
            # The result might be an object with a total_tokens attribute
            if hasattr(token_count, 'total_tokens'):
                 return token_count.total_tokens
            elif isinstance(token_count, int): # Fallback if it directly returns an int (older versions?)
                 return token_count
            else:
                 # Handle unexpected return type
                 # logging should be imported at the top level
                 logging.error(f"Unexpected return type from count_tokens: {type(token_count)}")
                 raise ValueError("Failed to get token count from the count_tokens response.")

        except Exception as e:
            # logging should be imported at the top level
            logging.exception(f"Error counting Gemini tokens for model {self.model_id}: {e}")
            # Re-raise as ValueError or a more specific custom exception if needed
            raise ValueError(f"Failed to count tokens using Gemini model {self.model_id}: {e}")
