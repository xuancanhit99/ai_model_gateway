# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import vision, health, chat, openai_compat, manage_keys, manage_provider_keys, activity_logs, auth # Thêm activity_logs
from app.core.config import get_settings
from app.core.db import close_db_pool, init_db_pool

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
)


@app.on_event("startup")
async def startup_event():
    init_db_pool()


@app.on_event("shutdown")
async def shutdown_event():
    close_db_pool()

# Cấu hình CORS
origins = [
    "http://localhost",
    "http://localhost:5173",  # Local Vite dev server
    "http://localhost:6060",  # Local Nginx frontend
    "https://gateway.vnpay.dev",
    "https://gateway-api.vnpay.dev",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Authorization"],
)

# Health route
app.include_router(health.router, prefix=settings.API_V1_STR, tags=["Health"])

# Vision routes
app.include_router(vision.router, prefix=f"{settings.API_V1_STR}/vision", tags=["Vision"])

# Original Chat routes (keep them for backward compatibility)
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["Chat"])

# OpenAI compatible routes - Chỉ sử dụng prefix /v1
app.include_router(openai_compat.router, prefix="/v1", tags=["OpenAI Standard"])

# API Key Management routes
app.include_router(manage_keys.router, tags=["API Key Management"]) # Prefix is defined in the router itself

# Provider Key Management routes
app.include_router(manage_provider_keys.router, tags=["Provider Key Management"]) # Prefix is defined in the router itself

# Activity Log routes
app.include_router(activity_logs.router, prefix=f"{settings.API_V1_STR}/activity-logs", tags=["Activity Logs"])

# Auth routes
app.include_router(auth.router, tags=["Auth"])

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}!"}

if __name__ == "__main__":
    import uvicorn
    print(f"Starting server. Access API docs at http://127.0.0.1:6161/docs")
    uvicorn.run("main:app", host="127.0.0.1", port=6161, reload=True)
    # reload=True tự động cập nhật khi thay đổi mã - chỉ dùng cho môi trường phát triển
