# app/core/supabase_client.py
import os
from supabase import create_client, Client
from .config import get_settings
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

@lru_cache()
def get_supabase_client() -> Client:
    """
    Khởi tạo và trả về một Supabase client.

    Sử dụng lru_cache để đảm bảo chỉ khởi tạo client một lần.
    Đọc URL và Service Role Key từ cài đặt.

    Raises:
        ValueError: Nếu SUPABASE_URL hoặc SUPABASE_SERVICE_ROLE_KEY không được cấu hình.

    Returns:
        Client: Đối tượng Supabase client đã được khởi tạo.
    """
    settings = get_settings()
    supabase_url = settings.SUPABASE_URL
    supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY

    if not supabase_url:
        logger.error("SUPABASE_URL is not set in the environment variables or .env file.")
        raise ValueError("SUPABASE_URL is not configured.")
    if not supabase_key:
        logger.error("SUPABASE_SERVICE_ROLE_KEY is not set in the environment variables or .env file.")
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY is not configured.")

    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized successfully.")
        return supabase
    except Exception as e:
        logger.exception(f"Failed to initialize Supabase client: {e}")
        raise

# Có thể export trực tiếp client nếu muốn, nhưng dùng hàm getter với cache thường linh hoạt hơn
# supabase_client = get_supabase_client()