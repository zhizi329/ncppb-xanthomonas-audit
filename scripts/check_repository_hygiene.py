#!/usr/bin/env python3
"""Fail when repository layout or tracked-file policy is violated."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPRECATED_TOP_LEVEL = (
    "results", "outputs", "tmp", "archive", "deliverables", "local_data", "scratch"
)
LOCAL_ONLY_TOP_LEVEL = ("private_inputs", ".cache")
FORBIDDEN_TRACKED_SUFFIXES = (
    ".fastq",
    ".fastq.gz",
    ".fq",
    ".fq.gz",
    ".sra",
    ".sam",
    ".bam",
    ".bai",
    ".cram",
    ".crai",
)
MAX_TRACKED_BYTES = 20 * 1024 * 1024


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    )
    return [Path(item.decode("utf-8")) for item in output.split(b"\0") if item]


def main() -> None:
    errors: list[str] = []

    for name in DEPRECATED_TOP_LEVEL:
        if (ROOT / name).exists():
            errors.append(f"deprecated top-level directory exists: {name}/")

    for relative in tracked_files():
        text = relative.as_posix()
        if relative.parts and relative.parts[0] in LOCAL_ONLY_TOP_LEVEL:
            errors.append(f"local-only path is tracked: {text}")
        if text.endswith(FORBIDDEN_TRACKED_SUFFIXES):
            errors.append(f"sequence payload is tracked: {text}")
        path = ROOT / relative
        if path.is_file() and path.stat().st_size > MAX_TRACKED_BYTES:
            errors.append(
                f"tracked file exceeds {MAX_TRACKED_BYTES // (1024 * 1024)} MiB: "
                f"{text} ({path.stat().st_size} bytes)"
            )

    current_run = ROOT / "runs/audit/2026-07-10_v2.1.1"
    for name in (
        "README.md",
        "run_manifest.json",
        "run_summary.md",
        "supervisor_sequence_availability.tsv",
        "phylogeny_input_manifest.tsv",
        "manual_review_queue.tsv",
    ):
        if not (current_run / name).exists():
            errors.append(f"current audit run is missing: {name}")

    if errors:
        raise SystemExit("Repository hygiene failed:\n- " + "\n- ".join(errors))

    print("Repository hygiene passed.")
    print(f"Tracked-file size limit: {MAX_TRACKED_BYTES // (1024 * 1024)} MiB")
    print("Large biological payloads: local-only")


if __name__ == "__main__":
    main()
