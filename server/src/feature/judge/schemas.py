from pydantic import BaseModel, Field


class StoryRequest(BaseModel):
    story: str = Field(..., min_length=3, max_length=5000, description="사용자가 입력한 사연")


class Judgment(BaseModel):
    title: str = Field(..., description="가능한 죄명")
    basis: str = Field(..., description="간단한 근거")
    severity: str = Field(..., description="경미/중간/중대 중 하나")


class JudgmentResponse(BaseModel):
    summary: str = Field(..., description="사연 요약")
    possible_crimes: list[Judgment] = Field(default_factory=list, description="가능한 죄 목록")
    verdict: str = Field(..., description="최종 판단 요약")
    disclaimer: str = Field(..., description="법률 자문 아님 안내")
