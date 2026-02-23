# AI Model Gateway Multi-Account Migration Note (IDSafe)

Ngày cập nhật: 2026-02-23  
Phạm vi: `hyper-ai-gateway` (client tích hợp ngoài `account-console`)

## 0. Bối cảnh

Trước đây `ai_model_gateway` chỉ chạy theo mô hình single-account:

- Đang login account A muốn sang account B phải logout A trước.
- Frontend giữ token theo 1 bucket global trong browser, không tách theo account/slot.
- Khi dùng luồng slot-aware (`/u/{slot}`), callback và issuer verification chưa đồng bộ hoàn toàn.

Mục tiêu migration:

- Cho phép **Switch Account** để mở chooser (`prompt=select_account`) mà không logout toàn bộ.
- Hỗ trợ chuyển qua lại nhiều account đã nhớ trên IDSafe.
- Bảo toàn compatibility với flow/account-manager đã rollout multi-account trước đó.

## 1. Quyết định kiến trúc và cấu hình chốt

### 1.1 Flow + slot profile

- Browser flow target: `idsafe-login-aal-flow-multi`
- Client bind pilot: `hyper-ai-gateway`
- `slot_count=3`
- `max_saved_users=3`

Lý do: đồng bộ với profile hệ thống hiện tại (3 slot), tránh mismatch giữa runtime extension, route `/u/{slot}` và kỳ vọng QA.

### 1.2 Client attributes

- `multi-account-slot-aware=true` cho `hyper-ai-gateway`
- `multi-account-require-existing-client-session=false` cho `hyper-ai-gateway` (giai đoạn hiện tại)

Ý nghĩa policy `multi-account-require-existing-client-session`:

- `false` (đang dùng): cho phép one-click attach session đã có ở SSO cho client này, UX mượt hơn.
- `true`: chỉ cho switch nếu đã tồn tại authenticated client session cho chính client đó, chặt hơn nhưng dễ tăng friction.

Khuyến nghị hiện tại cho gateway user-facing: giữ `false`, chỉ nâng `true` nếu có yêu cầu compliance cụ thể.

## 2. Kế hoạch triển khai đã thực hiện

### Phase A - Realm rollout bằng script

Script orchestrator:

- `scripts/rollout_multi_account_slots.sh`
- gọi nội bộ `scripts/setup_multi_account_flow.py`
- optional runtime check: `scripts/check_multi_account_slot_runtime.sh`
- optional deep smoke: `scripts/smoke_multi_account_deep.py`

Command profile đã chuẩn hóa:

```bash
export IDSAFE_ADMIN_PASSWORD='<admin_password>'
bash scripts/rollout_multi_account_slots.sh \
  --base-url https://sso.vnpay.dev \
  --realm idsafe-uat \
  --slot-count 3 \
  --max-saved-users 3 \
  --bind-client hyper-ai-gateway \
  --slot-aware-client hyper-ai-gateway \
  --run-remote-check true \
  --run-smoke false
```

### Phase B - Deploy gateway app

Deploy script:

- `ai_model_gateway/ops/deploy_remote_compose.sh`

Mục tiêu:

- Deploy compose stack từ remote server.
- Chờ health endpoint `/api/v1/health`.
- Fail-fast nếu service không healthy trong timeout.

### Phase C - Smoke và UI check

- Chạy deep smoke 3 account, nhiều vòng switch qua lại.
- Chạy UI check Playwright để reproduce và verify hành vi chooser/switch.

Artifacts gần nhất:

- `.artifacts/smoke/multi_account_deep_20260223_015819/report.md`
- `.artifacts/smoke/multi_account_deep_20260223_015819/report.json`
- `.artifacts/smoke/multi_account_deep_20260223_015819/run.log`

Kết quả run gần nhất: `PASS` (3 account, 2 rounds switch, logout/relogin signed-out path).

## 3. Review code chưa commit trong `ai_model_gateway`

Danh sách file thay đổi:

- `IDSAFE_INTEGRATION.md`
- `README.md`
- `README.vi.md`
- `app/core/auth.py`
- `frontend/user-dashboard/src/keycloakClient.ts`
- `frontend/user-dashboard/src/keycloakMultiAccount.ts` (new)
- `frontend/user-dashboard/src/App.tsx`
- `frontend/user-dashboard/public/locales/en/translation.json`
- `frontend/user-dashboard/public/locales/vi/translation.json`

### 3.1 Backend (`app/core/auth.py`)

Đã bổ sung issuer resolution cho token slot-aware:

