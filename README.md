# 🌐 AI Model Gateway

A unified API gateway for accessing multiple AI models including Gemini, Grok, and GigaChat.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.12-009688.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717.svg)](https://github.com/xuancanhit99/ai_model_gateway)

## 📋 Overview

AI Model Gateway is a service that provides a unified API interface to interact with different AI models through a standardized REST API. The service currently supports:

- **Gemini AI models** (Google)
- **Grok AI models** (xAI)
- **GigaChat models** (Sber)

Key features:
- OpenAI-compatible API interface
- Text generation API
- Image-to-text extraction
- Streaming responses
- Health monitoring

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

## 🔒 Security

API authentication uses Bearer tokens in the format `Bearer sk-...`.

## 📄 License

[MIT License](LICENSE)

## 👥 Contributing

We welcome contributions! Please feel free to submit a pull request.

## 🆘 Support

For issues and feature requests, please open an issue in the repository.