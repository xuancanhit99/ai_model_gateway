# app/core/config.py
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Cài đặt chung cho ứng dụng."""
    APP_NAME: str = "AI Model Gateway"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Gateway service for multiple AI models including Gemini, Grok, Cloud Vision, GigaChat, Perplexity Sonar, etc."

    API_V1_STR: str = "/api/v1"
    API_BASE_URL: str = "http://ai_gateway_service:6161"

    # PostgreSQL
    DATABASE_URL: str = "postgresql://ai_gateway:ai_gateway_change_me@postgres:5432/ai_gateway"
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 10
    DB_AUTO_MIGRATE: bool = True

    # App secrets
    APP_ENCRYPTION_KEY: Optional[str] = None

    # AI model settings
    GOOGLE_AI_STUDIO_API_KEY: Optional[str] = None
    GEMINI_VISION_MODEL_NAME: str = "gemini-2.0-flash"
    GEMINI_CHAT_MODEL_NAME: str = "gemini-2.5-pro-exp-03-25"

    XAI_API_KEY: Optional[str] = None
    XAI_API_BASE_URL: str = "https://api.x.ai/v1"
    GROK_CHAT_MODEL_NAME: str = "grok-2-1212"
    GROK_VISION_MODEL_NAME: str = "grok-2-vision-1212"

    GIGACHAT_AUTH_KEY: Optional[str] = None
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"
    GIGACHAT_TOKEN_URL: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    GIGACHAT_CHAT_URL: str = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    GIGACHAT_DEFAULT_MODEL: str = "GigaChat-Pro"

    PERPLEXITY_API_KEY: Optional[str] = None
    PERPLEXITY_API_BASE_URL: str = "https://api.perplexity.ai"
    SONAR_DEFAULT_MODEL: str = "sonar"

    GEMINI_ALLOWED_CONTENT_TYPES: List[str] = Field(default_factory=lambda: [
        "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"
    ])
    GROK_ALLOWED_CONTENT_TYPES: List[str] = Field(default_factory=lambda: [
        "image/jpeg", "image/png"
    ])

    # IDSafe / Keycloak
    IDSAFE_ISSUER_URL: Optional[str] = None
    IDSAFE_TOKEN_URL: Optional[str] = None
    IDSAFE_REGISTER_URL: str = "https://idsafe.vnpay.dev/realms/idsafe-uat/idsafe-api/user/register"
    IDSAFE_VERIFY_AUD: bool = False
    IDSAFE_EXPECTED_AUDIENCE: Optional[str] = None
    IDSAFE_EXPECTED_AZP: str = "hyper-ai-gateway"
    IDSAFE_SERVICE_CLIENT_ID: Optional[str] = None
    IDSAFE_SERVICE_CLIENT_SECRET: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Lấy đối tượng settings và cache để dùng lại."""
    return Settings()
