import asyncio
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
