import base64
import bcrypt
import logging
import secrets
import string
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
import jwt as pyjwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db import PostgresCompatClient as Client
from app.core.db import get_db_client

logger = logging.getLogger(__name__)

ALGORITHM = "RS256"

_jwks_clients: Dict[str, PyJWKClient] = {}
_jwks_lock = threading.Lock()
_idsafe_service_token_cache: Dict[str, Dict[str, Any]] = {}
_idsafe_service_token_lock = threading.Lock()

api_key_scheme = HTTPBearer(description="API Key authentication using 'hp_' prefixed keys.")
jwt_scheme = HTTPBearer(description="User authentication using JWT obtained from IDSafe (Keycloak OIDC).")

API_KEY_PREFIX = "hp_"
API_KEY_SECRET_LENGTH = 32
API_KEY_PREFIX_LOOKUP_LENGTH = 6


class TokenData(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None


def _get_jwks_client(issuer_url: str) -> PyJWKClient:
    if issuer_url not in _jwks_clients:
        with _jwks_lock:
            if issuer_url not in _jwks_clients:
                jwks_url = f"{issuer_url}/protocol/openid-connect/certs"
                _jwks_clients[issuer_url] = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
                logger.info("Created JWKS client for: %s", jwks_url)
    return _jwks_clients[issuer_url]


def _resolve_idsafe_token_url(settings: Any) -> str:
    if settings.IDSAFE_TOKEN_URL:
        return settings.IDSAFE_TOKEN_URL.rstrip("/")

    issuer_url = settings.IDSAFE_ISSUER_URL
    if not issuer_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi cấu hình xác thực phía máy chủ (missing IDSAFE_ISSUER_URL).",
        )
    return f"{issuer_url.rstrip('/')}/protocol/openid-connect/token"


def _normalize_audience_claim(aud_claim: Any) -> set[str]:
    if isinstance(aud_claim, str):
        return {aud_claim}
    if isinstance(aud_claim, list):
        return {item for item in aud_claim if isinstance(item, str)}
    return set()


def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    normalized = email.strip().lower()
    return normalized or None


