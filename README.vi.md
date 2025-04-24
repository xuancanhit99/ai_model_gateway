# 🌐 AI Model Gateway

Cổng API thống nhất để truy cập nhiều mô hình AI khác nhau bao gồm Gemini, Grok, GigaChat, và Perplexity Sonar.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.12-009688.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717.svg)](https://github.com/xuancanhit99/ai_model_gateway)

## 📋 Tổng quan

AI Model Gateway là một dịch vụ cung cấp giao diện API thống nhất để tương tác với các mô hình AI khác nhau thông qua một REST API tiêu chuẩn. Dịch vụ hiện hỗ trợ:

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

## 🔒 Bảo mật

Xác thực API sử dụng token Bearer với định dạng `Bearer sk-...`.

## 📄 Giấy phép

[Giấy phép MIT](LICENSE)

## 👥 Đóng góp

Chúng tôi hoan nghênh mọi đóng góp! Vui lòng gửi pull request.

## 🆘 Hỗ trợ

Đối với vấn đề và yêu cầu tính năng, vui lòng mở issue trong repository.