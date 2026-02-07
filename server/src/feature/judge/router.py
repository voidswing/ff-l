import asyncio
import json
import logging
from collections.abc import Sequence
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError
from sqlmodel import Session, select
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.core.db.connection import get_session
from src.feature.judge.model import JudgeRequestLog
from src.feature.judge.schemas import JudgmentResponse, StoryRequest
from src.feature.judge.service import EvidenceValidationError, build_evidence_context, judge_story
from src.feature.user.model import User
from src.utils.slack import send_slack_message
from src.core.config import settings

router = APIRouter(tags=["judge"])
logger = logging.getLogger(__name__)


async def _close_upload_files(files: Sequence[UploadFile]) -> None:
    for upload in files:
        try:
            await upload.close()
        except Exception:  # noqa: BLE001 - 업로드 파일 정리는 best-effort
            pass


async def _parse_story_and_evidence(
    request: Request,
    *,
    story_form: str | None,
    evidence_files_form: list[UploadFile | str] | None,
) -> tuple[str, list[UploadFile]]:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type:
        story = story_form.strip() if isinstance(story_form, str) else ""
        raw_items = list(evidence_files_form or [])
        normalized: list[UploadFile] = []
        for item in raw_items:
            # Swagger UI 기본 placeholder("string") 같은 문자열 필드는 무시한다.
            if isinstance(item, StarletteUploadFile):
                normalized.append(item)
        return story, normalized

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


def _shorten(text: str, max_length: int = 120) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[:max_length] + "..."


async def _send_judge_log_to_slack(
    *,
    event: str,
    request_uuid: str,
    udid: str,
    story: str,
    evidence_count: int,
    status: str | None = None,
    reason: str | None = None,
) -> None:
    token = settings.slack_token
    if not token:
        return

    text_lines = [
        f"*Judge API {event}*",
        f"- request_uuid: `{request_uuid}`",
        f"- udid: `{udid}`",
        f"- story: {_shorten(story)}",
        f"- evidence_count: {evidence_count}",
    ]
    if status:
        text_lines.append(f"- status: `{status}`")
    if reason:
        text_lines.append(f"- reason: `{_shorten(reason, 200)}`")

    payload = {
        "text": f"judge {event}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(text_lines),
                },
            }
        ],
    }
    try:
        await send_slack_message(
            channel=settings.slack_log_channel,
            payload=payload,
            slack_token=token,
        )
    except Exception as exc:  # noqa: BLE001 - Slack 실패는 비즈니스 흐름 차단 금지
        logger.exception("Failed to send judge slack log | error=%s", str(exc))


def _schedule_judge_slack_log(**kwargs: str | int | None) -> None:
    # endpoint 응답 지연을 막기 위해 fire-and-forget
    asyncio.create_task(_send_judge_log_to_slack(**kwargs))


def _is_judgment_failure(result: JudgmentResponse) -> bool:
    verdict = result.verdict.strip()
    return verdict.startswith("모델 호출에 실패했습니다") or verdict.startswith("모델 응답을 파싱하지 못했습니다")


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
    story: str | None = Form(default=None, min_length=3, max_length=5000),
    evidence_files: list[UploadFile | str] | None = File(default=None),
) -> JudgmentResponse:
    story, evidence_files = await _parse_story_and_evidence(
        request,
        story_form=story,
        evidence_files_form=evidence_files,
    )
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
    _schedule_judge_slack_log(
        event="received",
        request_uuid=request_log.request_uuid,
        udid=udid,
        story=payload.story,
        evidence_count=len(evidence_context),
        status="processing",
    )
    logger.info(
        "Judge request received | request_uuid=%s | udid=%s | story_length=%d | evidence_count=%d",
        request_log.request_uuid,
        udid,
        len(payload.story),
        len(evidence_context),
    )

    try:
        result = await judge_story(payload.story, evidence_context=evidence_context)
        if _is_judgment_failure(result):
            request_log.status = "failed"
            request_log.error_message = result.verdict
        else:
            request_log.status = "completed"
        request_log.result_summary = result.summary
        request_log.result_verdict = result.verdict
        request_log.result_json = result.model_dump_json()
        request_log.completed_at = datetime.utcnow()
        session.add(request_log)
        session.commit()
        _schedule_judge_slack_log(
            event="completed",
            request_uuid=request_log.request_uuid,
            udid=udid,
            story=payload.story,
            evidence_count=len(evidence_context),
            status=request_log.status,
            reason=request_log.error_message,
        )
        logger.info(
            "Judge request completed | request_uuid=%s | udid=%s | status=%s | verdict_preview=%s",
            request_log.request_uuid,
            udid,
            request_log.status,
            _shorten(result.verdict, 160),
        )
        return result
    except Exception as exc:  # noqa: BLE001 - 판단 실패를 DB에 기록하기 위한 처리
        request_log.status = "failed"
        request_log.error_message = str(exc)[:2000]
        request_log.completed_at = datetime.utcnow()
        session.add(request_log)
        session.commit()
        _schedule_judge_slack_log(
            event="failed",
            request_uuid=request_log.request_uuid,
            udid=udid,
            story=payload.story,
            evidence_count=len(evidence_context),
            status="failed",
            reason=request_log.error_message,
        )
        logger.exception(
            "Judge request failed with unhandled exception | request_uuid=%s | udid=%s | error=%s",
            request_log.request_uuid,
            udid,
            str(exc),
        )
        raise
