# app/services/gemini.py
import google.generativeai as genai
from google.generativeai.types import generation_types # Import specific types for error handling
from typing import AsyncGenerator # Add this import
from app.core.config import get_settings
from app.models.schemas import ChatMessage # Import ChatMessage schema
from fastapi import HTTPException, status

settings = get_settings()


class GeminiService:
    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.model = None
        self.api_key = api_key or settings.GOOGLE_AI_STUDIO_API_KEY
        # Default to the chat model; the dependency function for vision will override if needed
        self.model_name = model_name or settings.GEMINI_CHAT_MODEL_NAME
        self._initialize_model()

    def _initialize_model(self):
        if not self.api_key:
            raise ValueError("Google Gemini API key is not set")

        genai.configure(api_key=self.api_key)
        try:
            self.model = genai.GenerativeModel(self.model_name)
        except Exception as e:
            # More specific error for model initialization
            raise ValueError(f"Failed to initialize Gemini model '{self.model_name}': {e}")

    async def extract_text(self, image_data: bytes, content_type: str, prompt: str | None = None) -> str:
        """Extracts text from an image using the configured Gemini vision model."""
        if not self.model:
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
            response = self.model.generate_content([final_prompt, image_part])
            # Accessing response.text directly might raise if the response was blocked or empty
            if not response.parts:
                 # Handle cases where the response might be empty due to safety or other reasons
                 if response.prompt_feedback.block_reason:
                     raise generation_types.BlockedPromptException(f"Prompt blocked due to {response.prompt_feedback.block_reason.name}")
                 else:
                     return "" # Or raise an error if empty response is unexpected
            return response.text
        except generation_types.BlockedPromptException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Content blocked by Gemini safety filters: {e}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing image with Gemini: {e}"
            )

    async def generate_text_response(
        self,
        message: str,
        history: list[ChatMessage],
        model_name_override: str | None = None
    ) -> tuple[str, str]: # Return response text and model used
        """
        Generates a text response using the specified or default Gemini text model,
        considering chat history.
        """
        # Determine which model to use
        target_model_name = model_name_override or self.model_name
        model_to_use = self.model # Default to the initialized model

        # If an override is specified and it's different from the default initialized model,
        # try to initialize a temporary model instance for this request.
        # Note: This creates a new model object per request if overridden.
        # Consider caching or a different approach if performance becomes an issue.
        if model_name_override and model_name_override != self.model_name:
            try:
                # Ensure API key is configured before trying to create a new model
                if not self.api_key:
                     raise ValueError("Google Gemini API key is not configured for model override.")
                genai.configure(api_key=self.api_key) # Ensure configuration is set
                model_to_use = genai.GenerativeModel(target_model_name)
            except Exception as e:
                 raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to initialize requested Gemini model '{target_model_name}': {e}"
                )

        if not model_to_use:
             # This should ideally not happen if initialization worked or default model exists
             raise HTTPException(
                 status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                 detail=f"Gemini chat model '{target_model_name}' could not be used."
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
                     return "Model did not provide a response.", target_model_name
 
             # Return both the text and the actual model name used
            return response.text, target_model_name
        except generation_types.BlockedPromptException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chat content blocked by Gemini safety filters: {e}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating chat response with Gemini: {e}"
            )

    async def stream_text_response(
            self,
            message: str,
            history: list[ChatMessage],
            model_name_override: str | None = None
        ) -> AsyncGenerator[str, None]:
            """
            Generates and streams a text response using the specified Gemini model.
            Yields text chunks.
            """
            target_model_name = model_name_override or self.model_name
            model_to_use = self.model

            # Handle model override (similar logic to non-streaming method)
            if model_name_override and model_name_override != self.model_name:
                try:
                    if not self.api_key:
                         raise ValueError("Google Gemini API key is not configured for model override.")
                    genai.configure(api_key=self.api_key)
                    model_to_use = genai.GenerativeModel(target_model_name)
                except Exception as e:
                     # In a streaming context, raising HTTPException might not be ideal.
                     # Yielding an error message or logging might be better.
                     # For now, let's re-raise to be caught by the router.
                     raise ValueError(f"Failed to initialize requested Gemini model '{target_model_name}' for streaming: {e}")

            if not model_to_use:
                 raise ValueError(f"Gemini chat model '{target_model_name}' could not be used for streaming.")

            # Format history and the current message for generate_content
            formatted_history = [
                {"role": "model" if msg.role == "assistant" else msg.role, "parts": [msg.content]}
                for msg in history
            ]
            # Combine history with the current user message
            contents = formatted_history + [{"role": "user", "parts": [message]}]

            try:
                # Use generate_content with stream=True
                # Note: Using generate_content_async for FastAPI compatibility
                response_stream = await model_to_use.generate_content_async(
                    contents,
                    stream=True
                )
    
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


            except generation_types.BlockedPromptException as e:
                # This might be caught before streaming starts
                print(f"Initial prompt blocked by Gemini safety filters: {e}")
                # Yield an error message or raise? Yielding might be safer for SSE.
                yield f"[ERROR: Initial prompt blocked by safety filter - {e}]"
            except Exception as e:
                print(f"Error during Gemini streaming generation: {e}")
                # Yield an error message
                yield f"[ERROR: Internal server error during streaming - {e}]"
