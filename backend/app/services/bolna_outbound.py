"""Outbound Bolna call. Tests patch start_outbound_call so pytest never dials."""

import json
import os
import urllib.error
import urllib.request

BOLNA_CALL_URL = "https://api.bolna.ai/call"
AGENT_ID = "8ad7201e-2fe5-4595-8a45-35ed60fb1fcd"
FROM_NUMBER = "+14235838428"


def start_outbound_call(
    *,
    agent_id: str,
    recipient_phone_number: str,
    from_phone_number: str,
    user_data: dict,
) -> str:
    """Place one outbound call and return the Bolna execution id."""
    api_key = os.environ.get("BOLNA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BOLNA_API_KEY is required to place a call")
    body = {
        "agent_id": agent_id,
        "recipient_phone_number": recipient_phone_number,
        "from_phone_number": from_phone_number,
        "user_data": user_data,
    }
    request = urllib.request.Request(
        BOLNA_CALL_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Bolna call was rejected with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Bolna call could not be reached") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Bolna did not return an execution id")
    execution_id = payload.get("execution_id")
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise RuntimeError("Bolna did not return an execution id")
    return execution_id.strip()
