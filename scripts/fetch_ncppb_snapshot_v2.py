#!/usr/bin/env python3
"""Download and preserve an NCPPB catalogue HTML snapshot when a stable URL is available."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Stable NCPPB result URL; session-only pages may require browser export instead")
    parser.add_argument("--output-dir", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    request = urllib.request.Request(args.url, headers={"User-Agent": "ncppb-audit-v2/2.0"})
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        content = response.read()
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "")
    if b"furtherinfo.cfm?ncppb_no=" not in content:
        raise SystemExit("Downloaded page does not look like an NCPPB catalogue result page; preserve a browser-exported HTML snapshot instead.")
    digest = hashlib.sha256(content).hexdigest()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    html_path = args.output_dir / f"ncppb_catalogue_{timestamp}_{digest[:12]}.html"
    html_path.write_bytes(content)
    manifest = {
        "requested_url": args.url,
        "final_url": final_url,
        "downloaded_at_utc": timestamp,
        "content_type": content_type,
        "sha256": digest,
        "bytes": len(content),
        "html_file": html_path.name,
    }
    manifest_path = html_path.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(html_path)
    print(manifest_path)


if __name__ == "__main__":
    main()
