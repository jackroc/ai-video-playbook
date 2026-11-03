#!/usr/bin/env python3
"""Send a plain-text collection status through the locally configured webhook."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def webhook_url():
    value = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not value:
        path = ROOT / ".env"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("FEISHU_WEBHOOK_URL="):
                    value = line.split("=", 1)[1].strip()
                    break
    if not re.fullmatch(
        r"https://open\.feishu\.cn/open-apis/bot/v2/hook/[a-zA-Z0-9-]+", value
    ):
        raise ValueError("Configure a valid FEISHU_WEBHOOK_URL in the local .env.")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def notify(text):
    payload = json.dumps(
        {"msg_type": "text", "content": {"text": text}}, ensure_ascii=False
    ).encode("utf-8")
    if len(payload) > 20000:
        raise ValueError("Notification exceeds the webhook payload limit.")
    request = urllib.request.Request(
        webhook_url(), data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as r:
            result = json.load(r)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Webhook returned HTTP {exc.code}.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("Webhook request failed; delivery status is unknown.") from None
    if result.get("code", result.get("StatusCode")) != 0:
        # Do not log the URL or untrusted response bodies.
        raise RuntimeError(f"Webhook rejected notification: code={result.get('code', result.get('StatusCode'))}.")
    return {"ok": True, "notification": "delivered"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(notify(args.text)))
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
