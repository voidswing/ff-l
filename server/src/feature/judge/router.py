from fastapi import APIRouter

from src.feature.judge.schemas import JudgmentResponse, StoryRequest
from src.feature.judge.service import judge_story

router = APIRouter(tags=["judge"])


@router.post("/judge", response_model=JudgmentResponse)
async def judge(payload: StoryRequest) -> JudgmentResponse:
    return await judge_story(payload.story)
