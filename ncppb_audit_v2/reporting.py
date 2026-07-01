from __future__ import annotations

import json
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .common import sha256_file, stable_json


def count_values(rows: list[dict[str, str]], column: str) -> str:
    counts = Counter(row.get(column, "") or "blank" for row in rows)
    return "; ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def write_summary(
    outdir: Path,
    strains: list[dict[str, str]],
    clauses: list[dict[str, str]],
    identifiers: list[dict[str, str]],
    reviews: list[dict[str, str]],
    query_plan: list[dict[str, str]],
    snapshot_diff: list[dict[str, str]],
    match_rows: list[dict[str, str]] | None = None,
    supervisor_rows: list[dict[str, str]] | None = None,
    comparison_rows: list[dict[str, str]] | None = None,
) -> None:
    missing = [row["ncppb_number"] for row in snapshot_diff if row["snapshot_status"] == "missing_from_v2_snapshot"]
    has_v1_baseline = any(
        row.get("snapshot_status") != "current_snapshot_no_v1_baseline" for row in snapshot_diff
    )
    searchable_other = [
        row for row in identifiers
        if row.get("identifier_type") != "ncppb_number" and row.get("search_eligible") == "yes"
    ]
    lines = [
        "# NCPPB audit V2.1 run summary",
        "",
        "## Local input and parser",
        "",
        f"- Current HTML snapshot records: {len(strains)}",
        (
            f"- Records missing relative to V1: {len(missing)} ({'; '.join(missing) or 'none'})"
            if has_v1_baseline
            else "- V1 catalogue baseline: not supplied (comparison is optional)"
        ),
        f"- Other-reference clauses: {len(clauses)}",
        f"- Clause types: {count_values(clauses, 'clause_type')}",
        f"- Clause risk levels: {count_values(clauses, 'risk_level')}",
        f"- Parser review queue rows: {len(reviews)}",
        f"- Searchable Other-reference identifiers: {len(searchable_other)}",
        "",
        "## Two-track NCBI query plan",
        "",
        f"- Query rows: {len(query_plan)}",
        f"- Query tracks: {count_values(query_plan, 'query_track')}",
        f"- Query tiers: {count_values(query_plan, 'query_tier')}",
        "- The NCPPB-number track combines a broad trusted-prefix harvest with one literal full-identifier query per catalogue strain. Full forms such as `NCPPB 45`, `NCPPB45`, and `NCPPB:45` are OR-combined and never emitted as independent prefix/number `AND` terms.",
        "- Formal Other-reference collection numbers use prefix harvest plus complete local identifier validation; medium donor/isolate codes are candidate-only and cannot be auto-accepted.",
    ]
    if match_rows is not None and supervisor_rows is not None:
        changed = [row for row in (comparison_rows or []) if row.get("biosample_accessions_changed") == "yes"]
        lines.extend(
            [
                "",
                "## NCBI matching and linked records",
                "",
                f"- Candidate decisions: {len(match_rows)}",
                f"- Decisions: {count_values(match_rows, 'decision')}",
                f"- Evidence classes: {count_values(match_rows, 'evidence_class')}",
                f"- Supervisor rows: {len(supervisor_rows)}",
                f"- Sequence categories: {count_values(supervisor_rows, 'sequence_availability_category')}",
                f"- Strains with changed confirmed BioSample accessions versus V1: {len(changed)}",
            ]
        )
    (outdir / "run_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_manifest(
    outdir: Path,
    html_path: Path,
    args: dict[str, Any],
    counts: dict[str, int],
    stage_status: str,
    record_input_hash: bool = False,
) -> dict[str, Any]:
    outputs = {}
    for path in sorted(outdir.rglob("*")):
        if path.is_file() and path.name != "run_manifest.json":
            outputs[str(path.relative_to(outdir))] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
    manifest = {
        "schema_version": 1,
        "workflow_version": __version__,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stage_status": stage_status,
        "source_html": html_path.name,
        "source_html_sha256": sha256_file(html_path) if record_input_hash else "",
        "source_html_hash_recorded": record_input_hash,
        "source_html_bytes": html_path.stat().st_size,
        "counts": counts,
        "parameters": args,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "outputs": outputs,
    }
    (outdir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
