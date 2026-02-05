import json
from typing import Any

from openai import OpenAI

from src.core.config import settings
from src.feature.judge.schemas import JudgmentResponse

SYSTEM_PROMPT = """
너는 한국어로 답하는 'AI 판사'야.
사용자의 사연을 읽고, 가능한 죄명과 근거를 조심스럽게 추정해.
반드시 JSON만 출력하고, 아래 스키마를 정확히 따를 것:
{
  "summary": string,
  "possible_crimes": [
    {"title": string, "basis": string, "severity": "경미"|"중간"|"중대"}
  ],
  "verdict": string,
  "disclaimer": string
}
주의:
- 확실하지 않으면 "가능성이 낮음" 같은 완화 표현을 사용
- 사실관계가 부족하면 그 점을 명시
- 단정적 유죄 표현 금지 (가능성/의심/추정 표현 사용)
- 인격 모욕, 혐오 발언 금지
- 법률 자문이 아님을 disclaimer에 명시
""".strip()


def _build_client() -> OpenAI | None:
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_json(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return _safe_json_loads(text[start : i + 1])
    return None


def _normalize_severity(value: str) -> str:
    normalized = value.strip()
    if normalized in {"경미", "중간", "중대"}:
        return normalized
    if normalized in {"낮음", "경미함", "가벼움"}:
        return "경미"
    if normalized in {"보통", "중간정도"}:
        return "중간"
    if normalized in {"높음", "심각", "중함"}:
        return "중대"
    return "중간"


def _normalize_response(data: dict[str, Any], story: str) -> JudgmentResponse:
    summary = str(data.get("summary") or story[:140] + ("..." if len(story) > 140 else ""))
    verdict = str(data.get("verdict") or "판단 요약을 제공하지 못했습니다.")
    disclaimer = str(data.get("disclaimer") or "법률 자문이 아니며 참고용입니다.")
    if "법률" not in disclaimer:
        disclaimer = f"{disclaimer} (법률 자문이 아님)"

    crimes_raw = data.get("possible_crimes") or []
    crimes = []
    if isinstance(crimes_raw, list):
        for item in crimes_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            basis = str(item.get("basis") or "").strip()
            if not title or not basis:
                continue
            severity = _normalize_severity(str(item.get("severity") or "중간"))
            crimes.append({"title": title, "basis": basis, "severity": severity})

    return JudgmentResponse(
        summary=summary,
        possible_crimes=crimes,
        verdict=verdict,
        disclaimer=disclaimer,
    )


def _fallback_response(story: str) -> JudgmentResponse:
    return JudgmentResponse(
        summary=story[:140] + ("..." if len(story) > 140 else ""),
        possible_crimes=[],
        verdict="OPENAI_API_KEY가 설정되지 않아 모의 판단만 제공합니다.",
        disclaimer="법률 자문이 아니며 참고용입니다.",
    )


async def judge_story(story: str) -> JudgmentResponse:
    client = _build_client()
    if client is None:
        return _fallback_response(story)

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": story},
            ],
            temperature=0.2,
            max_tokens=650,
        )
    except Exception as exc:  # noqa: BLE001 - 외부 API 예외를 넓게 수용
        return JudgmentResponse(
            summary=story[:140] + ("..." if len(story) > 140 else ""),
            possible_crimes=[],
            verdict=f"모델 호출에 실패했습니다: {exc}",
            disclaimer="법률 자문이 아니며 참고용입니다.",
        )

    content = response.choices[0].message.content or ""
    data = _safe_json_loads(content) or _extract_json(content)
    if not data:
        return JudgmentResponse(
            summary=story[:140] + ("..." if len(story) > 140 else ""),
            possible_crimes=[],
            verdict=content[:300] if content else "모델 응답을 파싱하지 못했습니다.",
            disclaimer="법률 자문이 아니며 참고용입니다.",
        )

    return _normalize_response(data, story)
