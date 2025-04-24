# app/services/gemini.py
import google.generativeai as genai
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
            response = self.genai_model.generate_content([final_prompt, image_part])
            # Accessing response.text directly might raise if the response was blocked or empty
            if not response.parts:
                 # Handle cases where the response might be empty due to safety or other reasons
                 if response.prompt_feedback.block_reason:
                     raise generation_types.BlockedPromptException(f"Prompt blocked due to {response.prompt_feedback.block_reason.name}")
                 else:
                     return "", self.model_id # Return empty string and model ID
            # Return extracted text and the model ID used
            return response.text, self.model_id
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
            return response.text, target_model_id # Return target_model_id
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
