"""Ask every starter question against a running Verity, so first visitors get fast answers.

Why: the free host sleeps when idle and free model quotas are slow. Running this after each
deploy wakes the app and fills its shared answer cache for the sample data, which is what the
starter chips on the landing page ask (docs/DESIGN.md, section 5).

Usage: make warm URL=https://your-app.onrender.com
Standard library only, so it runs anywhere Python does.
"""

from __future__ import annotations

import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

STARTERS = Path(__file__).resolve().parents[2] / "demo_data" / "starters.json"
TIMEOUT_S = 180  # a sleeping free instance takes about a minute to wake
PAUSE_S = 5  # free model tiers allow only a few thousand tokens a minute


def last_event(stream: str) -> tuple[str, dict]:
    """Return the final (event, payload) of a server-sent-event body, skipping ": ping" heartbeats."""
    event, payload = "error", {"message": "The stream ended without an answer."}
    for block in stream.split("\n\n"):
        lines = [line for line in block.splitlines() if ": " in line and not line.startswith(":")]
        fields = dict(line.split(": ", 1) for line in lines)
        if "event" in fields and "data" in fields:
            event, payload = fields["event"], json.loads(fields["data"])
    return event, payload


def _post(url: str, body: dict | None = None) -> str:
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    request = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return response.read().decode("utf-8")


def main(base_url: str) -> int:
    base = base_url.rstrip("/")
    if not base.startswith(("https://", "http://")):
        print(f"'{base_url}' is not a web address. Use something like https://your-app.onrender.com")
        return 2
    try:
        session_id = json.loads(_post(f"{base}/api/sessions"))["session_id"]
        _post(f"{base}/api/sessions/{session_id}/sample")
        failed = 0
        for question in json.loads(STARTERS.read_text(encoding="utf-8")):
            started = time.monotonic()
            event, payload = last_event(_post(f"{base}/api/sessions/{session_id}/ask", {"question": question}))
            kind = payload.get("kind", event)
            failed += kind == "error"
            print(f"{kind:<8} {time.monotonic() - started:5.1f}s  {question}")
            if kind == "error":
                print(f"{'':<16}{payload.get('text') or payload.get('message', '')}")
            time.sleep(PAUSE_S)
    except urllib.error.HTTPError as e:
        print(f"The app answered with HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
        return 1
    except (OSError, http.client.HTTPException) as e:  # unreachable, timed out, or dropped mid-reply
        print(f"Could not reach {base}: {e}. Check the address and that the app is deployed.")
        return 1
    except (ValueError, KeyError):  # a reply that is not Verity's JSON, e.g. a web page at a mistyped address
        print(f"{base} replied, but not the way Verity does. Check that the address is the deployed app.")
        return 1
    if failed:
        print(f"{failed} question(s) ended in an error and were not cached. Run this again in a minute.")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: make warm URL=https://your-app.onrender.com")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
