# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv() # Ensure .env is loaded

class Settings(BaseSettings):
    """Cài đặt chung cho ứng dụng"""
    # --- App Info ---
    APP_NAME: str = "AI Model Gateway"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Gateway service for multiple AI models including Gemini, Grok, Cloud Vision, GigaChat, etc."

    # --- API ---
    API_V1_STR: str = "/api/v1"

    # --- AI Model Settings ---
    GOOGLE_AI_STUDIO_API_KEY: Optional[str] = None
    GEMINI_VISION_MODEL_NAME: str = "gemini-2.0-flash"
    GEMINI_CHAT_MODEL_NAME: str = "gemini-2.5-pro-exp-03-25"

    # --- Grok Settings ---
    XAI_API_KEY: Optional[str] = None # Allow None if key might be passed via header
    XAI_API_BASE_URL: str = "https://api.x.ai/v1" # Default Grok API base
    GROK_CHAT_MODEL_NAME: str = "grok-2-1212" # Example text model
    GROK_VISION_MODEL_NAME: str = "grok-2-vision-1212" # Example vision model

    # --- GigaChat Settings ---
    GIGACHAT_AUTH_KEY: Optional[str] = None # Authorization key for GigaChat (e.g., from .env or header)
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"
    GIGACHAT_TOKEN_URL: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    GIGACHAT_CHAT_URL: str = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions" # Removed trailing '='
    GIGACHAT_DEFAULT_MODEL: str = "GigaChat-Pro" # Default model if needed

    # --- File Handling ---
    # Allowed content types for each service
    GEMINI_ALLOWED_CONTENT_TYPES: List[str] = Field(default_factory=lambda: [
        "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"
    ])
    GROK_ALLOWED_CONTENT_TYPES: List[str] = Field(default_factory=lambda: [
        "image/jpeg", "image/png" # As specified for Grok
    ])

    # --- Pydantic Settings Config ---
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

@lru_cache()
def get_settings():
    """Lấy đối tượng settings và lưu vào bộ nhớ cache để tránh khởi tạo lại nhiều lần"""
    return Settings()