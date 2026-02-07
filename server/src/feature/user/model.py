from datetime import datetime

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "app_user"

    id: int | None = Field(default=None, primary_key=True)
    udid: str = Field(
        sa_column=Column(String(64), unique=True, nullable=False, index=True),
        description="클라이언트 UUID/UDID",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: datetime = Field(default_factory=datetime.utcnow)
