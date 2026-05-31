#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the question bank evaluation API.")
    parser.add_argument("--host", default=os.environ.get("QUESTION_BANK_API_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("QUESTION_BANK_API_PORT", "8000")),
    )
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    uvicorn.run(
        "evaluation_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
