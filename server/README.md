# AI 판사 서버

간단한 사연을 입력받아 GPT가 어떤 죄가 가능한지 추정해 주는 FastAPI 서버입니다.

`ff-postgres` 기반으로 동작하며, 다음 데이터를 DB에 저장합니다.
- UUID 로그인 사용자(`app_user`)
- 판단 요청 수신 시점 로그(`judge_request_log`, status=`processing`)
- LLM 결과 수신 후 결과/상태 업데이트(`completed` 또는 `failed`)

## Docker 실행 (ff/d, ff/a와 동일 패턴)

사전 준비:

```bash
cd ../..
docker compose -f docker-compose-db.yml up -d
```

API 실행:

```bash
cd l/server
docker compose up --build
```

접속:
- API: `http://localhost:8003`
- Docs: `http://localhost:8003/docs`

## 실행

```bash
cd server
uv sync
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## 환경변수

`.env.example`을 참고해서 `.env`를 생성하세요.

선택 환경변수:
- `OPENAI_MODEL` (기본값: `gpt-5-nano`)
- `OPENAI_TIMEOUT_SECONDS` (기본값: `20`)
- `DB_HOST` (기본값: `ff-postgres`)
- `DB_PORT` (기본값: `5432`)
- `DB_NAME` (기본값: `l`)
- `DB_USER` (기본값: `postgres`)
- `DB_PASSWORD` (기본값: `postgres`)
- `DATABASE_URL` (지정 시 위 DB_* 값을 무시하고 우선 사용)
- `DB_ECHO` (기본값: `false`)
- `SLACK_TOKEN` (`judge` API 요청/완료/실패 로그 전송용)
- `SLACK_LOG_CHANNEL` (기본값: `#l`)
- `CORS_ALLOW_ORIGINS` (기본값: `["*"]`)
- `CORS_ALLOW_CREDENTIALS` (기본값: `false`)

## 엔드포인트

- `GET /health`
- `POST /api/user/login`
- `POST /api/judge`

로그인 요청 예시:

```json
{
  "udid": "6f3ee6d0-9fdb-4eca-9f3f-6c74c56b830d"
}
```

요청 예시:

```json
{
  "story": "친구 몰래 신용카드를 사용해 결제했어."
}
```

`/api/judge` 호출 시 `X-USER-UDID` 헤더를 함께 보내면 사용자 기준으로 요청/결과가 기록됩니다.
