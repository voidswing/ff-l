# AI 판사 서버

간단한 사연을 입력받아 GPT가 어떤 죄가 가능한지 추정해 주는 FastAPI 서버입니다.

## 실행

```bash
cd server
uv sync
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## 환경변수

`.env.example`을 참고해서 `.env`를 생성하세요.

선택 환경변수:
- `OPENAI_MODEL` (기본값: `gpt-4o-mini`)

## 엔드포인트

- `GET /health`
- `POST /api/judge`

요청 예시:

```json
{
  "story": "친구 몰래 신용카드를 사용해 결제했어."
}
```
