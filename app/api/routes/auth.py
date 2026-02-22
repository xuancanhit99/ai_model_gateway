import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import get_idsafe_service_token, sync_or_reconcile_gateway_user
from app.core.config import get_settings
from app.core.db import PostgresCompatClient as Client
from app.core.db import get_db_client

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    phone: str = Field(..., min_length=8, max_length=20)
    firstname: str = Field(..., min_length=1, max_length=100)
    lastname: str = Field(..., min_length=1, max_length=100)
    attributes: Optional[Dict[str, List[str] | str]] = None


class RegisterResponse(BaseModel):
    gateway_user_id: str
    sub: Optional[str] = None
    email: Optional[str] = None
    vnpay_id: Optional[str] = None
    idsafe_response: Dict[str, Any]


def _extract_scalar_string(value: Any) -> Optional[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                normalized = item.strip()
                if normalized:
                    return normalized

    return None


def _recursive_find_first(data: Any, accepted_keys: set[str]) -> Optional[str]:
    if isinstance(data, dict):
        for key, value in data.items():
            if key in accepted_keys:
                extracted = _extract_scalar_string(value)
                if extracted:
                    return extracted
            nested = _recursive_find_first(value, accepted_keys)
            if nested:
                return nested
    elif isinstance(data, list):
        for item in data:
            nested = _recursive_find_first(item, accepted_keys)
            if nested:
                return nested
    return None


def _extract_register_claims(body: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    sub = _recursive_find_first(body, {"sub", "userId", "user_id", "idsafeSub"})
    email = _recursive_find_first(body, {"email"})
    vnpay_id = _recursive_find_first(body, {"vnpay_id", "vnpayId", "taxIdUsername"})
    return sub, email, vnpay_id


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user at IDSafe then sync local gateway_users projection",
)
async def register_user(
    req: RegisterRequest,
    db: Client = Depends(get_db_client),
) -> RegisterResponse:
    settings = get_settings()
    service_client_id = settings.IDSAFE_SERVICE_CLIENT_ID
    if not service_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Thiếu IDSAFE_SERVICE_CLIENT_ID.",
        )

    payload: Dict[str, Any] = {
        "reqId": str(uuid.uuid4()),
        "firstname": req.firstname,
        "lastname": req.lastname,
        "email": req.email,
        "phone": req.phone,
        "attributes": {
            "address": [""],
            "taxIdUsername": [""],
            "userType": ["1"],
            "nationId": [""],
            "nationIdType": [""],
            "idIssueDate": [""],
            "gender": [""],
            "placeOfIssue": [""],
            "dob": [""],
            "authenticate_by": ["email"],
            "legacySource": [service_client_id],
        },
    }

    if req.attributes:
        payload["attributes"].update(req.attributes)

    access_token = await get_idsafe_service_token(settings)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(settings.IDSAFE_REGISTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            resp_body = resp.json()
    except httpx.HTTPStatusError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"IDSafe register error: {err.response.status_code} {err.response.text}",
        )
    except (httpx.RequestError, httpx.TimeoutException) as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Không thể kết nối IDSafe register endpoint: {err}",
        )

    sub, email, vnpay_id = _extract_register_claims(resp_body)
    if not sub and not vnpay_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="IDSafe register response thiếu cả sub/userId và vnpayId.",
        )

    gateway_user = await sync_or_reconcile_gateway_user(
        {
            "sub": sub,
            "email": email or str(req.email),
            "vnpay_id": vnpay_id,
            "attributes": resp_body.get("attributes", {}),
        },
        db,
    )

    return RegisterResponse(
        gateway_user_id=str(gateway_user["gateway_user_id"]),
        sub=gateway_user["idsafe_sub"],
        email=gateway_user.get("email"),
        vnpay_id=gateway_user.get("vnpay_id"),
        idsafe_response=resp_body,
    )
