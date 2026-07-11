#!/usr/bin/env python3
"""Resume and verify ENA FASTQ downloads for the three-species smoke test."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "runs/phylogeny/2026-07-10_three-species-snp-smoke-summary/selected_runs.tsv"
DEFAULT_DATA_ROOT = Path(
    os.environ.get("XANTHOMONAS_DATA_ROOT", ROOT.parent / "xanthomonas-data")
).expanduser()
DEFAULT_OUTDIR = DEFAULT_DATA_ROOT / "phylogeny/three_species_snp_smoke/fastq_raw"


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recover_one(task: dict[str, str]) -> dict[str, str]:
    path = Path(task["path"])
    expected_md5 = task["md5"]
    expected_bytes = int(task["bytes"])
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.stat().st_size == expected_bytes and md5_file(path) == expected_md5:
        return {**task, "status": "already_verified", "message": ""}

    if path.exists() and path.stat().st_size > expected_bytes:
        path.unlink()

    command = [
        "curl", "--fail", "--location", "--continue-at", "-",
        "--retry", "12", "--retry-all-errors", "--retry-delay", "5",
        "--connect-timeout", "30", "--speed-time", "180", "--speed-limit", "1024",
        "--output", str(path), task["url"],
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        return {**task, "status": "download_failed", "message": completed.stderr[-1000:]}
    if path.stat().st_size != expected_bytes:
        return {
            **task,
            "status": "size_mismatch",
            "message": f"expected={expected_bytes}; actual={path.stat().st_size}",
        }
    actual_md5 = md5_file(path)
    if actual_md5 != expected_md5:
        path.unlink(missing_ok=True)
        return {
            **task,
            "status": "md5_mismatch_removed",
            "message": f"expected={expected_md5}; actual={actual_md5}",
        }
    return {**task, "status": "verified", "message": ""}


def write_status(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ["species", "ncppb", "run_accession", "tree_label", "mate", "path", "bytes", "md5", "url", "status", "message"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()

    with args.manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    tasks: list[dict[str, str]] = []
    for row in rows:
        for mate in ("1", "2"):
            tasks.append(
                {
                    "species": row["species"],
                    "ncppb": row["ncppb"],
                    "run_accession": row["run_accession"],
                    "tree_label": row["tree_label"],
                    "mate": mate,
                    "path": str(args.outdir / f"{row['tree_label']}_{mate}.fastq.gz"),
                    "bytes": row[f"fastq_bytes_{mate}"],
                    "md5": row[f"fastq_md5_{mate}"],
                    "url": row[f"fastq_url_{mate}"],
                }
            )

    results: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = {executor.submit(recover_one, task): task for task in tasks}
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            print(f"[{index}/{len(tasks)}] {result['status']}: {result['run_accession']} R{result['mate']}", flush=True)
            write_status(args.outdir.parent / "fastq_recovery_status.tsv", sorted(results, key=lambda item: (item["tree_label"], item["mate"])))

    failed = [row for row in results if row["status"] not in {"verified", "already_verified"}]
    if failed:
        raise SystemExit(f"FASTQ recovery incomplete: {len(failed)} failed files")
    print(f"FASTQ recovery complete: {len(results)} files verified")


if __name__ == "__main__":
    main()