def _claim_value(payload: Dict[str, Any], key: str) -> Optional[str]:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()

    attrs = payload.get("attributes")
    if isinstance(attrs, dict):
        attr_val = attrs.get(key)
        if isinstance(attr_val, list) and attr_val:
            first = attr_val[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
        if isinstance(attr_val, str) and attr_val.strip():
            return attr_val.strip()
    return None


def _extract_email(payload: Dict[str, Any]) -> Optional[str]:
    email = _claim_value(payload, "email")
    if email:
        return email

    preferred_username = payload.get("preferred_username")
    if isinstance(preferred_username, str) and "@" in preferred_username:
        return preferred_username.strip()
    return None


def _extract_vnpay_id(payload: Dict[str, Any]) -> Optional[str]:
    candidate_keys = [
        "vnpay_id",
        "vnpayId",
        "vnpayid",
        "taxIdUsername",
        "tax_id_username",
    ]
    for key in candidate_keys:
        value = _claim_value(payload, key)
        if value:
            return value
    return None


def _record_gateway_conflict(
    db: Client,
    conflict_type: str,
    idsafe_sub: Optional[str],
    email_norm: Optional[str],
    matched_subs: Optional[list[str]],
    details: Optional[str] = None,
) -> None:
    try:
        db.execute(
            """
            INSERT INTO gateway_user_conflicts (conflict_type, idsafe_sub, email_norm, matched_subs, details, created_at)
            VALUES (%s, %s, %s, %s, %s, now())
            """,
            (
                conflict_type,
                idsafe_sub,
                email_norm,
                matched_subs or [],
                details,
            ),
        )
    except Exception as err:
        logger.warning("Unable to record gateway_user_conflicts: %s", err)


def _upsert_gateway_user_by_sub(
    db: Client,
    idsafe_sub: str,
    email: Optional[str],
    email_norm: Optional[str],
    vnpay_id: Optional[str],
) -> Dict[str, Any]:
    try:
        rows = db.execute_returning(
            """
            INSERT INTO gateway_users (idsafe_sub, email, email_norm, vnpay_id, status, created_at, updated_at, last_login_at)
            VALUES (%s, %s, %s, %s, 'active', now(), now(), now())
            ON CONFLICT (idsafe_sub)
            DO UPDATE SET
                email = COALESCE(EXCLUDED.email, gateway_users.email),
                email_norm = COALESCE(EXCLUDED.email_norm, gateway_users.email_norm),
                vnpay_id = COALESCE(EXCLUDED.vnpay_id, gateway_users.vnpay_id),
                status = 'active',
                updated_at = now(),
                last_login_at = now()
            RETURNING gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status
            """,
            (idsafe_sub, email, email_norm, vnpay_id),
        )
        return rows[0]
    except Exception as err:
        # Common case: vnpay_id unique conflict with another row.
        logger.warning("gateway_users upsert conflict for sub=%s vnpay_id=%s: %s", idsafe_sub, vnpay_id, err)
        _record_gateway_conflict(
            db,
            conflict_type="UPSERT_CONFLICT",
            idsafe_sub=idsafe_sub,
            email_norm=email_norm,
            matched_subs=None,
            details=str(err),
        )
        rows = db.execute_returning(
            """
            INSERT INTO gateway_users (idsafe_sub, email, email_norm, status, created_at, updated_at, last_login_at)
            VALUES (%s, %s, %s, 'active', now(), now(), now())
            ON CONFLICT (idsafe_sub)
            DO UPDATE SET
                email = COALESCE(EXCLUDED.email, gateway_users.email),
                email_norm = COALESCE(EXCLUDED.email_norm, gateway_users.email_norm),
                status = 'active',
                updated_at = now(),
                last_login_at = now()
            RETURNING gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status
            """,
            (idsafe_sub, email, email_norm),
        )
        return rows[0]


def _upsert_gateway_user_provisional(
    db: Client,
    email: Optional[str],
    email_norm: Optional[str],
    vnpay_id: str,
) -> Dict[str, Any]:
    rows = db.execute_returning(
        """
        INSERT INTO gateway_users (idsafe_sub, email, email_norm, vnpay_id, status, created_at, updated_at, last_login_at)
        VALUES (NULL, %s, %s, %s, 'provisional', now(), now(), NULL)
        ON CONFLICT (vnpay_id)
        DO UPDATE SET
            email = COALESCE(EXCLUDED.email, gateway_users.email),
            email_norm = COALESCE(EXCLUDED.email_norm, gateway_users.email_norm),
            status = CASE
                WHEN gateway_users.idsafe_sub IS NULL THEN 'provisional'
                ELSE 'active'
            END,
            updated_at = now()
        RETURNING gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status
        """,
        (email, email_norm, vnpay_id),
    )
    return rows[0]


def _attach_sub_to_gateway_user(
    db: Client,
    gateway_user_id: Any,
    idsafe_sub: str,
    email: Optional[str],
    email_norm: Optional[str],
    vnpay_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    rows = db.execute_returning(
        """
        UPDATE gateway_users
        SET idsafe_sub = %s,
            email = COALESCE(%s, email),
            email_norm = COALESCE(%s, email_norm),
            vnpay_id = COALESCE(%s, vnpay_id),
            status = 'active',
            updated_at = now(),
            last_login_at = now()
        WHERE gateway_user_id = %s
        RETURNING gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status
        """,
        (idsafe_sub, email, email_norm, vnpay_id, gateway_user_id),
    )
    return rows[0] if rows else None


async def sync_or_reconcile_gateway_user(payload: Dict[str, Any], db: Client) -> Dict[str, Any]:
    raw_sub = payload.get("sub")
    idsafe_sub = raw_sub.strip() if isinstance(raw_sub, str) and raw_sub.strip() else None

    email = _extract_email(payload)
    email_norm = _normalize_email(email)
    vnpay_id = _extract_vnpay_id(payload)

    if not idsafe_sub and not vnpay_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không tìm thấy định danh user từ IDSafe (thiếu cả sub và vnpayId).",
        )

    if idsafe_sub:
        existing_by_sub = db.fetch_one(
            "SELECT gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status FROM gateway_users WHERE idsafe_sub = %s",
            (idsafe_sub,),
        )
        if existing_by_sub:
            return _upsert_gateway_user_by_sub(db, idsafe_sub, email, email_norm, vnpay_id)

        if vnpay_id:
            existing_by_vnpay = db.fetch_one(
                "SELECT gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status FROM gateway_users WHERE vnpay_id = %s",
                (vnpay_id,),
            )
            if existing_by_vnpay:
                existing_sub = existing_by_vnpay.get("idsafe_sub")
                if existing_sub and existing_sub != idsafe_sub:
                    _record_gateway_conflict(
                        db,
                        conflict_type="SUB_VNPAY_MISMATCH",
                        idsafe_sub=idsafe_sub,
                        email_norm=email_norm,
                        matched_subs=[existing_sub],
                        details=f"vnpay_id {vnpay_id} is already linked to another sub.",
                    )
                    return _upsert_gateway_user_by_sub(db, idsafe_sub, email, email_norm, None)

                attached = _attach_sub_to_gateway_user(
                    db,
                    existing_by_vnpay["gateway_user_id"],
                    idsafe_sub,
                    email,
                    email_norm,
                    vnpay_id,
                )
                if attached:
                    logger.info(
                        "Attached idsafe_sub to provisional gateway user. gateway_user_id=%s sub=%s",
                        existing_by_vnpay["gateway_user_id"],
                        idsafe_sub,
                    )
                    return attached

        if email_norm:
            email_matches = db.fetch_all(
                """
                SELECT gateway_user_id, idsafe_sub
                FROM gateway_users
                WHERE email_norm = %s
                ORDER BY created_at ASC
                """,
                (email_norm,),
            )
            if len(email_matches) == 1:
                match = email_matches[0]
                match_sub = match.get("idsafe_sub")
                if match_sub and match_sub != idsafe_sub:
                    _record_gateway_conflict(
                        db,
                        conflict_type="EMAIL_SUB_MISMATCH",
                        idsafe_sub=idsafe_sub,
                        email_norm=email_norm,
                        matched_subs=[match_sub],
                        details="Single email match belongs to another sub.",
                    )
                else:
                    try:
                        attached = _attach_sub_to_gateway_user(
                            db,
                            match["gateway_user_id"],
                            idsafe_sub,
                            email,
                            email_norm,
                            vnpay_id,
                        )
                        if attached:
                            logger.info(
                                "Auto-merged gateway user by email. gateway_user_id=%s sub=%s",
                                match["gateway_user_id"],
                                idsafe_sub,
                            )
                            return attached
                    except Exception as err:
                        logger.warning("Auto-merge by email failed sub=%s: %s", idsafe_sub, err)
                        _record_gateway_conflict(
                            db,
                            conflict_type="AUTO_MERGE_FAILED",
                            idsafe_sub=idsafe_sub,
                            email_norm=email_norm,
                            matched_subs=[match_sub] if match_sub else None,
                            details=str(err),
                        )

            elif len(email_matches) > 1:
                matched_subs = [row["idsafe_sub"] for row in email_matches if row.get("idsafe_sub")]
                _record_gateway_conflict(
                    db,
                    conflict_type="MULTIPLE_EMAIL_MATCH",
                    idsafe_sub=idsafe_sub,
                    email_norm=email_norm,
                    matched_subs=matched_subs or None,
                    details="Multiple gateway_users rows match same email_norm.",
                )

        return _upsert_gateway_user_by_sub(db, idsafe_sub, email, email_norm, vnpay_id)

    # Provisional register path: no sub yet, but we have vnpay_id.
    assert vnpay_id is not None

    existing_by_vnpay = db.fetch_one(
        "SELECT gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status FROM gateway_users WHERE vnpay_id = %s",
        (vnpay_id,),
    )
    if existing_by_vnpay:
        rows = db.execute_returning(
            """
            UPDATE gateway_users
            SET email = COALESCE(%s, email),
                email_norm = COALESCE(%s, email_norm),
                status = CASE
                    WHEN idsafe_sub IS NULL THEN 'provisional'
                    ELSE 'active'
                END,
                updated_at = now()
            WHERE gateway_user_id = %s
            RETURNING gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status
            """,
            (email, email_norm, existing_by_vnpay["gateway_user_id"]),
        )
        return rows[0]

    if email_norm:
        email_matches = db.fetch_all(
            """
            SELECT gateway_user_id, idsafe_sub
            FROM gateway_users
            WHERE email_norm = %s
            ORDER BY created_at ASC
            """,
            (email_norm,),
        )
        if len(email_matches) == 1 and not email_matches[0].get("idsafe_sub"):
            rows = db.execute_returning(
                """
                UPDATE gateway_users
                SET email = COALESCE(%s, email),
                    email_norm = COALESCE(%s, email_norm),
                    vnpay_id = COALESCE(%s, vnpay_id),
                    status = 'provisional',
                    updated_at = now()
                WHERE gateway_user_id = %s
                RETURNING gateway_user_id, idsafe_sub, email, email_norm, vnpay_id, status
                """,
                (email, email_norm, vnpay_id, email_matches[0]["gateway_user_id"]),
            )
            if rows:
                return rows[0]
        elif len(email_matches) > 1:
            matched_subs = [row["idsafe_sub"] for row in email_matches if row.get("idsafe_sub")]
            _record_gateway_conflict(
                db,
                conflict_type="MULTIPLE_EMAIL_MATCH_PROVISIONAL",
                idsafe_sub=None,
                email_norm=email_norm,
                matched_subs=matched_subs or None,
                details="Multiple rows match provisional register email.",
            )

    return _upsert_gateway_user_provisional(db, email, email_norm, vnpay_id)


async def get_idsafe_service_token(settings: Optional[Any] = None) -> str:
    settings = settings or get_settings()
    client_id = settings.IDSAFE_SERVICE_CLIENT_ID
    client_secret = settings.IDSAFE_SERVICE_CLIENT_SECRET

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Thiếu cấu hình IDSafe service client (IDSAFE_SERVICE_CLIENT_ID/IDSAFE_SERVICE_CLIENT_SECRET).",
        )

    token_url = _resolve_idsafe_token_url(settings)
    cache_key = f"{token_url}|{client_id}"
    now_ts = int(time.time())

    with _idsafe_service_token_lock:
        cached = _idsafe_service_token_cache.get(cache_key)
        if cached and int(cached.get("expires_at", 0)) - 30 > now_ts:
            access_token = cached.get("access_token")
            if isinstance(access_token, str) and access_token:
                return access_token

    token_payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(token_url, data=token_payload)
            response.raise_for_status()

        response_body = response.json()
        access_token = response_body.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không nhận được access token từ IDSafe.",
            )

        expires_in_raw = response_body.get("expires_in", 300)
        try:
            expires_in = max(int(expires_in_raw), 60)
        except (TypeError, ValueError):
            expires_in = 300

        with _idsafe_service_token_lock:
            _idsafe_service_token_cache[cache_key] = {
                "access_token": access_token,
                "expires_at": now_ts + expires_in,
            }
        return access_token

    except httpx.HTTPStatusError as err:
        logger.error("IDSafe token endpoint returned %s: %s", err.response.status_code, err.response.text)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IDSafe từ chối cấp service token (client_credentials).",
        )
    except (httpx.RequestError, httpx.TimeoutException) as err:
        logger.error("Cannot reach IDSafe token endpoint: %s", err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể kết nối token endpoint của IDSafe.",
        )


