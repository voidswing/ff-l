from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.core.config import settings
from src.feature.judge.router import router as judge_router

load_dotenv()

app = FastAPI(
    title=settings.app_name,
    description="AI 판사 API",
    version="0.1.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


app.include_router(judge_router, prefix="/api")
