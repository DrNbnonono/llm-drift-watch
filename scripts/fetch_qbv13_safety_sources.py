#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from question_bank_runtime import MANIFESTS, ROOT


SOURCE_CONFIG = ROOT / "config" / "qbv13_safety_sources.json"
RAW_ROOT = ROOT / "raw_sources" / "qbv13-safety"
SNAPSHOT_MANIFEST = MANIFESTS / "qbv13_safety_source_snapshots.json"
ALLOWED_LICENSES = {"MIT", "Apache-2.0", "CC-BY-4.0", "BSD-3-Clause"}


def validate_source(source: dict[str, Any]) -> None:
    if source.get("enabled") and source.get("license") not in ALLOWED_LICENSES:
        raise ValueError(f"source {source.get('id')} license is not allowed: {source.get('license')}")
    required = {"id", "dataset", "url", "revision", "license", "modules", "enabled"}
    missing = sorted(required - set(source))
    if missing:
        raise ValueError(f"source {source.get('id', '<unknown>')} missing fields: {missing}")
    if source.get("enabled") and not str(source.get("url", "")).startswith("https://"):
        raise ValueError(f"source {source.get('id')} must use https")


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def source_filename(source: dict[str, Any]) -> str:
    name = Path(urllib.parse.urlparse(source["url"]).path).name
    return name or f"{source['id']}.data"


def download_source(source: dict[str, Any], raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    validate_source(source)
    if not source.get("enabled"):
        return {**source, "status": "disabled"}
    request = urllib.request.Request(
        source["url"], headers={"User-Agent": "qbv13-safety-builder/1.0"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    if not payload:
        raise ValueError(f"source {source['id']} returned an empty payload")
    target = raw_root / source["id"] / source_filename(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(target)
    return {
        **source,
        "status": "downloaded",
        "local_path": str(target),
        "bytes": len(payload),
        "content_sha256": sha256_bytes(payload),
    }


def fetch_sources(config_path: Path = SOURCE_CONFIG, raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    snapshots = [download_source(source, raw_root) for source in config.get("sources", [])]
    return {"schema_version": 1, "sources": snapshots}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch pinned QB-v1.3 safety benchmark sources.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    payload = fetch_sources()
    if args.write:
        SNAPSHOT_MANIFEST.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
