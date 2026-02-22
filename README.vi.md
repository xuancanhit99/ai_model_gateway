<div align="center">
  <img src="frontend/user-dashboard/src/assets/Hyper.svg" alt="Hyper AI Gateway Logo" width="200" height="200"/>
</div>

# 🌐 Hyper AI Gateway

Cổng API thống nhất để truy cập nhiều mô hình AI khác nhau bao gồm Gemini, Grok, GigaChat, và Perplexity Sonar.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.12-009688.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717.svg)](https://github.com/xuancanhit99/ai_model_gateway)

## 📋 Tổng quan

Hyper AI Gateway là một dịch vụ cung cấp giao diện API thống nhất để tương tác với các mô hình AI khác nhau thông qua một REST API tiêu chuẩn. Dịch vụ hiện hỗ trợ:

- **Các mô hình Gemini AI** (Google)
- **Các mô hình Grok AI** (xAI)
- **Các mô hình GigaChat** (Sber)
- **Các mô hình Sonar** (Perplexity AI)

Tính năng chính:
- Giao diện API tương thích OpenAI
- API tạo văn bản
- Trích xuất văn bản từ hình ảnh
- Phản hồi dạng streaming
- Giám sát trạng thái
- Quản lý Khóa API Nhà cung cấp (Lưu trữ, quản lý và nhập khóa qua giao diện người dùng)
- **Tự động chuyển đổi dự phòng (Failover) Khóa API**: Tự động xoay vòng sang khóa khả dụng tiếp theo khi gặp lỗi API cụ thể (ví dụ: 401, 429).
- **Ghi Nhật ký Hoạt động**: Theo dõi các hành động quản lý khóa (thêm, xóa, chọn, nhập) và các sự kiện failover.

## 🚀 Bắt đầu nhanh

### 🐳 Sử dụng Docker Compose

Cách đơn giản nhất để chạy dịch vụ là thông qua Docker Compose:

```bash
# Sao chép repository
git clone https://github.com/xuancanhit99/ai_model_gateway.git
cd ai_model_gateway

# Tạo và cấu hình file .env (sao chép từ file mẫu)
cp .env.example .env
# Chỉnh sửa file .env để thêm các API key của bạn

# Chạy với Docker Compose
docker-compose up -d
```

### 💻 Cài đặt thủ công

Nếu bạn muốn cài đặt thủ công:

```bash
# Sao chép repository
git clone https://github.com/xuancanhit99/ai_model_gateway.git
cd ai_model_gateway

# Tạo và kích hoạt môi trường ảo
python -m venv .venv
source .venv/bin/activate  # Trên Windows: .venv\Scripts\activate

# Cài đặt các gói phụ thuộc
pip install -r requirements.txt

# Tạo và cấu hình file .env
cp .env.example .env
# Chỉnh sửa file .env để thêm các API key của bạn

# Chạy dịch vụ
uvicorn main:app --host 0.0.0.0 --port 6161
```

## ⚙️ Cấu hình

Cấu hình dịch vụ bằng cách chỉnh sửa file `.env`:

```
# Cài đặt ứng dụng
APP_NAME='AI Model Gateway'
APP_VERSION=1.0.0
APP_DESCRIPTION='Gateway service for multiple AI models'

# Cài đặt API
API_V1_STR=/api/v1

# Cài đặt PostgreSQL
DATABASE_URL=postgresql://ai_gateway:***@postgres:5432/ai_gateway
DB_POOL_MIN_SIZE=1
DB_POOL_MAX_SIZE=10
APP_ENCRYPTION_KEY=<base64-key-32-byte>

# Cài đặt Gemini
GOOGLE_AI_STUDIO_API_KEY=your_google_api_key
GEMINI_VISION_MODEL_NAME=gemini-2.0-flash
GEMINI_CHAT_MODEL_NAME=gemini-2.5-pro-exp-03-25

# Cài đặt Grok
XAI_API_KEY=your_xai_api_key
XAI_API_BASE_URL=https://api.x.ai/v1
GROK_CHAT_MODEL_NAME=grok-2-1212
GROK_VISION_MODEL_NAME=grok-2-vision-1212

# Cài đặt GigaChat
GIGACHAT_AUTH_KEY=your_gigachat_auth_key
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_TOKEN_URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth
GIGACHAT_CHAT_URL=https://gigachat.devices.sberbank.ru/api/v1/chat/completions
GIGACHAT_DEFAULT_MODEL=GigaChat-Pro

# Cài đặt Perplexity
PERPLEXITY_API_KEY=your_perplexity_api_key
PERPLEXITY_API_BASE_URL=https://api.perplexity.ai
SONAR_DEFAULT_MODEL=sonar

# Cài đặt IDSafe
IDSAFE_ISSUER_URL=https://idsafe.vnpay.dev/realms/idsafe-uat
IDSAFE_REGISTER_URL=https://idsafe.vnpay.dev/realms/idsafe-uat/idsafe-api/user/register
IDSAFE_SERVICE_CLIENT_ID=hyper-ai-gateway-service
IDSAFE_SERVICE_CLIENT_SECRET=***
IDSAFE_VERIFY_AUD=false
IDSAFE_EXPECTED_AUDIENCE=hyper-ai-gateway-service
IDSAFE_EXPECTED_AZP=hyper-ai-gateway
```

## 📚 Tài liệu API

Khi dịch vụ đang chạy, bạn có thể khám phá tài liệu API tại:
- OpenAPI UI: `http://localhost:6161/docs`
- ReDoc: `http://localhost:6161/redoc`

Để xem tài liệu API chi tiết, hãy xem [Tài liệu API](./docs/api.vi.md).

## 🔌 Các Endpoint được hỗ trợ

Dịch vụ cung cấp các endpoint chính sau:

- **Kiểm tra trạng thái**: `/api/v1/health`
- **Tạo văn bản**: `/api/v1/chat/generate-text`
- **Trích xuất văn bản từ hình ảnh**: `/api/v1/vision/extract-text`
- **Chat Completions tương thích OpenAI**: `/v1/chat/completions`
- **Danh sách mô hình tương thích OpenAI**: `/v1/models`
- **Quản lý Khóa Nhà cung cấp**: `/api/v1/provider-keys`
- **Nhật ký Hoạt động**: `/api/v1/activity-logs`
- **Proxy đăng ký IDSafe**: `/api/v1/auth/register`

## 🤖 Các mô hình có sẵn

Dịch vụ hỗ trợ nhiều mô hình từ các nhà cung cấp khác nhau:

### 🔷 Mô hình Gemini
- gemini-2.5-pro-exp-03-25
- gemini-2.0-flash
- gemini-1.5-pro
- Và các mô hình khác...

### 🔶 Mô hình Grok
- grok-2-1212
- grok-2-vision-1212
- grok-3-beta
- Và các mô hình khác...

### 🔴 Mô hình GigaChat
- GigaChat-Pro
- GigaChat-2
- GigaChat-2-Pro
- Và các mô hình khác...

### 🔵 Mô hình Perplexity Sonar
- sonar
- sonar-pro
- sonar-reasoning
- sonar-reasoning-pro
- sonar-deep-research
- r1-1776

Để xem danh sách đầy đủ các mô hình được hỗ trợ, sử dụng endpoint `/v1/models`.

## ✨ Cách hoạt động (Failover Khóa)

Khi thực hiện yêu cầu thông qua các endpoint tương thích OpenAI (`/v1/chat/completions`) hoặc các endpoint gateway cụ thể (`/api/v1/chat/generate-text`, `/api/v1/vision/extract-text`):

1.  **Ưu tiên Khóa**: Gateway ưu tiên các khóa API theo thứ tự sau:
    1.  Khóa được cung cấp trong header của yêu cầu (ví dụ: `X-Google-API-Key`).
    2.  Khóa hiện đang được *chọn* của người dùng cho nhà cung cấp đó (quản lý qua giao diện người dùng).
    3.  Khóa dự phòng được định nghĩa trong tệp `.env` (nếu có).
2.  **Phát hiện Lỗi**: Nếu khóa được chọn gây ra lỗi API cho thấy vấn đề về khóa (ví dụ: 401 Unauthorized, 403 Forbidden, 429 Too Many Requests), cơ chế failover sẽ được kích hoạt.
3.  **Tự động Xoay vòng**:
    *   Khóa bị lỗi sẽ được đánh dấu (tạm thời vô hiệu hóa đối với lỗi 429).
    *   Hệ thống cố gắng tìm khóa *khả dụng tiếp theo* (không bị vô hiệu hóa) cho nhà cung cấp đó thuộc về người dùng, xoay vòng dựa trên thứ tự tạo.
    *   Khóa mới tìm thấy sẽ tự động được chọn (`is_selected` = true trong cơ sở dữ liệu).
4.  **Thử lại**: Yêu cầu API ban đầu được thử lại bằng khóa mới được chọn.
5.  **Cạn kiệt**: Nếu tất cả các khóa khả dụng cho một nhà cung cấp đều bị lỗi liên tiếp, lỗi 503 Service Unavailable sẽ được trả về.
6.  **Ghi Log**: Tất cả các sự kiện failover (khóa bị bỏ chọn do lỗi, khóa mới được chọn, cạn kiệt khóa) đều được ghi lại trong Nhật ký Hoạt động.

Điều này đảm bảo tính sẵn sàng và khả năng phục hồi cao hơn bằng cách tự động xử lý các sự cố khóa tạm thời hoặc khóa không hợp lệ.

## 📜 Nhật ký Hoạt động

Gateway ghi lại các sự kiện quan trọng liên quan đến quản lý khóa nhà cung cấp:
- **Hành động thủ công qua UI**: Thêm, Xóa, Chọn/Bỏ chọn, Nhập khóa.
- **Hành động hệ thống**: Tự động chọn/bỏ chọn khóa trong quá trình failover, sự kiện cạn kiệt khóa.
- **Ghi log chi tiết**: Mỗi bản ghi nhật ký bao gồm thời gian, loại hành động, tên nhà cung cấp, định danh khóa và mô tả.

Nhật ký có thể được xem trong phần "Nhật ký Hoạt động" của bảng điều khiển người dùng hoặc truy xuất theo chương trình thông qua endpoint `/api/v1/activity-logs`.

Các hành động log có sẵn bao gồm:
- `ADD`: Khi một khóa nhà cung cấp mới được thêm
- `DELETE`: Khi một khóa nhà cung cấp bị xóa
- `SELECT`: Khi một khóa được chọn (thủ công hoặc tự động thông qua failover)
- `UNSELECT`: Khi một khóa bị bỏ chọn (thủ công hoặc do lỗi)
- `IMPORT`: Khi các khóa được nhập hàng loạt

Hệ thống ghi log toàn diện này cho phép quản trị viên theo dõi mẫu sử dụng khóa, khắc phục sự cố xác thực và giám sát hiệu quả của hệ thống failover tự động.

## 🏗️ Cấu trúc Dự án

```
.
├── app/                  # Ứng dụng backend FastAPI
│   ├── api/              # Các endpoint API (routes)
│   ├── core/             # Các thành phần cốt lõi (auth, config, db client, utils)
│   ├── models/           # Các model Pydantic (schemas)
│   └── services/         # Logic nghiệp vụ, tương tác dịch vụ bên ngoài (mô hình AI)
├── docs/                 # Các tệp tài liệu API (Markdown)
├── frontend/             # Ứng dụng frontend React (Bảng điều khiển người dùng)
│   └── user-dashboard/
│       ├── public/       # Tài sản tĩnh, bản địa hóa
│       └── src/          # Mã nguồn React
│           ├── assets/
│           ├── components/ # Các component UI tái sử dụng
│           ├── services/   # Logic tương tác API frontend (nếu có)
│           ├── styles/     # CSS, styling
│           └── ...         # App chính, routing, quản lý state
├── .env.example          # Biến môi trường mẫu
├── compose.yaml          # Cấu hình Docker Compose
├── Dockerfile            # Dockerfile backend chính
├── main.py               # Điểm vào ứng dụng FastAPI
├── requirements.txt      # Các gói phụ thuộc Python backend
├── README.md             # README tiếng Anh
└── README.vi.md          # README tiếng Việt (tệp này)
```

## 🔒 Bảo mật

Xác thực API sử dụng token Bearer với định dạng `Bearer sk-...`.

## 📄 Giấy phép

[Giấy phép MIT](LICENSE)

## 👥 Đóng góp

Chúng tôi hoan nghênh mọi đóng góp! Vui lòng gửi pull request.

## 🆘 Hỗ trợ

Đối với vấn đề và yêu cầu tính năng, vui lòng mở issue trong repository.