async def get_idsafe_service_auth_header(settings: Optional[Any] = None) -> Dict[str, str]:
    token = await get_idsafe_service_token(settings)
    return {"Authorization": f"Bearer {token}"}


def _generate_random_string(length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_api_key() -> Tuple[str, str, str]:
    secret_part = _generate_random_string(API_KEY_SECRET_LENGTH)
    full_api_key = f"{API_KEY_PREFIX}{secret_part}"
    key_prefix_lookup = secret_part[:API_KEY_PREFIX_LOOKUP_LENGTH]
    return full_api_key, key_prefix_lookup, secret_part


def hash_api_key(api_key: str) -> str:
    hashed_bytes = bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt())
    return hashed_bytes.decode("utf-8")


def verify_hashed_key(api_key: str, hashed_key: str) -> bool:
    try:
        return bcrypt.checkpw(api_key.encode("utf-8"), hashed_key.encode("utf-8"))
    except Exception:
        return False


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(api_key_scheme),
    db: Client = Depends(get_db_client),
) -> Dict[str, Any]:
    if credentials.scheme != "Bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Không đúng kiểu xác thực. Sử dụng Bearer token.")

    api_key = credentials.credentials
    if not api_key.startswith(API_KEY_PREFIX):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"API key không hợp lệ. Phải bắt đầu bằng '{API_KEY_PREFIX}'.")

    if len(api_key) != len(API_KEY_PREFIX) + API_KEY_SECRET_LENGTH:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Định dạng API key không hợp lệ (sai độ dài).")

    secret_part = api_key[len(API_KEY_PREFIX):]
    key_prefix_lookup = secret_part[:API_KEY_PREFIX_LOOKUP_LENGTH]

    response = db.table("api_keys").select("user_id, key_hash, is_active").eq("key_prefix", key_prefix_lookup).execute()
    candidates = response.data or []
    if not candidates:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key không hợp lệ hoặc không tồn tại.")

    for key_data in candidates:
        if not key_data.get("is_active"):
            continue
        stored_hash = key_data.get("key_hash")
        if stored_hash and verify_hashed_key(api_key, stored_hash):
            return {"user_id": key_data["user_id"], "key_prefix": key_prefix_lookup}

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key không hợp lệ.")


