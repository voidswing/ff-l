from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class UserLoginRequest(BaseModel):
    udid: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="클라이언트 UUID/UDID",
        validation_alias=AliasChoices("udid", "uuid"),
        serialization_alias="udid",
    )


class UserLoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    udid: str
    created_at: datetime
    last_login_at: datetime
