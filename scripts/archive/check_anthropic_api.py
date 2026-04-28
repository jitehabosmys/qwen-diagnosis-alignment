#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def parse_args() -> argparse.Namespace:
    load_dotenv(Path(".env"))
    parser = argparse.ArgumentParser(description="Check whether an Anthropic-compatible /v1/messages API responds correctly.")
    parser.add_argument("--base-url", default=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"), help="Anthropic-compatible API base URL.")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY"), help="API key. Falls back to ANTHROPIC_API_KEY.")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"), help="Model name.")
    parser.add_argument("--anthropic-version", default=os.environ.get("ANTHROPIC_VERSION", "2023-06-01"), help="Anthropic API version header.")
    parser.add_argument("--prompt", default="Reply with exactly OK", help="User prompt for the probe request.")
    parser.add_argument("--system", default="You are a health check probe. Keep responses minimal.", help="System prompt for the probe request.")
    parser.add_argument("--max-tokens", type=int, default=32, help="Max tokens for the probe response.")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature.")
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout in seconds.")
    parser.add_argument("--show-headers", action="store_true", help="Print response headers on success.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("Missing API key. Use --api-key or ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1

    url = args.base_url.rstrip("/") + "/v1/messages"
    body = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "system": args.system,
        "messages": [{"role": "user", "content": args.prompt}],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "content-type": "application/json",
            "x-api-key": args.api_key,
            "anthropic-version": args.anthropic_version,
        },
        method="POST",
    )

    print(json.dumps({"url": url, "model": args.model, "anthropic_version": args.anthropic_version}, ensure_ascii=False))

    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            print(f"HTTP {resp.status}")
            if args.show_headers:
                print("HEADERS")
                for key, value in resp.headers.items():
                    print(f"{key}: {value}")
            print("BODY")
            print(raw)
            return 0
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}", file=sys.stderr)
        print("BODY", file=sys.stderr)
        print(raw, file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"REQUEST_ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
