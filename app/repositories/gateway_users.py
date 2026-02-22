from typing import Any, Dict, Optional

from app.core.db import PostgresCompatClient


def get_by_idsafe_sub(db: PostgresCompatClient, idsafe_sub: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        "SELECT idsafe_sub, email, email_norm, vnpay_id, legacy_user_id, status, created_at, updated_at, last_login_at FROM gateway_users WHERE idsafe_sub = %s",
        (idsafe_sub,),
    )


def list_by_email_norm(db: PostgresCompatClient, email_norm: str) -> list[Dict[str, Any]]:
    return db.fetch_all(
        "SELECT idsafe_sub, email, vnpay_id, status FROM gateway_users WHERE email_norm = %s ORDER BY created_at ASC",
        (email_norm,),
    )


def upsert_gateway_user(
    db: PostgresCompatClient,
    idsafe_sub: str,
    email: Optional[str],
    email_norm: Optional[str],
    vnpay_id: Optional[str],
) -> Dict[str, Any]:
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
        RETURNING idsafe_sub, email, vnpay_id, status
        """,
        (idsafe_sub, email, email_norm, vnpay_id),
    )
    return rows[0]


def record_conflict(
    db: PostgresCompatClient,
    conflict_type: str,
    idsafe_sub: Optional[str],
    email_norm: Optional[str],
    matched_subs: Optional[list[str]],
    details: Optional[str],
) -> None:
    db.execute(
        """
        INSERT INTO gateway_user_conflicts (conflict_type, idsafe_sub, email_norm, matched_subs, details, created_at)
        VALUES (%s, %s, %s, %s, %s, now())
        """,
        (conflict_type, idsafe_sub, email_norm, matched_subs or [], details),
    )
