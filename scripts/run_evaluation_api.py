#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys

import uvicorn

# Make sure sibling modules under scripts/ are importable when launched as a script.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the question bank evaluation API.")
    parser.add_argument("--host", default=os.environ.get("QUESTION_BANK_API_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("QUESTION_BANK_API_PORT", "8000")),
    )
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload.")
    parser.add_argument(
        "--no-auto-master-key",
        action="store_true",
        help="Skip auto-generating QUESTION_BANK_SECRET_KEY when missing.",
    )
    parser.add_argument(
        "--strict-master-key",
        action="store_true",
        help=(
            "Refuse to auto-generate at startup; only load .env if it already exists. "
            "Used for end-to-end tests that need a no-key 503 response."
        ),
    )
    return parser.parse_args()


def _bootstrap_master_key(no_auto: bool, strict: bool) -> None:
    """Best-effort import so we can print a startup banner before uvicorn takes over."""
    try:
        from provider_runtime import ensure_master_key
    except Exception as exc:  # noqa: BLE001
        print(f"[master-key] provider_runtime import failed: {exc}", file=sys.stderr)
        return
    auto = False if (no_auto or strict) else True
    status = ensure_master_key(auto_generate=auto, emit=print, load_dotenv=not strict)
    if status.get("generated"):
        path = status.get("path") or "<in-memory only>"
        print(f"[master-key] persisted to {path}")


if __name__ == "__main__":
    args = parse_args()
    _bootstrap_master_key(no_auto=args.no_auto_master_key, strict=args.strict_master_key)
    uvicorn.run(
        "evaluation_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
