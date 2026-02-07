from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.core.config import settings
from src.core.db.connection import init_db
from src.feature.judge.router import router as judge_router
from src.feature.user.router import router as user_router

load_dotenv()

app = FastAPI(
    title=settings.app_name,
    description="AI 판사 API",
    version="0.1.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


app.include_router(judge_router, prefix="/api")
app.include_router(user_router, prefix="/api")
