# app/models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import time
import uuid


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
    model: str | None = None # Changed from model_name to model

class ChatResponse(BaseModel):
    """Response model for the chat endpoint."""
    response_text: str
    model_used: str

# --- OpenAI Compatible Schemas ---
class ChatCompletionMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str

class ChatCompletionRequest(BaseModel):
    model: str  # Format: "provider/model_name" (e.g. "google/gemini-2.5-pro-exp-03-25")
    messages: List[ChatCompletionMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None

class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatCompletionMessage
    finish_reason: str = "stop"

class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:10]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str

class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelInfo]