async def get_current_user_context(
    token: HTTPAuthorizationCredentials = Depends(jwt_scheme),
    settings: Any = Depends(get_settings),
    db: Client = Depends(get_db_client),
) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin đăng nhập",
        headers={"WWW-Authenticate": "Bearer"},
    )

    issuer_url = settings.IDSAFE_ISSUER_URL
    expected_audience = (settings.IDSAFE_EXPECTED_AUDIENCE or "").strip()
    expected_azp = settings.IDSAFE_EXPECTED_AZP
    verify_aud = bool(settings.IDSAFE_VERIFY_AUD)

    if not issuer_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi cấu hình xác thực phía máy chủ (missing IDSAFE_ISSUER_URL).")
    if not expected_azp:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi cấu hình xác thực phía máy chủ (missing IDSAFE_EXPECTED_AZP).")
    if verify_aud and not expected_audience:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi cấu hình xác thực phía máy chủ (missing IDSAFE_EXPECTED_AUDIENCE).")

    if token.scheme != "Bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yêu cầu JWT Bearer token.")

    try:
        jwks_client = _get_jwks_client(issuer_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token.credentials)
        payload = pyjwt.decode(
            token.credentials,
            signing_key.key,
            algorithms=[ALGORITHM],
            issuer=issuer_url,
            options={"verify_exp": True, "verify_aud": False},
        )

        user_sub = payload.get("sub")
        if not isinstance(user_sub, str) or not user_sub.strip():
            raise credentials_exception

        if verify_aud:
            aud_values = _normalize_audience_claim(payload.get("aud"))
            if expected_audience not in aud_values:
                raise credentials_exception

        azp = payload.get("azp")
        if azp != expected_azp:
            raise credentials_exception

        gateway_user = await sync_or_reconcile_gateway_user(payload, db)
        gateway_sub = gateway_user.get("idsafe_sub")
        if not isinstance(gateway_sub, str) or not gateway_sub.strip():
            raise credentials_exception

        return {
            "user_id": gateway_sub,
            "gateway_user_id": str(gateway_user.get("gateway_user_id")),
            "idsafe_sub": gateway_sub,
            "email": gateway_user.get("email"),
            "vnpay_id": gateway_user.get("vnpay_id"),
            "jwt_payload": payload,
            "token": token.credentials,
        }

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (pyjwt.PyJWTError, PyJWKClientError):
        raise credentials_exception


