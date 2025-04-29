# 📘 API Documentation

This document provides detailed information about the Hyper AI Gateway API endpoints.

## 📑 Table of Contents

- [Authentication](#authentication)
- [Health Check](#health-check)
- [Text Generation](#text-generation)
- [Vision (Text Extraction)](#vision-text-extraction)
- [Provider Key Management](#provider-key-management)
- [OpenAI-Compatible Endpoints](#openai-compatible-endpoints)
  - [Chat Completions](#chat-completions)
  - [Models List](#models-list)
- [Activity Log](#activity-log)

## 🔐 Authentication

Most endpoints require authentication using a Bearer token.

**Headers**:
```
Authorization: Bearer sk-openhyper123456789abcdef
```

For model-specific API keys, you can provide them via headers:
```
X-Google-API-Key: YOUR_GOOGLE_API_KEY
X-xAI-API-Key: YOUR_XAI_API_KEY
X-GigaChat-API-Key: YOUR_GIGACHAT_API_KEY
X-Perplexity-API-Key: YOUR_PERPLEXITY_API_KEY
```

If not provided, the service will attempt to use the user's selected key for the provider (managed via the UI) or fall back to the API keys specified in the `.env` file.

**Note on Failover**: For endpoints that interact with AI models (Text Generation, Vision, Chat Completions), the gateway implements an automatic API key failover mechanism. If the initially chosen key fails with specific errors (e.g., 401, 429), the system will automatically try the next available key for that provider associated with your account. See the main README for more details on the failover logic.

## ❤️‍🩹 Health Check

Check the health status of the service and get system information.

**Endpoint**: `GET /api/v1/health`

**Authentication**: Not required

**Response Example**:
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

## 💬 Text Generation

Generate text responses using the selected AI model.

**Endpoint**: `POST /api/v1/chat/generate-text`

**Authentication**: Required

**Headers**:
- `Authorization: Bearer sk-...` (required)
- `X-Google-API-Key: YOUR_KEY` (optional)
- `X-xAI-API-Key: YOUR_KEY` (optional)
- `X-GigaChat-API-Key: YOUR_KEY` (optional)
- `X-Perplexity-API-Key: YOUR_KEY` (optional)

**Request Body**:
```json
{
  "message": "What are the benefits of AI in healthcare?",
  "history": [
    {
      "role": "user",
      "content": "Tell me about artificial intelligence."
    },
    {
      "role": "assistant",
      "content": "Artificial Intelligence (AI) refers to systems designed to perform tasks that typically require human intelligence..."
    }
  ],
  "model": "gemini-2.5-pro-exp-03-25"
}
```

**Parameters**:
- `message` (string, required): The user message to generate a response for
- `history` (array, optional): Previous message history for context
- `model` (string, optional): Specific model to use (e.g., "gemini-2.5-pro-exp-03-25", "grok-2-1212", "GigaChat-Pro", "sonar", "sonar-pro")

**Response Example**:
```json
{
  "response_text": "AI offers numerous benefits in healthcare, including improved diagnosis accuracy through medical image analysis, personalized treatment recommendations based on patient data, streamlined administrative processes, predictive analytics for disease outbreaks, and remote patient monitoring capabilities...",
  "model_used": "gemini-2.5-pro-exp-03-25"
}
```

## 👁️ Vision (Text Extraction)

Extract text from images using vision models.

**Endpoint**: `POST /api/v1/vision/extract-text`

**Authentication**: Required

**Headers**:
- `Authorization: Bearer sk-...` (required)
- `X-Google-API-Key: YOUR_KEY` (optional)
- `X-xAI-API-Key: YOUR_KEY` (optional)

**Request Form Data**:
- `file` (file, required): The image file to extract text from
- `prompt` (string, optional): Custom extraction prompt
- `model` (string, optional): Vision model to use (default is "gemini-2.0-flash")

**Response Example**:
```json
{
  "filename": "document.jpg",
  "content_type": "image/jpeg",
  "extracted_text": "Meeting Agenda\n1. Project Updates\n2. Budget Review\n3. Timeline Discussion\n4. New Initiatives\n5. Q&A",
  "model_used": "gemini-2.0-flash"
}
```

## 🔑 Provider Key Management

Manage API keys for different AI providers (Google, xAI, GigaChat, Perplexity) associated with your user account. These keys are securely stored (encrypted) and can be used by the gateway when making requests to the respective providers if specific keys are not provided in request headers or configured globally in `.env`. The gateway prioritizes keys in the following order: Header > Selected Provider Key > `.env` Key.

**Base Endpoint**: `/api/v1/provider-keys`

**Authentication**: Required (`Authorization: Bearer sk-...`) for all endpoints in this section.

---

### Create Provider Key

Add a new API key for a specific provider.

**Endpoint**: `POST /`

**Request Body**:
```json
{
  "provider_name": "google",
  "api_key": "YOUR_PROVIDER_API_KEY",
  "name": "My Personal Google Key"
}
```

**Parameters**:
- `provider_name` (string, required): Name of the provider (e.g., "google", "xai", "gigachat", "perplexity").
- `api_key` (string, required): The actual API key from the provider. This will be encrypted before storage.
- `name` (string, optional): A descriptive name for the key (e.g., "Work Key", "Test Key").

**Response Example (201 Created)**:
```json
{
  "id": "pk_abc123xyz789",
  "provider_name": "google",
  "name": "My Personal Google Key",
  "is_selected": false,
  "created_at": "2025-04-29T19:55:00.123Z"
}
```

---

### List Provider Keys

Retrieve all provider keys associated with your account, optionally filtering by provider.

**Endpoint**: `GET /`

**Query Parameters**:
- `provider` (string, optional): Filter keys by provider name (e.g., `?provider=google`).

**Response Example**:
```json
[
  {
    "id": "pk_abc123xyz789",
    "provider_name": "google",
    "name": "My Personal Google Key",
    "is_selected": false,
    "created_at": "2025-04-29T19:55:00.123Z"
  },
  {
    "id": "pk_def456uvw456",
    "provider_name": "xai",
    "name": "Grok Dev Key",
    "is_selected": true,
    "created_at": "2025-04-28T10:10:10.000Z"
  }
  // ... more keys
]
```

---

### Get Specific Provider Key

Retrieve details for a single provider key by its ID.

**Endpoint**: `GET /{key_id}`

**Path Parameters**:
- `key_id` (string, required): The unique ID of the provider key.

**Response Example**:
```json
{
  "id": "pk_abc123xyz789",
  "provider_name": "google",
  "name": "My Personal Google Key",
  "is_selected": false,
  "created_at": "2025-04-29T19:55:00.123Z"
}
```

---

### Update Provider Key

Update the name or selection status of a provider key. Setting `is_selected` to `true` will automatically deselect any other key currently selected for the same provider.

**Endpoint**: `PATCH /{key_id}`

**Path Parameters**:
- `key_id` (string, required): The unique ID of the provider key to update.

**Request Body**:
```json
{
  "name": "Updated Google Key Name",
  "is_selected": true
}
```

**Parameters**:
- `name` (string, optional): New descriptive name for the key.
- `is_selected` (boolean, optional): Set to `true` to make this the default key for the provider, `false` otherwise.

**Response Example**:
```json
{
  "id": "pk_abc123xyz789",
  "provider_name": "google",
  "name": "Updated Google Key Name",
  "is_selected": true,
  "created_at": "2025-04-29T19:55:00.123Z"
}
```

---

### Delete Provider Key

Remove a specific provider key.

**Endpoint**: `DELETE /{key_id}`

**Path Parameters**:
- `key_id` (string, required): The unique ID of the provider key to delete.

**Response**: `204 No Content` on success.

---

### Delete All Keys for a Provider

Remove all keys associated with a specific provider for your account.

**Endpoint**: `DELETE /`

**Query Parameters**:
- `provider_name` (string, required): The name of the provider whose keys should be deleted (e.g., `?provider_name=google`).

**Response**: `204 No Content` on success.

---

## 📜 Activity Log

Retrieve recent activity logs related to provider key management for the authenticated user. This includes manual actions (add, delete, select, import) and automatic system events (failover actions).

**Endpoint**: `GET /api/v1/activity-logs`

**Authentication**: Required (`Authorization: Bearer sk-...`)

**Query Parameters**:
- `limit` (integer, optional, default: 50): Maximum number of log entries to return.
- `provider` (string, optional): Filter logs by provider name (e.g., `?provider=google`).
- `action` (string, optional): Filter logs by action type (e.g., `?action=SELECT`).
- `from_date` (string, optional): Filter logs created on or after this date (ISO format, e.g., `?from_date=2025-04-01T00:00:00Z`).
- `to_date` (string, optional): Filter logs created on or before this date (ISO format, e.g., `?to_date=2025-04-30T23:59:59Z`).

**Response Example**:
```json
[
  {
    "id": "log_uuid_1",
    "user_id": "user_uuid",
    "action": "SELECT",
    "provider_name": "google",
    "key_id": "pk_abc123xyz789",
    "description": "Selected key \"My Personal Google Key\" by automatic failover from key \"Old Google Key\"",
    "created_at": "2025-04-29T20:15:30.123Z"
  },
  {
    "id": "log_uuid_2",
    "user_id": "user_uuid",
    "action": "UNSELECT",
    "provider_name": "google",
    "key_id": "pk_oldkey456",
    "description": "Key 'Old Google Key' unselected due to error 429: Rate limit exceeded",
    "created_at": "2025-04-29T20:15:29.987Z"
  },
  {
    "id": "log_uuid_3",
    "user_id": "user_uuid",
    "action": "ADD",
    "provider_name": "xai",
    "key_id": "pk_def456uvw456",
    "description": "Added key \"Grok Dev Key\" for X.AI (Grok)",
    "created_at": "2025-04-29T18:05:00.000Z"
  }
  // ... more logs up to the limit
]
```

### Log Action Types

The activity log system tracks the following action types:

- `ADD`: When a new provider key is created
- `DELETE`: When a provider key is deleted
- `SELECT`: When a key is selected as the default for a provider (manually via UI or automatically via failover)
- `UNSELECT`: When a key is unselected (manually or due to errors during API calls)
- `IMPORT`: When keys are batch imported via the UI

### Filtering Examples

**Filter by provider and action**:
```
GET /api/v1/activity-logs?provider=google&action=SELECT
```

**Filter by date range**:
```
GET /api/v1/activity-logs?from_date=2025-04-01T00:00:00Z&to_date=2025-04-30T23:59:59Z
```

**Combined filters**:
```
GET /api/v1/activity-logs?provider=xai&action=ADD&limit=10
```

---

##  OpenAI-Compatible Endpoints

### 🤖 Chat Completions

Generate chat completions in a format compatible with OpenAI's API.

**Endpoint**: `POST /v1/chat/completions`

**Authentication**: Required

**Headers**:
- `Authorization: Bearer sk-...` (required)
- `X-Google-API-Key: YOUR_KEY` (optional)
- `X-xAI-API-Key: YOUR_KEY` (optional)
- `X-GigaChat-API-Key: YOUR_KEY` (optional)
- `X-Perplexity-API-Key: YOUR_KEY` (optional)

**Request Body**:
```json
{
  "model": "google/gemini-2.5-pro-exp-03-25",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is quantum computing?"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

**Parameters**:
- `model` (string, required): Model ID with optional provider prefix
- `messages` (array, required): Array of message objects with role and content
- `temperature` (number, optional): Controls randomness (0-1)
- `max_tokens` (integer, optional): Maximum tokens in response
- `stream` (boolean, optional): Stream response tokens if true

**Request Body Examples**:

Using Google Gemini model:
```json
{
  "model": "google/gemini-2.5-pro-exp-03-25",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is quantum computing?"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

Using Perplexity Sonar model:
```json
{
  "model": "perplexity/sonar-pro",
  "messages": [
    {"role": "system", "content": "You are a helpful, precise, and research-focused assistant."},
    {"role": "user", "content": "Summarize the latest research on large language models."}
  ],
  "temperature": 0.2,
  "max_tokens": 2000,
  "stream": false
}
```

**Response Example (non-streaming)**:
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
        "content": "Quantum computing is a type of computing that uses quantum-mechanical phenomena, such as superposition and entanglement, to perform operations on data..."
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

**Streaming Response Format**:
When `stream: true`, the API returns a stream of Server-Sent Events (SSE), each containing a chunk of the response:

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1715123456,"model":"google/gemini-2.5-pro-exp-03-25","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1715123456,"model":"google/gemini-2.5-pro-exp-03-25","choices":[{"index":0,"delta":{"content":"Quantum"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1715123456,"model":"google/gemini-2.5-pro-exp-03-25","choices":[{"index":0,"delta":{"content":" computing"},"finish_reason":null}]}

... more chunks ...

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1715123456,"model":"google/gemini-2.5-pro-exp-03-25","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 📋 Models List

Get a list of available models.

**Endpoint**: `GET /v1/models`

**Authentication**: Required

**Headers**:
- `Authorization: Bearer sk-...` (required)

**Response Example**:
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
    ... more models ...
  ]
}
```

## ⚠️ Error Responses

All endpoints return standard HTTP status codes and consistent error responses.

**Error Response Example**:
```json
{
  "detail": "Invalid API key provided"
}
```

Common error codes:
- `400 Bad Request`: Invalid parameters
- `401 Unauthorized`: Authentication failure
- `404 Not Found`: Resource not found
- `415 Unsupported Media Type`: Unsupported file format
- `429 Too Many Requests`: Rate limited
- `500 Internal Server Error`: Server error
- `502 Bad Gateway`: Provider API failure
- `503 Service Unavailable`: Service temporarily unavailable
- `504 Gateway Timeout`: Provider API timeout