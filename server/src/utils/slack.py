from typing import Any

import httpx


async def send_slack_message(
    channel: str,
    payload: dict[str, Any],
    slack_token: str,
    thread_ts: str | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {slack_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    body = {"channel": channel, **payload}
    if thread_ts:
        body["thread_ts"] = thread_ts

    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json=body,
        )

    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data}")
    return data
