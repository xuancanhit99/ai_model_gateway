# app/main.py
from fastapi import FastAPI
from app.api.routes import vision, health, chat, openai_compat
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
)

# Health route
app.include_router(health.router, prefix=settings.API_V1_STR, tags=["Health"])

# Vision routes
app.include_router(vision.router, prefix=f"{settings.API_V1_STR}/vision", tags=["Vision"])

# Original Chat routes (keep them for backward compatibility)
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["Chat"])

# OpenAI compatible routes - CHANGED PREFIX to be directly at /v1 instead of /api/v1/chat
# This makes it compatible with tools expecting standard OpenAI API structure
app.include_router(openai_compat.router, prefix="/v1", tags=["OpenAI Compatible"])

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}!"}

if __name__ == "__main__":
    import uvicorn
    print(f"Starting server. Access API docs at http://127.0.0.1:6161/docs")
    uvicorn.run("main:app", host="127.0.0.1", port=6161, reload=True)
    # reload=True tự động cập nhật khi thay đổi mã - chỉ dùng cho môi trường phát triển