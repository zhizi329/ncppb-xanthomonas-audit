#!/usr/bin/env python3
"""Compare script-extracted Other references identifiers with LLM review output."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def write_table(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def normalize_identifier(value: str) -> str:
    text = " ".join(str(value or "").upper().replace(",", " ").split())
    match = re.match(r"^([A-Z]{1,12})\s*[-:_]?\s*(\d+[A-Z0-9.-]*)$", text)
    if not match:
        return text
    return f"{match.group(1)} {match.group(2)}"


def split_identifier_list(value: str) -> set[str]:
    parts = re.split(r"[;|]\s*|\n+", value or "")
    return {normalize_identifier(part.strip()) for part in parts if part.strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True, help="LLM-filled review TSV")
    parser.add_argument("--output", required=True, help="Comparison TSV output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_table(Path(args.review))
    comparison_rows: list[dict[str, Any]] = []

    for row in rows:
        script_set = split_identifier_list(row.get("script_identifiers", ""))
        llm_set = split_identifier_list(row.get("llm_expected_identifiers", ""))
        missing = sorted(llm_set - script_set)
        extra = sorted(script_set - llm_set)
        llm_verdict = row.get("llm_verdict", "").strip()
        if not row.get("llm_expected_identifiers", "").strip() and llm_verdict == "no_identifier":
            verdict = "match" if not script_set else "mismatch"
        elif not row.get("llm_expected_identifiers", "").strip() and script_set:
            verdict = "mismatch"
        elif not row.get("llm_expected_identifiers", "").strip():
            verdict = "needs_llm_review"
        elif missing or extra:
            verdict = "mismatch"
        else:
            verdict = "match"

        comparison_rows.append(
            {
                "ncppb_number": row.get("ncppb_number", ""),
                "other_references": row.get("other_references", ""),
                "script_identifiers": "; ".join(sorted(script_set)),
                "llm_expected_identifiers": "; ".join(sorted(llm_set)),
                "missing_from_script": "; ".join(missing),
                "extra_in_script": "; ".join(extra),
                "comparison_verdict": verdict,
                "llm_notes": row.get("llm_notes", ""),
            }
        )

    write_table(
        Path(args.output),
        comparison_rows,
        [
            "ncppb_number",
            "other_references",
            "script_identifiers",
            "llm_expected_identifiers",
            "missing_from_script",
            "extra_in_script",
            "comparison_verdict",
            "llm_notes",
        ],
    )
    counts: dict[str, int] = {}
    for row in comparison_rows:
        counts[row["comparison_verdict"]] = counts.get(row["comparison_verdict"], 0) + 1
    print(f"Wrote {len(comparison_rows)} comparison rows to {args.output}")
    print(counts)


if __name__ == "__main__":
    main()
