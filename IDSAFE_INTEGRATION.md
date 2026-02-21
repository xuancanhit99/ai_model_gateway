# IDSafe Integration Guide — Hyper AI Gateway

Tài liệu này tổng hợp lại các cấu hình, thay đổi kỹ thuật, và kiến trúc hệ thống sau khi tích hợp thành công giải pháp đăng nhập tập trung **IDSafe (Keycloak OIDC)** vào hệ thống **Hyper AI Model Gateway**, thay thế cho hệ thống xác thực cũ của Supabase.

Supabase hiện tại chỉ còn đóng vai trò Data Storage (Provider Keys, Activity Logs).

## 1. Kiến Trúc Xác Thực (Authentication Architecture)

Hệ thống sử dụng mô hình xác thực qua 2 Clients độc lập trên IDSafe để bảo mật tối đa:

1. **Frontend (React SPA)**: Sử dụng **Public Client** với luồng PKCE (Proof Key for Code Exchange).
   - *Client ID*: `hyper-ai-gateway`
   - Bắt buộc vì Frontend không thể lưu trữ `client_secret` an toàn.
2. **Backend (FastAPI)**: Sử dụng **Confidential Client** với `client_secret` để thực hiện các nghiệp vụ Service Account.
   - *Client ID*: `hyper-ai-gateway-service`
   - *Quyền hạn*: Được cấp Role `call-spi-service` và `manage-users` trong `realm-management` để có thể gọi các Custom API nội bộ của IDSafe (như API tạo User).

> **LƯU Ý QUAN TRỌNG:**
> Cả 2 client trên IDSafe đều phải được cấu hình chung thuộc tính `legacySource` là `hyper-ai-gateway-service` để IDSafe có thể đồng bộ thông tin Account.

---

## 2. Chi Tiết Những Thay Đổi Code (Changelog)

### 2.1. Backend (FastAPI)
- **Xác thực JWT:** Chuyển từ việc verify JWT qua `SUPABASE_JWT_SECRET` sang verify qua bộ khoá công khai JWT (JWKS) của Keycloak theo chuẩn OIDC RS256.
- **Thư viện:** 
  - Gỡ endpoint Supabase cũ, cài đặt thư viện `PyJWT[crypto]` thao tác JWKS.
  - Cài thêm `cachetools` giúp hệ thống lưu cache public key `certs` thay vì liên tục gọi HTTP đến IDSafe mỗi khi có Request mới.
- **API Keys Authentication**: Cơ chế Check API Key của Application vẫn được giữ nguyên và Query từ Database Supabase như cũ (`verify_api_key`).

### 2.2. Frontend (React / Vite)
- **Thư viện:** 
  - Gỡ bỏ thư viện `@supabase/auth-ui-react`.
  - Cài đặt thư viện chính thức `keycloak-js`.
- **Cơ chế Login (App.tsx):** 
  - Thay vì render UI Auth của Supabase, giờ tự động Redirection người dùng sang trang Đăng nhập tập trung của IDSafe.
  - Sau khi đăng nhập xong IDSafe sẽ callback kèm Code để đổi lấy `access_token` và `id_token`.
- **Lưu Session:** 
  - Token được lưu tạm vào `localStorage` (gồm `kc_token`, `kc_refreshToken`).
  - Nếu user F5 reload trang, Keycloak sẽ tự mò lại token trong local và force verify (updateToken) nếu luồng check-sso iframe bị lỗi trên một số domain, tránh việc bắt user đăng nhập lại.
- **Tính năng Realtime:** Các đoạn code subscribe Supabase Channel Realtime trong `ProviderKeyList.tsx` đã bị vô hiệu hoá. Do Request đẩy lên từ Client dùng Token IDSafe chưa map được policy của DB. 

---

## 3. Cấu hình Môi Trường (Environment Variables)

### 3.1. Frontend `.env`
Bổ sung các thiết lập kết nối đến Server IDSafe:
```bash
VITE_IDSAFE_URL=https://idsafe.vnpay.dev
VITE_IDSAFE_REALM=idsafe-uat
VITE_IDSAFE_CLIENT_ID=hyper-ai-gateway
```

### 3.2. Backend `.env`
Bổ sung Issuer URL dùng để verify OIDC token:
```bash
IDSAFE_CLIENT_ID=hyper-ai-gateway-service
# Lưu ý url có chứa path /realms/{realm-name}
IDSAFE_ISSUER_URL=https://idsafe.vnpay.dev/realms/idsafe-uat
```

---

## 4. Hướng dẫn Test Đầu Cuối (E2E)

- **Bước 1**: User mở Gateway, do chưa đăng nhập sẽ thấy Login Button -> Bấm Đăng nhập chuyển hướng sang `idsafe.vnpay.dev`.
- **Bước 2**: Đăng nhập bằng tài khoản nội bộ (có thể bỏ qua OTP nếu đã gắn role bypass trên IDSafe Account).
- **Bước 3**: Nhảy về Dashboard trên cổng Gateway. Token được load ngầm vào `keycloak-js`.
- **Bước 4**: Frontend gọi request GET APIs... chèn vào Header `Authorization: Bearer <keycloak.token>`.
- **Bước 5**: Backend chặn ở middleware, decode Token và kiểm tra Verify JWKS Signature, lấy `sub` làm Context User ID.
- **Bước 6**: Bấm Đăng xuất từ Menu -> Gọi End Session OIDC -> LocalStorage bốc hơi -> Redirect về `window.location.origin` (Trang chủ không Auth).

*(Tài liệu này được tự động generate bởi Antigravity sau quá trình tích hợp)*
