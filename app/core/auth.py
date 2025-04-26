# app/core/auth.py
import secrets
import string
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer # Added OAuth2PasswordBearer
from typing import Dict, Any, Tuple, Optional # Added Optional
import logging
from datetime import datetime, timedelta, timezone # Added datetime imports
from jose import JWTError, jwt # Added jose imports
from pydantic import BaseModel, Field # Added pydantic imports

from .config import get_settings # Import get_settings

from .supabase_client import get_supabase_client
from supabase import Client

logger = logging.getLogger(__name__)
# Configure logging level if needed (e.g., in main.py or via environment variable)
# logging.basicConfig(level=logging.DEBUG) # Example: Set level to DEBUG

# --- Constants ---
ALGORITHM = "HS256" # Algorithm used by Supabase for JWT

# --- Security Schemes ---
# For API Key authentication (hp_...)
api_key_scheme = HTTPBearer(description="API Key authentication using 'hp_' prefixed keys.")
# For User JWT authentication (from Supabase Auth)
jwt_scheme = HTTPBearer(description="User authentication using JWT obtained from Supabase Auth.")


# --- Pydantic Models ---
class TokenData(BaseModel):
    """Pydantic model for JWT payload data (relevant fields)."""
    sub: Optional[str] = None # Subject (usually the user ID in Supabase JWT)
    exp: Optional[int] = None # Expiration time


# --- API Key Constants ---
API_KEY_PREFIX = "hp_"
API_KEY_SECRET_LENGTH = 32 # Độ dài phần bí mật của key
API_KEY_PREFIX_LOOKUP_LENGTH = 6 # Số ký tự đầu của secret dùng để tra cứu nhanh

# --- Helper Functions for Key Generation ---