async def get_current_user(context: Dict[str, Any] = Depends(get_current_user_context)) -> str:
    return str(context["user_id"])


async def get_user_provider_keys(db: Client, user_id: str) -> Dict[str, str]:
    try:
        response = db.table("user_provider_keys").select("provider_name, api_key_encrypted").eq("user_id", user_id).eq("is_selected", True).execute()
        rows = response.data or []
        if not rows:
            return {}

        result: Dict[str, str] = {}
        for item in rows:
            provider = item.get("provider_name")
            encrypted_key = item.get("api_key_encrypted")
            if not provider or not encrypted_key:
                continue
            try:
                key = get_encryption_key()
                f = Fernet(base64.urlsafe_b64encode(key))
                result[provider] = f.decrypt(encrypted_key.encode()).decode()
            except Exception:
                logger.exception("Error decrypting provider key for provider=%s", provider)
        return result
    except Exception:
        logger.exception("Error retrieving provider keys for user=%s", user_id)
        return {}


def get_encryption_key() -> bytes:
    settings = get_settings()
    raw = settings.APP_ENCRYPTION_KEY
    if not raw:
        raise ValueError("APP_ENCRYPTION_KEY is missing")

    # Preferred format: base64-url-safe encoded Fernet source (decodes to 32 bytes).
    try:
        decoded = base64.urlsafe_b64decode(raw.encode())
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass

    raw_bytes = raw.encode("utf-8")
    if len(raw_bytes) == 32:
        return raw_bytes

    raise ValueError("APP_ENCRYPTION_KEY must decode to 32 bytes (or be a raw 32-byte string)")


async def verify_api_key_with_provider_keys(
    credentials: HTTPAuthorizationCredentials = Depends(api_key_scheme),
    db: Client = Depends(get_db_client),
) -> Dict[str, Any]:
    auth_data = await verify_api_key(credentials, db)
    user_id = auth_data.get("user_id")

    auth_info_to_return = {
        "user_id": user_id,
        "key_prefix": auth_data.get("key_prefix"),
        "provider_keys": {},
        "token": credentials.credentials,
    }

    if user_id:
        auth_info_to_return["provider_keys"] = await get_user_provider_keys(db, str(user_id))

    return auth_info_to_return
