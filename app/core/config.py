# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List, Optional

class Settings(BaseSettings):
    """Cài đặt chung cho ứng dụng"""
    # --- App Info ---
    APP_NAME: str = "AI Model Gateway"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Gateway service for multiple AI models including Gemini, Grok, Cloud Vision, GigaChat, etc."

    # --- API ---
    API_V1_STR: str = "/api/v1"

    # --- AI Model Settings ---
    GOOGLE_AI_STUDIO_API_KEY: str = ""
    GEMINI_VISION_MODEL_NAME: str = "gemini-2.0-flash"
    GEMINI_CHAT_MODEL_NAME: str = "gemini-2.5-pro-exp-03-25"

    # --- File Handling ---
    ALLOWED_CONTENT_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"]
    
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