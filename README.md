<div align="center">
  <img src="frontend/user-dashboard/src/assets/Hyper.svg" alt="Hyper AI Gateway Logo" width="200" height="200"/>
</div>

# 🌐 Hyper AI Gateway

A unified API gateway for accessing multiple AI models including Gemini, Grok, GigaChat, and Perplexity Sonar.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.12-009688.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717.svg)](https://github.com/xuancanhit99/ai_model_gateway)

## 📋 Overview

Hyper AI Gateway is a service that provides a unified API interface to interact with different AI models through a standardized REST API. The service currently supports:

- **Gemini AI models** (Google)
- **Grok AI models** (xAI)
- **GigaChat models** (Sber)
- **Sonar models** (Perplexity AI)

Key features:
- OpenAI-compatible API interface
- Text generation API
- Image-to-text extraction
- Streaming responses
- Health monitoring
- Provider API Key Management (Store, manage, and import keys via UI)
- **Automatic API Key Failover**: Automatically rotates to the next available key upon encountering specific API errors (e.g., 401, 429).
- **Activity Logging**: Tracks key management actions (add, delete, select, import) and failover events.

## 🚀 Quick Start

### 🐳 Using Docker Compose

The simplest way to run the service is via Docker Compose:

```bash
# Clone the repository
git clone https://github.com/xuancanhit99/ai_model_gateway.git
cd ai_model_gateway

# Create and configure .env file (copy from example)
cp .env.example .env
# Edit the .env file to add your API keys

# Run with Docker Compose
docker-compose up -d
```

### 💻 Manual Setup

If you prefer a manual setup:

```bash
# Clone the repository
git clone https://github.com/xuancanhit99/ai_model_gateway.git
cd ai_model_gateway

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create and configure .env file
cp .env.example .env
# Edit the .env file to add your API keys

# Run the service
uvicorn main:app --host 0.0.0.0 --port 6161
```

## ⚙️ Configuration

Configure the service by editing the `.env` file:

```
# App settings
APP_NAME='AI Model Gateway'
APP_VERSION=1.0.0
APP_DESCRIPTION='Gateway service for multiple AI models'

# API settings
API_V1_STR=/api/v1

# Gemini Settings
GOOGLE_AI_STUDIO_API_KEY=your_google_api_key
GEMINI_VISION_MODEL_NAME=gemini-2.0-flash
GEMINI_CHAT_MODEL_NAME=gemini-2.5-pro-exp-03-25

# Grok Settings
XAI_API_KEY=your_xai_api_key
XAI_API_BASE_URL=https://api.x.ai/v1
GROK_CHAT_MODEL_NAME=grok-2-1212
GROK_VISION_MODEL_NAME=grok-2-vision-1212

# GigaChat Settings
GIGACHAT_AUTH_KEY=your_gigachat_auth_key
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_TOKEN_URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth
GIGACHAT_CHAT_URL=https://gigachat.devices.sberbank.ru/api/v1/chat/completions
GIGACHAT_DEFAULT_MODEL=GigaChat-Pro
```

## 📚 API Documentation

Once the service is running, you can explore the API documentation at:
- OpenAPI UI: `http://localhost:6161/docs`
- ReDoc: `http://localhost:6161/redoc`

For detailed API documentation, see [API Documentation](./docs/api.md).

## 🔌 Supported Endpoints

The service provides the following main endpoints:

- **Health Check**: `/api/v1/health`
- **Text Generation**: `/api/v1/chat/generate-text`
- **Text Extraction from Images**: `/api/v1/vision/extract-text`
- **OpenAI-Compatible Chat Completions**: `/v1/chat/completions`
- **OpenAI-Compatible Models List**: `/v1/models`
- **Provider Key Management**: `/api/v1/provider-keys`
- **Activity Logs**: `/api/v1/activity-logs`

## 🤖 Available Models

The service supports multiple models from different providers:

### 🔷 Gemini Models
- gemini-2.5-pro-exp-03-25
- gemini-2.0-flash
- gemini-1.5-pro
- And others...

### 🔶 Grok Models
- grok-2-1212
- grok-2-vision-1212
- grok-3-beta
- And others...

### 🔴 GigaChat Models
- GigaChat-Pro
- GigaChat-2
- GigaChat-2-Pro
- And others...

For a complete list of supported models, use the `/v1/models` endpoint.

## ✨ How It Works (Key Failover)

When making requests through the OpenAI-compatible endpoints (`/v1/chat/completions`) or the specific gateway endpoints (`/api/v1/chat/generate-text`, `/api/v1/vision/extract-text`):

1.  **Key Prioritization**: The gateway prioritizes API keys in this order:
    1.  Key provided in the request header (e.g., `X-Google-API-Key`).
    2.  The user's currently *selected* key for that provider (managed via the UI).
    3.  The fallback key defined in the `.env` file (if any).
2.  **Error Detection**: If the chosen key results in an API error indicative of a key issue (e.g., 401 Unauthorized, 403 Forbidden, 429 Too Many Requests), the failover mechanism is triggered.
3.  **Automatic Rotation**:
    *   The failing key is marked (temporarily disabled for 429 errors).
    *   The system attempts to find the *next available* (not disabled) key for that provider belonging to the user, rotating based on creation order.
    *   The newly found key is automatically selected (`is_selected` = true in the database).
4.  **Retry**: The original API request is retried using the newly selected key.
5.  **Exhaustion**: If all available keys for a provider fail consecutively, a 503 Service Unavailable error is returned.
6.  **Logging**: All failover events (key unselected due to error, new key selected, exhaustion) are recorded in the Activity Log.

This ensures higher availability and resilience by automatically handling temporary key issues or invalid keys.

## 📜 Activity Log

The gateway logs important events related to provider key management:
- **Manual actions via UI**: Add, Delete, Select/Unselect, Import keys.
- **System actions**: Automatic key selection/unselection during failover, key exhaustion events.
- **Detailed logging**: Each log entry includes timestamp, action type, provider name, key identifier, and description.

Logs can be viewed in the "Activity Log" section of the user dashboard or retrieved programmatically through the `/api/v1/activity-logs` endpoint.

Available log actions include:
- `ADD`: When a new provider key is added
- `DELETE`: When a provider key is deleted 
- `SELECT`: When a key is selected (manually or automatically via failover)
- `UNSELECT`: When a key is unselected (manually or due to errors)
- `IMPORT`: When keys are batch imported

This comprehensive logging system allows administrators to track key usage patterns, troubleshoot authentication issues, and monitor the automatic failover system's effectiveness.

## 🏗️ Project Structure

```
.
├── app/                  # Backend FastAPI application
│   ├── api/              # API endpoints (routes)
│   ├── core/             # Core components (auth, config, db client, utils)
│   ├── models/           # Pydantic models (schemas)
│   └── services/         # Business logic, external service interactions (AI models)
├── docs/                 # API documentation files (Markdown)
├── frontend/             # Frontend React application (User Dashboard)
│   └── user-dashboard/
│       ├── public/       # Static assets, locales
│       └── src/          # React source code
│           ├── assets/
│           ├── components/ # Reusable UI components
│           ├── services/   # Frontend API interaction logic (if any)
│           ├── styles/     # CSS, styling
│           └── ...         # Main app, routing, state management
├── .env.example          # Example environment variables
├── compose.yaml          # Docker Compose configuration
├── Dockerfile            # Main backend Dockerfile
├── main.py               # FastAPI application entry point
├── requirements.txt      # Backend Python dependencies
├── README.md             # This file
└── README.vi.md          # Vietnamese README
```

## 🔒 Security

API authentication uses Bearer tokens in the format `Bearer sk-...`.

## 📄 License

[MIT License](LICENSE)

## 👥 Contributing

We welcome contributions! Please feel free to submit a pull request.

## 🆘 Support

For issues and feature requests, please open an issue in the repository.