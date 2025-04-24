# 📘 Tài liệu API

Tài liệu này cung cấp thông tin chi tiết về các endpoint API của AI Model Gateway.

## 📑 Mục lục

- [Xác thực](#xác-thực)
- [Kiểm tra trạng thái](#kiểm-tra-trạng-thái)
- [Tạo văn bản](#tạo-văn-bản)
- [Vision (Trích xuất văn bản)](#vision-trích-xuất-văn-bản)
- [Các Endpoint tương thích OpenAI](#các-endpoint-tương-thích-openai)
  - [Chat Completions](#chat-completions)
  - [Danh sách mô hình](#danh-sách-mô-hình)

## 🔐 Xác thực

Hầu hết các endpoint đều yêu cầu xác thực sử dụng token Bearer.

**Headers**:
```
Authorization: Bearer sk-openhyper123456789abcdef
```

Đối với API key của từng mô hình cụ thể, bạn có thể cung cấp chúng qua headers:
```
X-Google-API-Key: YOUR_GOOGLE_API_KEY
X-xAI-API-Key: YOUR_XAI_API_KEY
X-GigaChat-API-Key: YOUR_GIGACHAT_API_KEY
```

Nếu không được cung cấp, dịch vụ sẽ sử dụng các API key được chỉ định trong file `.env`.

## ❤️‍🩹 Kiểm tra trạng thái

Kiểm tra trạng thái của dịch vụ và lấy thông tin hệ thống.

**Endpoint**: `GET /api/v1/health`

**Xác thực**: Không yêu cầu

**Ví dụ phản hồi**:
```json
{
  "status": "healthy",
  "uptime": "01:23:45",
  "gemini_api": true,
  "system_stats": {
    "cpu_percent": 12.5,
    "memory_percent": 45.2,
    "disk_usage": 68.7
  }
}
```

## 💬 Tạo văn bản

Tạo phản hồi văn bản sử dụng mô hình AI đã chọn.

**Endpoint**: `POST /api/v1/chat/generate-text`

**Xác thực**: Yêu cầu

**Headers**:
- `Authorization: Bearer sk-...` (bắt buộc)
- `X-Google-API-Key: YOUR_KEY` (tùy chọn)
- `X-xAI-API-Key: YOUR_KEY` (tùy chọn)
- `X-GigaChat-API-Key: YOUR_KEY` (tùy chọn)

**Body của Request**:
```json
{
  "message": "Những lợi ích của AI trong y tế là gì?",
  "history": [
    {
      "role": "user",
      "content": "Hãy cho tôi biết về trí tuệ nhân tạo."
    },
    {
      "role": "assistant",
      "content": "Trí tuệ nhân tạo (AI) là các hệ thống được thiết kế để thực hiện các nhiệm vụ thường đòi hỏi trí thông minh của con người..."
    }
  ],
  "model": "gemini-2.5-pro-exp-03-25"
}
```

**Các tham số**:
- `message` (chuỗi, bắt buộc): Tin nhắn người dùng để tạo phản hồi
- `history` (mảng, tùy chọn): Lịch sử tin nhắn trước đó để cung cấp ngữ cảnh
- `model` (chuỗi, tùy chọn): Mô hình cụ thể để sử dụng (ví dụ: "gemini-2.5-pro-exp-03-25", "grok-2-1212", "GigaChat-Pro")

**Ví dụ phản hồi**:
```json
{
  "response_text": "AI mang đến nhiều lợi ích trong y tế, bao gồm cải thiện độ chính xác trong chẩn đoán thông qua phân tích hình ảnh y tế, đề xuất điều trị cá nhân hóa dựa trên dữ liệu bệnh nhân, hợp lý hóa các quy trình hành chính, phân tích dự đoán về dịch bệnh và khả năng theo dõi bệnh nhân từ xa...",
  "model_used": "gemini-2.5-pro-exp-03-25"
}
```

## 👁️ Vision (Trích xuất văn bản)

Trích xuất văn bản từ hình ảnh sử dụng các mô hình vision.

**Endpoint**: `POST /api/v1/vision/extract-text`

**Xác thực**: Yêu cầu

**Headers**:
- `Authorization: Bearer sk-...` (bắt buộc)
- `X-Google-API-Key: YOUR_KEY` (tùy chọn)
- `X-xAI-API-Key: YOUR_KEY` (tùy chọn)

**Form Data của Request**:
- `file` (file, bắt buộc): File hình ảnh để trích xuất văn bản
- `prompt` (chuỗi, tùy chọn): Prompt trích xuất tùy chỉnh
- `model` (chuỗi, tùy chọn): Mô hình vision để sử dụng (mặc định là "gemini-2.0-flash")

**Ví dụ phản hồi**:
```json
{
  "filename": "document.jpg",
  "content_type": "image/jpeg",
  "extracted_text": "Chương trình cuộc họp\n1. Cập nhật dự án\n2. Xem xét ngân sách\n3. Thảo luận về tiến độ\n4. Sáng kiến mới\n5. Hỏi đáp",
  "model_used": "gemini-2.0-flash"
}
```

## 🔄 Các Endpoint tương thích OpenAI

### 🤖 Chat Completions

Tạo chat completions theo định dạng tương thích với API của OpenAI.

**Endpoint**: `POST /v1/chat/completions`

**Xác thực**: Yêu cầu

**Headers**:
- `Authorization: Bearer sk-...` (bắt buộc)
- `X-Google-API-Key: YOUR_KEY` (tùy chọn)
- `X-xAI-API-Key: YOUR_KEY` (tùy chọn)
- `X-GigaChat-API-Key: YOUR_KEY` (tùy chọn)

**Body của Request**:
```json
{
  "model": "google/gemini-2.5-pro-exp-03-25",
  "messages": [
    {"role": "system", "content": "Bạn là một trợ lý hữu ích."},
    {"role": "user", "content": "Điện toán lượng tử là gì?"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

**Các tham số**:
- `model` (chuỗi, bắt buộc): ID mô hình với tiền tố nhà cung cấp tùy chọn
- `messages` (mảng, bắt buộc): Mảng các đối tượng tin nhắn với vai trò và nội dung
- `temperature` (số, tùy chọn): Kiểm soát độ ngẫu nhiên (0-1)
- `max_tokens` (số nguyên, tùy chọn): Số token tối đa trong phản hồi
- `stream` (boolean, tùy chọn): Trả về phản hồi dạng stream nếu là true

**Ví dụ phản hồi (không stream)**:
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1715123456,
  "model": "google/gemini-2.5-pro-exp-03-25",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Điện toán lượng tử là một loại điện toán sử dụng các hiện tượng cơ học lượng tử, như sự chồng chất và sự vướng víu, để thực hiện các phép tính với dữ liệu..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 24,
    "completion_tokens": 120,
    "total_tokens": 144
  }
}
```

**Định dạng phản hồi streaming**:
Khi `stream: true`, API trả về một luồng các sự kiện Server-Sent Events (SSE), mỗi sự kiện chứa một phần nhỏ của phản hồi:

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1715123456,"model":"google/gemini-2.5-pro-exp-03-25","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1715123456,"model":"google/gemini-2.5-pro-exp-03-25","choices":[{"index":0,"delta":{"content":"Điện"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1715123456,"model":"google/gemini-2.5-pro-exp-03-25","choices":[{"index":0,"delta":{"content":" toán"},"finish_reason":null}]}

... nhiều phần nhỏ khác ...

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1715123456,"model":"google/gemini-2.5-pro-exp-03-25","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 📋 Danh sách mô hình

Lấy danh sách các mô hình có sẵn.

**Endpoint**: `GET /v1/models`

**Xác thực**: Yêu cầu

**Headers**:
- `Authorization: Bearer sk-...` (bắt buộc)

**Ví dụ phản hồi**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "google/gemini-2.5-pro-exp-03-25",
      "object": "model",
      "created": 1711000000,
      "owned_by": "google"
    },
    {
      "id": "x-ai/grok-2-1212",
      "object": "model",
      "created": 1710000000,
      "owned_by": "xai"
    },
    {
      "id": "sber/GigaChat-Pro",
      "object": "model",
      "created": 1700000011,
      "owned_by": "salutedevices"
    },
    ... các mô hình khác ...
  ]
}
```

## ⚠️ Phản hồi lỗi

Tất cả các endpoint đều trả về mã trạng thái HTTP tiêu chuẩn và phản hồi lỗi nhất quán.

**Ví dụ phản hồi lỗi**:
```json
{
  "detail": "API key được cung cấp không hợp lệ"
}
```

Các mã lỗi phổ biến:
- `400 Bad Request`: Tham số không hợp lệ
- `401 Unauthorized`: Lỗi xác thực
- `404 Not Found`: Không tìm thấy tài nguyên
- `415 Unsupported Media Type`: Định dạng file không được hỗ trợ
- `429 Too Many Requests`: Vượt quá giới hạn tần suất
- `500 Internal Server Error`: Lỗi máy chủ
- `502 Bad Gateway`: Lỗi API của nhà cung cấp
- `503 Service Unavailable`: Dịch vụ tạm thời không khả dụng
- `504 Gateway Timeout`: Hết thời gian chờ API của nhà cung cấp