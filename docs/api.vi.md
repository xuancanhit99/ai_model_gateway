# 📘 Tài liệu API

Tài liệu này cung cấp thông tin chi tiết về các endpoint API của AI Model Gateway.

## 📑 Mục lục

- [Xác thực](#xác-thực)
- [Kiểm tra trạng thái](#kiểm-tra-trạng-thái)
- [Tạo văn bản](#tạo-văn-bản)
- [Vision (Trích xuất văn bản)](#vision-trích-xuất-văn-bản)
- [Quản lý Khóa Nhà cung cấp](#quản-lý-khóa-nhà-cung-cấp)
- [Các Endpoint tương thích OpenAI](#các-endpoint-tương-thích-openai)
  - [Chat Completions](#chat-completions)
  - [Danh sách mô hình](#danh-sách-mô-hình)
- [Nhật ký Hoạt động](#nhật-ký-hoạt-động)

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
X-Perplexity-API-Key: YOUR_PERPLEXITY_API_KEY
```

Nếu không được cung cấp, dịch vụ sẽ cố gắng sử dụng khóa đã chọn của người dùng cho nhà cung cấp đó (quản lý qua giao diện người dùng) hoặc sử dụng các API key được chỉ định trong file `.env`.

**Lưu ý về Failover**: Đối với các endpoint tương tác với mô hình AI (Tạo văn bản, Vision, Chat Completions), gateway triển khai cơ chế tự động chuyển đổi dự phòng (failover) khóa API. Nếu khóa được chọn ban đầu thất bại với các lỗi cụ thể (ví dụ: 401, 429), hệ thống sẽ tự động thử khóa khả dụng tiếp theo cho nhà cung cấp đó được liên kết với tài khoản của bạn. Xem tệp README chính để biết thêm chi tiết về logic failover.

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
- `X-Perplexity-API-Key: YOUR_KEY` (tùy chọn)

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
- `model` (chuỗi, tùy chọn): Mô hình cụ thể để sử dụng (ví dụ: "gemini-2.5-pro-exp-03-25", "grok-2-1212", "GigaChat-Pro", "sonar", "sonar-pro")

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

## 🔑 Quản lý Khóa Nhà cung cấp

Quản lý các khóa API cho các nhà cung cấp AI khác nhau (Google, xAI, GigaChat, Perplexity) được liên kết với tài khoản người dùng của bạn. Các khóa này được lưu trữ an toàn (mã hóa) và có thể được gateway sử dụng khi thực hiện yêu cầu đến các nhà cung cấp tương ứng nếu khóa cụ thể không được cung cấp trong header yêu cầu hoặc được cấu hình chung trong tệp `.env`. Gateway ưu tiên các khóa theo thứ tự sau: Header > Khóa Nhà cung cấp được chọn > Khóa trong `.env`.

**Endpoint Cơ sở**: `/api/v1/provider-keys`

**Xác thực**: Yêu cầu (`Authorization: Bearer sk-...`) cho tất cả các endpoint trong phần này.

---

### Tạo Khóa Nhà cung cấp

Thêm một khóa API mới cho một nhà cung cấp cụ thể.

**Endpoint**: `POST /`

**Body của Request**:
```json
{
  "provider_name": "google",
  "api_key": "YOUR_PROVIDER_API_KEY",
  "name": "Khóa Google cá nhân của tôi"
}
```

**Các tham số**:
- `provider_name` (chuỗi, bắt buộc): Tên của nhà cung cấp (ví dụ: "google", "xai", "gigachat", "perplexity").
- `api_key` (chuỗi, bắt buộc): Khóa API thực tế từ nhà cung cấp. Khóa này sẽ được mã hóa trước khi lưu trữ.
- `name` (chuỗi, tùy chọn): Tên mô tả cho khóa (ví dụ: "Khóa Công việc", "Khóa Thử nghiệm").

**Ví dụ phản hồi (201 Created)**:
```json
{
  "id": "pk_abc123xyz789",
  "provider_name": "google",
  "name": "Khóa Google cá nhân của tôi",
  "is_selected": false,
  "created_at": "2025-04-29T19:55:00.123Z"
}
```

---

### Liệt kê Khóa Nhà cung cấp

Truy xuất tất cả các khóa nhà cung cấp được liên kết với tài khoản của bạn, có thể lọc theo nhà cung cấp.

**Endpoint**: `GET /`

**Tham số Query**:
- `provider` (chuỗi, tùy chọn): Lọc khóa theo tên nhà cung cấp (ví dụ: `?provider=google`).

**Ví dụ phản hồi**:
```json
[
  {
    "id": "pk_abc123xyz789",
    "provider_name": "google",
    "name": "Khóa Google cá nhân của tôi",
    "is_selected": false,
    "created_at": "2025-04-29T19:55:00.123Z"
  },
  {
    "id": "pk_def456uvw456",
    "provider_name": "xai",
    "name": "Khóa Grok Dev",
    "is_selected": true,
    "created_at": "2025-04-28T10:10:10.000Z"
  }
  // ... các khóa khác
]
```

---

### Lấy Khóa Nhà cung cấp Cụ thể

Truy xuất chi tiết cho một khóa nhà cung cấp duy nhất bằng ID của nó.

**Endpoint**: `GET /{key_id}`

**Tham số Path**:
- `key_id` (chuỗi, bắt buộc): ID duy nhất của khóa nhà cung cấp.

**Ví dụ phản hồi**:
```json
{
  "id": "pk_abc123xyz789",
  "provider_name": "google",
  "name": "Khóa Google cá nhân của tôi",
  "is_selected": false,
  "created_at": "2025-04-29T19:55:00.123Z"
}
```

---

### Cập nhật Khóa Nhà cung cấp

Cập nhật tên hoặc trạng thái lựa chọn của khóa nhà cung cấp. Đặt `is_selected` thành `true` sẽ tự động bỏ chọn bất kỳ khóa nào khác hiện đang được chọn cho cùng một nhà cung cấp.

**Endpoint**: `PATCH /{key_id}`

**Tham số Path**:
- `key_id` (chuỗi, bắt buộc): ID duy nhất của khóa nhà cung cấp cần cập nhật.

**Body của Request**:
```json
{
  "name": "Tên Khóa Google đã cập nhật",
  "is_selected": true
}
```

**Các tham số**:
- `name` (chuỗi, tùy chọn): Tên mô tả mới cho khóa.
- `is_selected` (boolean, tùy chọn): Đặt thành `true` để đặt khóa này làm mặc định cho nhà cung cấp, ngược lại là `false`.

**Ví dụ phản hồi**:
```json
{
  "id": "pk_abc123xyz789",
  "provider_name": "google",
  "name": "Tên Khóa Google đã cập nhật",
  "is_selected": true,
  "created_at": "2025-04-29T19:55:00.123Z"
}
```

---

### Xóa Khóa Nhà cung cấp

Xóa một khóa nhà cung cấp cụ thể.

**Endpoint**: `DELETE /{key_id}`

**Tham số Path**:
- `key_id` (chuỗi, bắt buộc): ID duy nhất của khóa nhà cung cấp cần xóa.

**Phản hồi**: `204 No Content` khi thành công.

---

### Xóa Tất cả Khóa cho một Nhà cung cấp

Xóa tất cả các khóa được liên kết với một nhà cung cấp cụ thể cho tài khoản của bạn.

**Endpoint**: `DELETE /`

**Tham số Query**:
- `provider_name` (chuỗi, bắt buộc): Tên của nhà cung cấp có khóa cần xóa (ví dụ: `?provider_name=google`).

**Phản hồi**: `204 No Content` khi thành công.

---

## 📜 Nhật ký Hoạt động

Truy xuất các bản ghi nhật ký hoạt động gần đây liên quan đến quản lý khóa nhà cung cấp cho người dùng đã xác thực. Điều này bao gồm các hành động thủ công (thêm, xóa, chọn, nhập) và các sự kiện hệ thống tự động (hành động failover).

**Endpoint**: `GET /api/v1/activity-logs`

**Xác thực**: Yêu cầu (`Authorization: Bearer sk-...`)

**Tham số Query**:
- `limit` (số nguyên, tùy chọn, mặc định: 50): Số lượng bản ghi nhật ký tối đa cần trả về.

**Ví dụ phản hồi**:
```json
[
  {
    "id": "log_uuid_1",
    "user_id": "user_uuid",
    "action": "SELECT",
    "provider_name": "google",
    "key_id": "pk_abc123xyz789",
    "description": "Đã chọn khóa \"Khóa Google cá nhân của tôi\" bằng failover tự động từ khóa \"Khóa Google cũ\"",
    "created_at": "2025-04-29T20:15:30.123Z"
  },
  {
    "id": "log_uuid_2",
    "user_id": "user_uuid",
    "action": "UNSELECT",
    "provider_name": "google",
    "key_id": "pk_oldkey456",
    "description": "Khóa 'Khóa Google cũ' bị bỏ chọn do lỗi 429: Vượt quá giới hạn tần suất",
    "created_at": "2025-04-29T20:15:29.987Z"
  },
  {
    "id": "log_uuid_3",
    "user_id": "user_uuid",
    "action": "ADD",
    "provider_name": "xai",
    "key_id": "pk_def456uvw456",
    "description": "Đã thêm khóa \"Khóa Grok Dev\" cho X.AI (Grok)",
    "created_at": "2025-04-29T18:05:00.000Z"
  }
  // ... các bản ghi khác cho đến giới hạn
]
```

---
##  Các Endpoint tương thích OpenAI

### 🤖 Chat Completions

Tạo chat completions theo định dạng tương thích với API của OpenAI.

**Endpoint**: `POST /v1/chat/completions`

**Xác thực**: Yêu cầu

**Headers**:
- `Authorization: Bearer sk-...` (bắt buộc)
- `X-Google-API-Key: YOUR_KEY` (tùy chọn)
- `X-xAI-API-Key: YOUR_KEY` (tùy chọn)
- `X-GigaChat-API-Key: YOUR_KEY` (tùy chọn)
- `X-Perplexity-API-Key: YOUR_KEY` (tùy chọn)

**Ví dụ Body Request**:

Sử dụng mô hình Google Gemini:
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

Sử dụng mô hình Perplexity Sonar:
```json
{
  "model": "perplexity/sonar-pro",
  "messages": [
    {"role": "system", "content": "Bạn là một trợ lý hữu ích, chính xác và tập trung vào nghiên cứu."},
    {"role": "user", "content": "Tóm tắt các nghiên cứu mới nhất về mô hình ngôn ngữ lớn."}
  ],
  "temperature": 0.2,
  "max_tokens": 2000,
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
    {
      "id": "perplexity/sonar",
      "object": "model",
      "created": 1717000000,
      "owned_by": "perplexity"
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