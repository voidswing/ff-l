import asyncio
import logging
from io import BytesIO

from fastapi import UploadFile

from src.feature.judge import service


def test_extract_json_from_embedded_text() -> None:
    text = "결과입니다.\n```json\n{\"summary\":\"요약\",\"possible_crimes\":[],\"verdict\":\"판단\",\"disclaimer\":\"법률 자문이 아닙니다.\"}\n```"
    extracted = service._extract_json(text)

    assert extracted is not None
    assert extracted["summary"] == "요약"


def test_normalize_response_fills_defaults() -> None:
    response = service._normalize_response(
        {
            "summary": "",
            "possible_crimes": [
                {"title": "절도", "basis": "타인 재물을 무단 취득", "severity": "high"},
                {"title": "", "basis": "빈 제목", "severity": "중간"},
            ],
            "verdict": "",
            "disclaimer": "참고용 안내",
        },
        story="친구 지갑에서 돈을 가져갔어요.",
    )

    assert response.summary == "친구 지갑에서 돈을 가져갔어요."
    assert response.verdict == "판단 요약을 제공하지 못했습니다."
    assert response.disclaimer.endswith("(법률 자문이 아님)")
    assert len(response.possible_crimes) == 1
    assert response.possible_crimes[0].severity == "중대"


def test_judge_story_without_api_key_returns_fallback() -> None:
    original_key = service.settings.openai_api_key
    service.settings.openai_api_key = None
    service._build_client.cache_clear()

    try:
        result = asyncio.run(service.judge_story("친구 돈을 허락 없이 썼어요."))
    finally:
        service.settings.openai_api_key = original_key
        service._build_client.cache_clear()

    assert result.possible_crimes == []
    assert "모의 판단" in result.verdict
    assert "법률 자문" in result.disclaimer


def test_build_evidence_context_rejects_unsupported_file_extension() -> None:
    evidence_file = UploadFile(filename="malware.exe", file=BytesIO(b"dummy"))

    try:
        asyncio.run(service.build_evidence_context([evidence_file]))
    except service.EvidenceValidationError as exc:
        assert "지원하지 않는 파일 형식" in str(exc)
    else:
        raise AssertionError("EvidenceValidationError was not raised for unsupported extension")


def test_build_evidence_context_allows_pdf_and_image() -> None:
    image_file = UploadFile(filename="photo.jpg", file=BytesIO(b"image-bytes"))
    pdf_file = UploadFile(filename="document.pdf", file=BytesIO(b"%PDF-1.4"))

    context = asyncio.run(service.build_evidence_context([image_file, pdf_file]))

    assert len(context) == 2
    assert "photo.jpg" in context[0]
    assert "document.pdf" in context[1]


def test_judge_story_logs_model_call_failure_reason(monkeypatch, caplog) -> None:
    class FailingCompletions:
        async def create(self, **kwargs):  # noqa: ANN003
            raise RuntimeError("upstream timeout")

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FailingCompletions()

    class FakeClient:
        def __init__(self) -> None:
            self.chat = FakeChat()

    monkeypatch.setattr(service, "_build_client", lambda: FakeClient())
    caplog.set_level(logging.ERROR)

    result = asyncio.run(service.judge_story("친구가 날 밀쳤다"))

    assert "모델 호출에 실패했습니다" in result.verdict
    assert "OpenAI model call failed" in caplog.text
    assert "upstream timeout" in caplog.text


def test_judge_story_logs_parse_failure_reason(monkeypatch, caplog) -> None:
    class PassingCompletions:
        async def create(self, **kwargs):  # noqa: ANN003
            choice = type("Choice", (), {"message": type("Msg", (), {"content": "not-json"})()})()
            return type("Resp", (), {"choices": [choice]})()

    class FakeChat:
        def __init__(self) -> None:
            self.completions = PassingCompletions()

    class FakeClient:
        def __init__(self) -> None:
            self.chat = FakeChat()

    monkeypatch.setattr(service, "_build_client", lambda: FakeClient())
    caplog.set_level(logging.ERROR)

    result = asyncio.run(service.judge_story("친구가 날 밀쳤다"))

    assert "모델 응답을 파싱하지 못했습니다" in result.verdict
    assert "Failed to parse model response as JSON" in caplog.text


def test_judge_story_uses_max_completion_tokens_for_gpt5_models(monkeypatch) -> None:
    called_kwargs: dict[str, object] = {}

    class PassingCompletions:
        async def create(self, **kwargs):  # noqa: ANN003
            called_kwargs.update(kwargs)
            choice = type(
                "Choice",
                (),
                {"message": type("Msg", (), {"content": "{\"summary\":\"요약\",\"possible_crimes\":[],\"verdict\":\"판단\",\"disclaimer\":\"법률 자문이 아닙니다.\"}"})()},
            )()
            return type("Resp", (), {"choices": [choice]})()

    class FakeChat:
        def __init__(self) -> None:
            self.completions = PassingCompletions()

    class FakeClient:
        def __init__(self) -> None:
            self.chat = FakeChat()

    monkeypatch.setattr(service, "_build_client", lambda: FakeClient())

    result = asyncio.run(service.judge_story("친구가 날 밀쳤다"))

    assert result.summary == "요약"
    assert called_kwargs["max_completion_tokens"] == 700
    assert "max_tokens" not in called_kwargs
    assert "temperature" not in called_kwargs


def test_judge_story_retries_when_first_response_is_empty(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class RetryingCompletions:
        async def create(self, **kwargs):  # noqa: ANN003
            calls.append(kwargs)
            if len(calls) == 1:
                # 첫 호출은 빈 content
                choice = type("Choice", (), {"message": type("Msg", (), {"content": ""})()})()
                return type("Resp", (), {"choices": [choice]})()
            # 두 번째 호출은 JSON 응답
            choice = type(
                "Choice",
                (),
                {"message": type("Msg", (), {"content": "{\"summary\":\"요약\",\"possible_crimes\":[],\"verdict\":\"판단\",\"disclaimer\":\"법률 자문이 아닙니다.\"}"})()},
            )()
            return type("Resp", (), {"choices": [choice]})()

    class FakeChat:
        def __init__(self) -> None:
            self.completions = RetryingCompletions()

    class FakeClient:
        def __init__(self) -> None:
            self.chat = FakeChat()

    monkeypatch.setattr(service, "_build_client", lambda: FakeClient())

    result = asyncio.run(service.judge_story("친구가 날 밀쳤다"))

    assert result.summary == "요약"
    assert len(calls) == 2
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]


def test_judge_story_does_not_use_secondary_model_when_gpt5_returns_empty(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class EmptyCompletions:
        async def create(self, **kwargs):  # noqa: ANN003
            calls.append(kwargs)
            choice = type("Choice", (), {"message": type("Msg", (), {"content": ""})()})()
            return type("Resp", (), {"choices": [choice]})()

    class FakeChat:
        def __init__(self) -> None:
            self.completions = EmptyCompletions()

    class FakeClient:
        def __init__(self) -> None:
            self.chat = FakeChat()

    original_model = service.settings.openai_model
    service.settings.openai_model = "gpt-5.2"
    monkeypatch.setattr(service, "_build_client", lambda: FakeClient())
    try:
        result = asyncio.run(service.judge_story("친구가 날 밀쳤다"))
    finally:
        service.settings.openai_model = original_model

    assert "모델 응답을 파싱하지 못했습니다" in result.verdict
    models = [str(item.get("model")) for item in calls]
    # primary 1차 + retry 1차
    assert models[0] == "gpt-5.2"
    assert models[1] == "gpt-5.2"
    assert all(model == "gpt-5.2" for model in models)