- Cho phép `iss` đúng tuyệt đối với issuer cấu hình.
- Hoặc `iss` theo dạng `/u/<slot>/realms/<same-realm>`.
- Verify chữ ký/JWKS theo issuer thực tế được chấp nhận.

Tác dụng:

- Tránh reject token hợp lệ chỉ vì khác path slot.
- Giảm lỗi xác thực API khi switch account ở slot khác.

### 3.2 Frontend auth client (`keycloakClient.ts`)

`Keycloak` URL được resolve động theo thứ tự:

1. `iss` trong callback URL.
2. `authuser` query param.
3. `active-authuser` đã lưu local.
4. fallback base URL.

Tác dụng:

- Giữ đúng auth-server context theo slot.
- Giảm drift giữa callback và phiên hiện hành.

### 3.3 Frontend multi-account storage (`keycloakMultiAccount.ts`)

Bổ sung module mới để quản lý session local theo scope:

- Scope: `realm:clientId`
- Partition key tối thiểu: `authuser + sub`
- Lưu/restore/clear session theo từng `authuser`
- Cờ `skip-restore-once` để tránh restore vòng lặp sau logout
- Patch callback redirect URI của PKCE state (`kc-callback-*`) theo slot hiện tại

### 3.4 Frontend app logic (`App.tsx`)

Thay đổi chính:

- Thêm nút `Switch Account` trong user actions.
- Login/switch dùng `createLoginUrl` + `prompt=select_account` + `response_mode=query`.
- Redirect URI được build theo `authuser` hiện tại.
- Save/restore token chuyển sang session partitioned thay vì global `kc_*`.
- Khi logout: clear session theo authuser hiện tại + mark skip restore + logout về redirect đúng slot.

### 3.5 i18n + docs

- Thêm key i18n cho `switchAccount` (EN/VI).
- README/README.vi bổ sung mô tả feature switch-account.
- `IDSAFE_INTEGRATION.md` bổ sung phần rollout multi-account.

## 4. Sự cố chính đã gặp và hướng xử lý

### 4.1 Triệu chứng

Case reproduce:

1. Login đủ 3 account A/B/C.
2. Switch A<->B bình thường.
3. Khi đang ở C mở chooser, chỉ còn thấy A/B.
4. Chọn "Đăng nhập bằng tài khoản khác" thì hiện form login của C dù chưa logout.

### 4.2 Phân tích

Các điểm gây lệch state:

- Session local phía gateway trước đây không partition theo account/slot.
- Callback/redirect PKCE và auth-server URL chưa bám chặt theo `authuser`.
- Backend issuer verify ban đầu chỉ theo issuer base, chưa bao quát dạng slot-aware.

### 4.3 Cách sửa

- Partition local session theo `authuser + sub`.
- Đồng bộ redirect URI + callback patch theo slot.
- Resolve keycloak authServerUrl theo `iss/authuser/active-authuser`.
- Backend chấp nhận issuer slot-aware cùng realm/host.

Kết quả: scenario 3 account switch qua lại đã pass trong deep smoke mới nhất.

## 5. Rollback plan

Nếu cần rollback nhanh:

1. Rebind `hyper-ai-gateway` về browser flow cũ (`idsafe-login-aal-flow`).
2. Giữ nguyên server cookies (không bắt buộc purge ngay).
3. Revert frontend multi-account branch nếu cần quay lại single-account UX.

## 6. Checklist phát hành production

- [ ] Runtime `IDSAFE_MULTI_ACCOUNT_SLOT_COUNT=3`
- [ ] Runtime `IDSAFE_MULTI_ACCOUNT_MAX_SAVED_USERS=3`
- [ ] Nginx/gateway route đầy đủ `/u/1`, `/u/2`
- [ ] Client `hyper-ai-gateway` bind đúng flow multi-account
- [ ] Client attr `multi-account-slot-aware=true`
- [ ] Chính sách `multi-account-require-existing-client-session` được xác nhận theo risk profile
- [ ] Deploy app bằng `ai_model_gateway/ops/deploy_remote_compose.sh`
- [ ] Chạy deep smoke 3 account sau deploy
- [ ] Lưu artifacts smoke + release note cho thay đổi auth behavior

## 7. Gaps còn lại

- Chưa có e2e CI tự động bắt buộc cho scenario 3 account mỗi lần release.
- Hiện đang tối ưu UX (policy `require-existing-client-session=false`); nếu yêu cầu bảo mật tăng, cần đánh giá chuyển `true` kèm impact UX.
