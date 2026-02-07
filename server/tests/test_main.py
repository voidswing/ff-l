from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.core.db.connection import engine
from src.feature.judge import service
from src.feature.judge import router as judge_router_module
from src.feature.judge.model import JudgeRequestLog
from src.feature.judge.schemas import JudgmentResponse
from src.feature.user.model import User
from src.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_judge_endpoint_works_without_api_key() -> None:
    original_key = service.settings.openai_api_key
    service.settings.openai_api_key = None
    service._build_client.cache_clear()

    client = TestClient(app)
    try:
        response = client.post("/api/judge", json={"story": "친구 카드로 결제했어요."})
    finally:
        service.settings.openai_api_key = original_key
        service._build_client.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]
    assert isinstance(payload["possible_crimes"], list)
    assert "법률 자문" in payload["disclaimer"]


def test_judge_endpoint_accepts_multipart_evidence() -> None:
    original_key = service.settings.openai_api_key
    service.settings.openai_api_key = None
    service._build_client.cache_clear()

    client = TestClient(app)
    try:
        response = client.post(
            "/api/judge",
            data={"story": "증거 사진이 있습니다."},
            files=[
                ("evidence_files", ("photo1.jpg", b"fake-image-data", "image/jpeg")),
                ("evidence_files", ("doc1.pdf", b"%PDF-1.4 fake-data", "application/pdf")),
            ],
        )
    finally:
        service.settings.openai_api_key = original_key
        service._build_client.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]
    assert isinstance(payload["possible_crimes"], list)
    assert "법률 자문" in payload["disclaimer"]


def test_judge_endpoint_rejects_more_than_three_evidence_files() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/judge",
        data={"story": "파일을 너무 많이 첨부합니다."},
        files=[
            ("evidence_files", ("1.jpg", b"1", "image/jpeg")),
            ("evidence_files", ("2.jpg", b"2", "image/jpeg")),
            ("evidence_files", ("3.jpg", b"3", "image/jpeg")),
            ("evidence_files", ("4.jpg", b"4", "image/jpeg")),
        ],
    )

    assert response.status_code == 422
    assert "최대 3개" in response.json()["detail"]


def test_judge_endpoint_ignores_string_placeholder_for_evidence_files() -> None:
    original_key = service.settings.openai_api_key
    service.settings.openai_api_key = None
    service._build_client.cache_clear()

    client = TestClient(app)
    try:
        response = client.post(
            "/api/judge",
            data={"story": "친구가 계속 놀려서 내가 때림"},
            files=[("evidence_files", (None, "string"))],
        )
    finally:
        service.settings.openai_api_key = original_key
        service._build_client.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]
    assert "법률 자문" in payload["disclaimer"]


def test_user_login_with_udid_creates_or_updates_user() -> None:
    client = TestClient(app)
    udid = "6f3ee6d0-9fdb-4eca-9f3f-6c74c56b830d"

    first = client.post("/api/user/login", json={"udid": udid})
    second = client.post("/api/user/login", json={"udid": udid})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["udid"] == udid
    assert second.json()["id"] == first.json()["id"]

    with Session(engine) as session:
        db_user = session.exec(select(User).where(User.udid == udid)).first()
        assert db_user is not None
        assert db_user.last_login_at is not None


def test_judge_request_and_result_are_saved_to_database() -> None:
    original_key = service.settings.openai_api_key
    service.settings.openai_api_key = None
    service._build_client.cache_clear()

    client = TestClient(app)
    udid = "0df52f15-6ea3-4bc8-b31b-0a3c42d39dca"
    try:
        response = client.post(
            "/api/judge",
            headers={"X-USER-UDID": udid},
            json={"story": "친구 카드로 결제했어요."},
        )
    finally:
        service.settings.openai_api_key = original_key
        service._build_client.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]

    with Session(engine) as session:
        row = session.exec(
            select(JudgeRequestLog).where(JudgeRequestLog.user_udid == udid)
        ).first()
        assert row is not None
        assert row.status == "completed"
        assert row.story == "친구 카드로 결제했어요."
        assert row.result_json is not None
        assert row.completed_at is not None


def test_judge_endpoint_schedules_slack_logs(monkeypatch) -> None:
    events: list[str] = []

    def fake_schedule(**kwargs):  # noqa: ANN003
        events.append(str(kwargs.get("event")))

    monkeypatch.setattr(judge_router_module, "_schedule_judge_slack_log", fake_schedule)

    client = TestClient(app)
    response = client.post(
        "/api/judge",
        headers={"X-USER-UDID": "1e9d0fc8-d992-4ca9-b648-33e0c8665f38"},
        json={"story": "친구가 계속 놀려서 내가 때림"},
    )

    assert response.status_code == 200
    assert events == ["received", "completed"]


def test_judge_endpoint_marks_failed_when_model_call_fails(monkeypatch) -> None:
    async def fake_judge_story(story: str, *, evidence_context=None):  # noqa: ANN001, ANN202
        return JudgmentResponse(
            summary="요약",
            possible_crimes=[],
            verdict="모델 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            disclaimer="법률 자문이 아니며 참고용입니다.",
        )

    monkeypatch.setattr(judge_router_module, "judge_story", fake_judge_story)

    client = TestClient(app)
    udid = "6cbf65d5-73c2-432e-9eb4-aac4b6b647f1"
    response = client.post(
        "/api/judge",
        headers={"X-USER-UDID": udid},
        json={"story": "친구가 계속 놀려서 내가 때림"},
    )

    assert response.status_code == 200
    with Session(engine) as session:
        row = session.exec(select(JudgeRequestLog).where(JudgeRequestLog.user_udid == udid)).first()
        assert row is not None
        assert row.status == "failed"
        assert row.error_message is not None
        assert "모델 호출에 실패" in row.error_message