def _generate_random_string(length: int) -> str:
    """Tạo chuỗi ngẫu nhiên an toàn."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

def generate_api_key() -> Tuple[str, str, str]:
    """
    Tạo API key mới, prefix tra cứu và secret.
    Returns:
        Tuple[str, str, str]: (full_api_key, key_prefix_lookup, secret_part)
        Ví dụ: ('hp_abcdef123...', 'abcdef', 'abcdef123...')
    """
    secret_part = _generate_random_string(API_KEY_SECRET_LENGTH)
    full_api_key = f"{API_KEY_PREFIX}{secret_part}"
    key_prefix_lookup = secret_part[:API_KEY_PREFIX_LOOKUP_LENGTH]
    return full_api_key, key_prefix_lookup, secret_part # Trả về secret để hash

def hash_api_key(api_key: str) -> str:
    """
    Hash toàn bộ API key sử dụng bcrypt.
    Args:
        api_key (str): API key đầy đủ (ví dụ: 'hp_abcdef123...').
    Returns:
        str: Chuỗi hash bcrypt.
    """
    hashed_bytes = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')

def verify_hashed_key(api_key: str, hashed_key: str) -> bool:
    """
    Kiểm tra API key có khớp với hash đã lưu không.
    Args:
        api_key (str): API key đầy đủ người dùng cung cấp.
        hashed_key (str): Hash lưu trong database.
    Returns:
        bool: True nếu khớp, False nếu không.
    """
    try:
        return bcrypt.checkpw(api_key.encode('utf-8'), hashed_key.encode('utf-8'))
    except ValueError:
        # Xử lý trường hợp hash không hợp lệ (ví dụ: sai định dạng)
        logger.warning(f"Invalid hash format encountered for key starting with {api_key[:10]}...")
        return False
    except Exception as e:
        logger.error(f"Error verifying password hash: {e}")
        return False


# --- Authentication Dependency ---

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(api_key_scheme), # Use api_key_scheme
    supabase: Client = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """
    Xác thực API key trong header Authorization sử dụng Supabase.

    1. Kiểm tra scheme 'Bearer'.
    2. Kiểm tra prefix 'hp_'.
    3. Tách prefix tra cứu (6 ký tự đầu sau 'hp_').
    4. Query Supabase để lấy các key có prefix trùng khớp.
    5. So sánh hash của key đầy đủ với hash trong DB bằng bcrypt.
    6. Trả về thông tin user nếu hợp lệ.
    """
    if credentials.scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không đúng kiểu xác thực. Sử dụng Bearer token."
        )

    api_key = credentials.credentials
    if not api_key.startswith(API_KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"API key không hợp lệ. Phải bắt đầu bằng '{API_KEY_PREFIX}'."
        )

    if len(api_key) != len(API_KEY_PREFIX) + API_KEY_SECRET_LENGTH:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Định dạng API key không hợp lệ (sai độ dài)."
        )

    secret_part = api_key[len(API_KEY_PREFIX):]
    key_prefix_lookup = secret_part[:API_KEY_PREFIX_LOOKUP_LENGTH]

    try:
        # Query Supabase for potential matches based on the prefix lookup
        response = supabase.table("api_keys") \
                                 .select("user_id, key_hash, is_active") \
                                 .eq("key_prefix", key_prefix_lookup) \
                                 .execute()

        if not response.data:
            logger.warning(f"No API key found for prefix lookup: {key_prefix_lookup}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key không hợp lệ hoặc không tồn tại."
            )

        # Iterate through potential matches and verify the full key hash
        for key_data in response.data:
            if not key_data.get('is_active', False):
                logger.debug(f"Key with prefix {key_prefix_lookup} is inactive.")
                continue # Bỏ qua key không hoạt động

            stored_hash = key_data.get('key_hash')
            if not stored_hash:
                 logger.error(f"Missing key_hash for key with prefix {key_prefix_lookup}")
                 continue # Bỏ qua nếu thiếu hash

            if verify_hashed_key(api_key, stored_hash):
                # Key hợp lệ và hoạt động
                logger.info(f"API Key validated successfully for user_id: {key_data['user_id']}")
                # Có thể cập nhật last_used_at ở đây (bất đồng bộ) nếu cần
                # await update_last_used(supabase, key_prefix_lookup, api_key) # Ví dụ
                return {"user_id": key_data['user_id'], "key_prefix": key_prefix_lookup}

        # Nếu không có key nào khớp sau khi kiểm tra hash
        logger.warning(f"API key provided failed hash verification for prefix lookup: {key_prefix_lookup}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key không hợp lệ."
        )

    except HTTPException as e:
        # Re-raise HTTPExceptions để FastAPI xử lý
        raise e
    except Exception as e:
        logger.exception(f"Lỗi trong quá trình xác thực API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi máy chủ nội bộ trong quá trình xác thực."
        )

# Hàm ví dụ để cập nhật last_used (chưa hoàn chỉnh, cần logic bất đồng bộ)
# async def update_last_used(supabase: Client, key_prefix: str, full_key: str):
#     try:
#         # Cần tìm đúng key dựa trên hash đầy đủ hoặc ID duy nhất nếu có
#         # Đây chỉ là ví dụ đơn giản, cần cẩn thận với race condition
#         # và hiệu năng khi cập nhật thường xuyên.
#         # Có thể cần một cột ID duy nhất cho mỗi key.
#         from datetime import datetime, timezone
#         await supabase.table("api_keys") \
#                       .update({"last_used_at": datetime.now(timezone.utc).isoformat()}) \
#                       .eq("key_prefix", key_prefix) \
#                       .execute() # Cẩn thận: Điều này cập nhật tất cả key cùng prefix!
#         logger.debug(f"Updated last_used_at for key prefix {key_prefix}")
#     except Exception as e:
#         logger.error(f"Failed to update last_used_at for key prefix {key_prefix}: {e}")


# --- JWT Authentication Dependency ---

async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(jwt_scheme),
    settings: Any = Depends(get_settings) # Inject settings
) -> str:
    """
    Giải mã và xác thực JWT từ header Authorization để lấy user ID.

    Args:
        token (HTTPAuthorizationCredentials): Token Bearer từ header.
        settings (Settings): Đối tượng cài đặt ứng dụng.

    Raises:
        HTTPException: 401 nếu token không hợp lệ, hết hạn, hoặc thiếu secret.
                       403 nếu token hợp lệ nhưng không có user ID (sub).

    Returns:
        str: User ID (UUID) từ payload của token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin đăng nhập",
        headers={"WWW-Authenticate": "Bearer"},
    )
    jwt_secret = settings.SUPABASE_JWT_SECRET
    if not jwt_secret:
        logger.error("SUPABASE_JWT_SECRET is not configured. Cannot verify JWT.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, # Use 500 for server config error
            detail="Lỗi cấu hình xác thực phía máy chủ."
        )

    if token.scheme != "Bearer":
         logger.warning(f"Invalid token scheme received: {token.scheme}")
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu JWT Bearer token."
        )

    logger.debug(f"Attempting to decode JWT: {token.credentials[:10]}...") # Log first 10 chars

    try:
        payload = jwt.decode(
            token.credentials,
            jwt_secret,
            algorithms=[ALGORITHM],
            audience='authenticated' # Specify the expected audience for Supabase JWTs
        )
        logger.debug(f"JWT payload decoded successfully: {payload}") # Log payload đã giải mã

        user_id: Optional[str] = payload.get("sub")
        expiration: Optional[int] = payload.get("exp")

        if user_id is None:
            logger.error("JWT payload missing 'sub' (user ID). Payload: %s", payload)
            raise credentials_exception # Or a more specific 403 Forbidden

        # Check expiration (jose might do this, but double-checking is safe)
        if expiration is None:
             logger.error("JWT payload missing 'exp' (expiration time). Payload: %s", payload)
             raise credentials_exception
        elif datetime.now(timezone.utc) > datetime.fromtimestamp(expiration, timezone.utc):
            logger.warning(f"JWT token has expired for user {user_id}. Expiry: {datetime.fromtimestamp(expiration, timezone.utc)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token đã hết hạn",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Token is valid, return the user ID
        logger.info(f"JWT validated successfully for user_id: {user_id}")
        return user_id

    except JWTError as e:
        # Log lỗi cụ thể từ thư viện jose
        logger.error(f"JWT validation error: {e}", exc_info=True)
        raise credentials_exception
    except Exception as e:
        logger.exception(f"Unexpected error during JWT validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi máy chủ nội bộ trong quá trình xác thực JWT."
        )