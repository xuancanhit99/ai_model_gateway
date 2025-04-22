# app/services/gemini.py
import google.generativeai as genai
from google.generativeai.types import generation_types # Import specific types for error handling
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
            # Ensure generate_content is awaited if it becomes async in future versions
            # Currently, it seems synchronous in the library for standard calls
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
            # Log the exception e here for debugging
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
            # Send the new message - this seems synchronous in the current library version
            response = chat.send_message(message)

            # Check for empty/blocked response similar to extract_text
            if not response.parts:
                 if response.prompt_feedback.block_reason:
                     raise generation_types.BlockedPromptException(f"Prompt blocked due to {response.prompt_feedback.block_reason.name}")
                 else:
                     # Decide how to handle empty responses in chat - maybe return a specific message
                     return "Model did not provide a response."

            # Return both the text and the actual model name used
            return response.text, target_model_name
        except generation_types.BlockedPromptException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chat content blocked by Gemini safety filters: {e}"
            )
        except Exception as e:
            # Log the exception e here for debugging
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating chat response with Gemini: {e}"
            )
