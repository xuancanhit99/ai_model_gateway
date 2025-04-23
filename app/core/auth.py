# app/core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any

# Tạo một lược đồ bảo mật (security scheme)
security = HTTPBearer()

# Đây chỉ là ví dụ, trong thực tế bạn nên lưu trữ API key trong cơ sở dữ liệu
# hoặc sử dụng phương pháp bảo mật hơn
VALID_API_KEYS = {
    "sk-openhyper123456789abcdef": {"user_id": "default"},
    # Thêm các API key khác ở đây
}

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Xác thực API key trong header Authorization."""
    if credentials.scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không đúng kiểu xác thực. Sử dụng Bearer token."
        )
    
    api_key = credentials.credentials
    if not api_key.startswith("sk-"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key không hợp lệ. Phải bắt đầu bằng 'sk-'."
        )
    
    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key không hợp lệ hoặc đã hết hạn."
        )
    
    return VALID_API_KEYS[api_key]