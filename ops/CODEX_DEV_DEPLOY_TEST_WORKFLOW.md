# Codex Dev -> Deploy -> Test Workflow

Muc tieu: sau moi lan Codex fix/dev, co the deploy nhanh len server Ubuntu va test lai ngay.

## 1) Nen dung gi?

Dung ket hop 3 lop:

1. `scripts` (`ops/*.sh`): chay lenh that, on dinh, co the goi lai.
2. `workflow` (file nay): quy trinh chuan de team va Codex bam theo.
3. `skill` (`.agent/skills/deploy-compose-playwright`): de Codex tu nhan dien dung flow khi ban yeu cau.

## 2) One-time setup

1. Dam bao server co `docker`, `docker compose`, `curl`.
2. Dam bao user SSH co quyen chay Docker (thuong la trong group `docker`).
3. Tao file env rieng cho automation:

```bash
cd /Users/canhvx/IdeaProjects/id-safe/ai_model_gateway
cp ops/.env.example ops/.env
```

4. Dien du thong tin nhay cam trong `ops/.env`:
   - `REMOTE_HOST`, `SSH_KEY_PATH`, `REMOTE_USER`, ...
   - `FRONTEND_URL=https://gateway.vnpay.dev`
   - `API_BASE_URL=https://gateway-api.vnpay.dev`
   - `CHECK_DOCS=false` neu domain public khong expose `/docs`
   - User test cho Playwright login:
     - `TEST_USER_EMAIL`
     - `TEST_USER_PASSWORD`
     - `TEST_USER_OTP` (neu can)
5. Khong luu password vao repo. Chi dung SSH private key.
6. Thu muc deploy tren server: `/opt/stacks/ai_model_gateway`.

## 3) Deploy len server

Tu local machine:

```bash
cd /Users/canhvx/IdeaProjects/id-safe/ai_model_gateway
chmod +x ops/deploy_remote_compose.sh ops/smoke_after_deploy.sh

# Script doc host/user/key tu ops/.env
./ops/deploy_remote_compose.sh
```

Tuy chon:

```bash
# Neu server deploy bang git
./ops/deploy_remote_compose.sh --branch main

# Neu muon day code local truc tiep len server (khong qua git pull)
./ops/deploy_remote_compose.sh --deploy-mode rsync
```

Script deploy se:

1. Dong stack: `docker compose down`
2. Build va chay lai: `docker compose up -d --build`
3. Cho health endpoint `GET /api/v1/health` pass

## 4) Smoke check sau deploy

```bash
cd /Users/canhvx/IdeaProjects/id-safe/ai_model_gateway
./ops/smoke_after_deploy.sh
```

Script smoke check:

1. Frontend tra ve HTML
2. Backend health tra ve `status=healthy`
3. `/docs` chi check khi `CHECK_DOCS=true`

## 5) UI test voi MCP Playwright / DevTools

Sau khi deploy + smoke pass, yeu cau Codex:

```text
Dung skill deploy-compose-playwright:
1) deploy len server
2) smoke check
3) mo UI bang Playwright, test login IDSafe
4) test tao 1 gateway api key, deactivate key do
5) bao cao ket qua va loi (neu co) theo tung buoc
```

Goi y test case toi thieu:

1. Login thanh cong tu man hinh dashboard.
2. Danh sach API key load duoc.
3. Tao API key moi thanh cong.
4. Deactivate API key vua tao thanh cong.
5. Logout thanh cong.

Luu y:

1. Neu thieu `TEST_USER_EMAIL` hoac `TEST_USER_PASSWORD`, Codex chi test duoc den buoc redirect sang man hinh dang nhap IDSafe (khong test duoc flow sau login).

## 6) Muc tieu automation tiep theo (khuyen nghi)

1. Them script rollback nhanh (`docker compose logs` + quay ve commit truoc).
2. Them script e2e API co token test account.
3. Dua quy trinh nay vao CI/CD (GitHub Actions + SSH deploy) de giam thao tac tay.

## 7) Cutover Supabase -> PostgreSQL (downtime)

Khi can chuyen du lieu live:

```bash
cd /Users/canhvx/IdeaProjects/id-safe/ai_model_gateway
./ops/migrate_live_supabase_to_postgres.sh
./ops/verify_postgres_cutover.sh
```

Dieu kien:

1. `DATABASE_URL` da tro den PostgreSQL moi trong remote `.env`.
2. `SOURCE_DB_URL` ton tai trong remote `.env`.
3. Da backup truoc khi migrate.

## 8) Checklist van hanh de lan sau muot hon

### 8.1 Env contract (quan trong nhat)

1. Backend chi dung key moi:
   - `IDSAFE_SERVICE_CLIENT_ID`
   - `IDSAFE_SERVICE_CLIENT_SECRET`
   - `APP_ENCRYPTION_KEY`
2. Khong dung lai key cu:
   - `IDSAFE_CLIENT_ID`, `IDSAFE_CLIENT_SECRET`
   - `PROVIDER_KEYS_ENCRYPTION_KEY`
   - toan bo `SUPABASE_*`, `VITE_SUPABASE_*`
3. Frontend chi dung:
   - `VITE_IDSAFE_URL`
   - `VITE_IDSAFE_REALM`
   - `VITE_IDSAFE_CLIENT_ID`
4. Luon giu key-set `.env` va `.env.example` khop nhau (backend va frontend).

### 8.2 Domain va smoke check

1. Tach ro domain:
   - `FRONTEND_URL=https://gateway.vnpay.dev`
   - `API_BASE_URL=https://gateway-api.vnpay.dev`
2. `ops/smoke_after_deploy.sh` khong con `BASE_URL` legacy.
3. `CHECK_DOCS=false` neu public gateway khong expose `/docs`.

### 8.3 Deploy mode

1. Neu ban chua push commit len remote git, dung:
   - `./ops/deploy_remote_compose.sh --deploy-mode rsync`
2. Neu remote stack deploy theo git, dung mode mac dinh:
   - `./ops/deploy_remote_compose.sh --branch main`

### 8.4 Runtime behavior can biet truoc

1. Sau `docker compose up -d --build`, co the gap `curl: (56) Recv failure: Connection reset by peer` trong vai giay dau; script health check da retry, day la hanh vi startup binh thuong.
2. `compose.yaml` hien canh bao `version is obsolete`; khong lam fail deploy, nhung nen remove key `version` khi don file.

### 8.5 Auth/Register flow note

1. Register flow:
   - Neu co `vnpayId` ma chua co `sub` -> tao `gateway_users` provisional.
   - Chi fail-fast khi thieu ca `sub` va `vnpayId`.
2. Login JWT lan dau voi `sub` se attach vao row provisional theo `vnpay_id`.
3. JWT verify:
   - Dang enforce `signature + iss + exp + azp`.
   - `aud` hien de `IDSAFE_VERIFY_AUD=false`; neu bat `true` thi phai dat `IDSAFE_EXPECTED_AUDIENCE` dung voi token setup tren Keycloak.

### 8.6 Secret hygiene

1. Khong commit `.env`, `ops/.env`.
2. Neu tao backup env tam, xoa ngay sau khi migrate/deploy.
3. `.gitignore` da co pattern:
   - `.env.backup*`
   - `ops/.env.backup*`
