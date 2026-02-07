from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class JudgeRequestLog(SQLModel, table=True):
    __tablename__ = "judge_request_log"

    id: int | None = Field(default=None, primary_key=True)
    request_uuid: str = Field(index=True, unique=True, max_length=36)
    user_udid: str = Field(index=True, max_length=64)
    story: str = Field(sa_column=Column(Text, nullable=False))
    evidence_count: int = Field(default=0)
    evidence_files_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="processing", max_length=20)
    result_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    result_verdict: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    result_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
