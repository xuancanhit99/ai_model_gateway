# 📘 API Documentation

This document provides detailed information about the AI Model Gateway API endpoints.

## 📑 Table of Contents

- [Authentication](#authentication)
- [Health Check](#health-check)
- [Text Generation](#text-generation)
- [Vision (Text Extraction)](#vision-text-extraction)
- [OpenAI-Compatible Endpoints](#openai-compatible-endpoints)
  - [Chat Completions](#chat-completions)
  - [Models List](#models-list)

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
```

If not provided, the service will fall back to the API keys specified in the `.env` file.

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
- `model` (string, optional): Specific model to use (e.g., "gemini-2.5-pro-exp-03-25", "grok-2-1212", "GigaChat-Pro")

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

## 🔄 OpenAI-Compatible Endpoints

### 🤖 Chat Completions

Generate chat completions in a format compatible with OpenAI's API.

**Endpoint**: `POST /v1/chat/completions`

**Authentication**: Required

**Headers**:
- `Authorization: Bearer sk-...` (required)
- `X-Google-API-Key: YOUR_KEY` (optional)
- `X-xAI-API-Key: YOUR_KEY` (optional)
- `X-GigaChat-API-Key: YOUR_KEY` (optional)

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