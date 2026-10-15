from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.news import news_router

from app.config import settings
from app.config.cors import headers, methods, origins

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=methods,
    allow_headers=headers,
)

@app.get("/")
async def root():
    return {"service": settings.APP_NAME, "version": settings.APP_VERSION}

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(news_router)