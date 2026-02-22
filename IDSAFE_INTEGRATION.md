# IDSafe Integration Guide — Hyper AI Gateway

Tài liệu này mô tả trạng thái tích hợp hiện tại của Hyper AI Gateway với IDSafe sau khi đã chuyển hẳn khỏi Supabase SDK và dùng PostgreSQL thuần cho lưu trữ.

## 1. Kiến trúc tổng quan

1. Frontend (React SPA) dùng public client `hyper-ai-gateway` theo OIDC PKCE.
2. Backend (FastAPI) dùng confidential service client `hyper-ai-gateway-service` để:
   - lấy token bằng `client_credentials`
   - gọi API register nội bộ của IDSafe
3. PostgreSQL là data store duy nhất cho gateway:
   - `gateway_users` (projection identity)
   - `api_keys`
   - `user_provider_keys`
   - `provider_key_logs`

## 2. JWT Verification Policy

Backend verify JWT theo JWKS (`RS256`) với các rule:

1. Luôn verify: `signature`, `iss`, `exp`, `azp`.
2. `aud` là tuỳ chọn theo cờ `IDSAFE_VERIFY_AUD`:
   - `false` (mặc định): bỏ qua `aud`
   - `true`: bắt buộc `aud` chứa `IDSAFE_EXPECTED_AUDIENCE`

Sau khi verify JWT thành công, backend sẽ sync/upsert user vào `gateway_users` và auto-merge theo email nếu phù hợp.

## 3. Register Flow

Endpoint mới: `POST /api/v1/auth/register`

1. Backend lấy service token từ IDSafe token endpoint.
2. Backend gọi `IDSAFE_REGISTER_URL` (`/realms/{realm}/idsafe-api/user/register`).
3. Parse `sub/email/vnpay_id` từ response.
4. Upsert vào `gateway_users`.

Nếu response không có `sub`, backend trả lỗi `502` và không ghi partial mapping.

## 4. Cấu hình môi trường

### Backend

```bash
DATABASE_URL=postgresql://ai_gateway:***@postgres:5432/ai_gateway
DB_POOL_MIN_SIZE=1
DB_POOL_MAX_SIZE=10
APP_ENCRYPTION_KEY=<base64-encoded-32-byte-key>

IDSAFE_ISSUER_URL=https://idsafe.vnpay.dev/realms/idsafe-uat
IDSAFE_TOKEN_URL=https://idsafe.vnpay.dev/realms/idsafe-uat/protocol/openid-connect/token
IDSAFE_REGISTER_URL=https://idsafe.vnpay.dev/realms/idsafe-uat/idsafe-api/user/register
IDSAFE_SERVICE_CLIENT_ID=hyper-ai-gateway-service
IDSAFE_SERVICE_CLIENT_SECRET=***
IDSAFE_VERIFY_AUD=false
IDSAFE_EXPECTED_AUDIENCE=hyper-ai-gateway-service
IDSAFE_EXPECTED_AZP=hyper-ai-gateway
```

### Frontend

```bash
VITE_IDSAFE_URL=https://idsafe.vnpay.dev
VITE_IDSAFE_REALM=idsafe-uat
VITE_IDSAFE_CLIENT_ID=hyper-ai-gateway
```

## 5. Ghi chú vận hành

1. Dùng `db/migrations/0001..0003` để chuẩn hoá schema trước cutover.
2. Dùng `ops/migrate_live_supabase_to_postgres.sh` cho migration downtime.
3. Dùng `ops/verify_postgres_cutover.sh` để kiểm tra row-count, orphan và duplicate `vnpay_id`.
