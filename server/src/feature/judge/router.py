import json
from collections.abc import Sequence
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import ValidationError
from sqlmodel import Session, select
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.core.db.connection import get_session
from src.feature.judge.model import JudgeRequestLog
from src.feature.judge.schemas import JudgmentResponse, StoryRequest
from src.feature.judge.service import EvidenceValidationError, build_evidence_context, judge_story
from src.feature.user.model import User

router = APIRouter(tags=["judge"])


async def _close_upload_files(files: Sequence[UploadFile]) -> None:
    for upload in files:
        try:
            await upload.close()
        except Exception:  # noqa: BLE001 - 업로드 파일 정리는 best-effort
            pass


async def _parse_story_and_evidence(request: Request) -> tuple[str, list[UploadFile]]:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type:
        form = await request.form()
        story_raw = form.get("story")
        story = story_raw.strip() if isinstance(story_raw, str) else ""

        files: list[UploadFile] = []
        for key in ("evidence_files", "evidence_files[]", "evidenceFiles"):
            for item in form.getlist(key):
                if isinstance(item, StarletteUploadFile):
                    files.append(item)
        return story, files

    try:
        payload = StoryRequest.model_validate(await request.json())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="요청 본문을 해석할 수 없습니다.") from exc
    return payload.story, []


def _extract_udid(request: Request) -> str:
    udid = request.headers.get("X-USER-UDID", "").strip()
    return udid or "Anonymous"


def _upsert_user(session: Session, udid: str) -> None:
    existing = session.exec(select(User).where(User.udid == udid)).first()
    if existing is None:
        now = datetime.utcnow()
        session.add(User(udid=udid, created_at=now, last_login_at=now))
        session.commit()


@router.post("/judge", response_model=JudgmentResponse)
async def judge(
    request: Request,
    session: Session = Depends(get_session),
) -> JudgmentResponse:
    story, evidence_files = await _parse_story_and_evidence(request)
    try:
        payload = StoryRequest(story=story)
    except ValidationError as exc:
        await _close_upload_files(evidence_files)
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    try:
        evidence_context = await build_evidence_context(evidence_files)
    except EvidenceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    udid = _extract_udid(request)
    _upsert_user(session, udid)

    request_log = JudgeRequestLog(
        request_uuid=str(uuid4()),
        user_udid=udid,
        story=payload.story,
        evidence_count=len(evidence_context),
        evidence_files_json=json.dumps(evidence_context, ensure_ascii=False),
        status="processing",
    )
    session.add(request_log)
    session.commit()
    session.refresh(request_log)

    try:
        result = await judge_story(payload.story, evidence_context=evidence_context)
        request_log.status = "completed"
        request_log.result_summary = result.summary
        request_log.result_verdict = result.verdict
        request_log.result_json = result.model_dump_json()
        request_log.completed_at = datetime.utcnow()
        session.add(request_log)
        session.commit()
        return result
    except Exception as exc:  # noqa: BLE001 - 판단 실패를 DB에 기록하기 위한 처리
        request_log.status = "failed"
        request_log.error_message = str(exc)[:2000]
        request_log.completed_at = datetime.utcnow()
        session.add(request_log)
        session.commit()
        raise
