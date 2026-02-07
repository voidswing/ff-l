from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from src.core.db.connection import get_session
from src.feature.user.model import User
from src.feature.user.schemas import UserLoginRequest, UserLoginResponse

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/login", response_model=UserLoginResponse)
async def login(
    payload: UserLoginRequest,
    session: Annotated[Session, Depends(get_session)],
) -> UserLoginResponse:
    udid = payload.udid.strip()
    user = session.exec(select(User).where(User.udid == udid)).first()

    now = datetime.utcnow()
    if user is None:
        user = User(udid=udid, created_at=now, last_login_at=now)
        session.add(user)
    else:
        user.last_login_at = now
        session.add(user)

    session.commit()
    session.refresh(user)
    return UserLoginResponse.model_validate(user)
