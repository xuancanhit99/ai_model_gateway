# app/models/schemas.py
from pydantic import BaseModel


class VisionResponse(BaseModel): # Renamed from OCRResponse
    filename: str
    content_type: str
    extracted_text: str
    model_used: str


class ErrorResponse(BaseModel):
    detail: str
# --- Chat Schemas ---
class ChatMessage(BaseModel):
    """Represents a single message in the chat history. Standardized to use 'content'."""
    role: str # Standardized role: 'user' or 'assistant'
    content: str # Standardized field for text content

class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""
    message: str # The new message from the user
    history: list[ChatMessage] = [] # Optional chat history
    model_name: str | None = None # Optional model override

class ChatResponse(BaseModel):
    """Response model for the chat endpoint."""
    response_text: str
    model_used: str
