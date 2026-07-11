#!/usr/bin/env python3
"""Refresh byte sizes and SHA-256 values for files listed by a run manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()

    manifest_path = args.run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for relative, metadata in manifest.get("outputs", {}).items():
        path = args.run_dir / relative
        if not path.is_file():
            missing.append(relative)
            continue
        metadata["bytes"] = path.stat().st_size
        metadata["sha256"] = sha256_file(path)

    if missing:
        raise SystemExit("Missing manifest outputs: " + ", ".join(missing))

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Refreshed {len(manifest.get('outputs', {}))} output records: {manifest_path}")


if __name__ == "__main__":
    main()
