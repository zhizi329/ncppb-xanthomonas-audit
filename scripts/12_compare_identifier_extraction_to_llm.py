#!/usr/bin/env python3
"""Compare extracted Other references identifiers with an LLM-filled audit table."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any


OUTPUT_COLUMNS = [
    "ncppb_number",
    "other_references",
    "script_included_identifiers",
    "llm_expected_identifiers",
    "missing_from_script",
    "extra_in_script",
    "comparison_verdict",
    "llm_notes",
]


def table_delimiter(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=table_delimiter(path))
        return [{key: value or "" for key, value in row.items()} for row in reader]


def write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, delimiter=table_delimiter(path))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def normalize_identifier(value: str) -> str:
    text = " ".join(str(value or "").upper().replace(",", " ").split()).strip()
    match = re.match(
        r"^([A-Z]{1,12}(?:[-/][A-Z]{1,12})*)\s*[-:_]?\s*([A-Z]*[-_/]?\d[A-Z0-9./-]*)$",
        text,
    )
    if not match:
        return text
    return f"{match.group(1)} {match.group(2)}"


def split_identifier_list(value: str) -> set[str]:
    parts = re.split(r"[;|]\s*|\n+", value or "")
    return {normalize_identifier(part.strip()) for part in parts if part.strip()}


def extracted_identifiers_by_strain(identifier_rows: list[dict[str, str]]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for row in identifier_rows:
        if row.get("include_for_search", "").strip().lower() != "yes":
            continue
        identifier = normalize_identifier(row.get("normalized_identifier", ""))
        if not identifier:
            continue
        grouped.setdefault(row.get("ncppb_number", ""), set()).add(identifier)
    return grouped


def compare_rows(review_rows: list[dict[str, str]], extracted: dict[str, set[str]]) -> list[dict[str, Any]]:
    comparison_rows: list[dict[str, Any]] = []
    for row in review_rows:
        ncppb_number = row.get("ncppb_number", "")
        script_set = extracted.get(ncppb_number, set())
        llm_set = split_identifier_list(row.get("llm_expected_identifiers", ""))
        missing = sorted(llm_set - script_set)
        extra = sorted(script_set - llm_set)
        llm_verdict = row.get("llm_verdict", "").strip()

        if not llm_set and llm_verdict == "no_identifier":
            verdict = "match" if not script_set else "mismatch"
        elif not llm_set and not script_set:
            verdict = "needs_llm_review"
        elif missing or extra:
            verdict = "mismatch"
        else:
            verdict = "match"

        comparison_rows.append(
            {
                "ncppb_number": ncppb_number,
                "other_references": row.get("other_references", ""),
                "script_included_identifiers": "; ".join(sorted(script_set)),
                "llm_expected_identifiers": "; ".join(sorted(llm_set)),
                "missing_from_script": "; ".join(missing),
                "extra_in_script": "; ".join(extra),
                "comparison_verdict": verdict,
                "llm_notes": row.get("llm_notes", ""),
            }
        )
    return comparison_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identifiers", required=True, help="Identifier candidate CSV/TSV from script 09")
    parser.add_argument("--review", required=True, help="LLM-filled review CSV/TSV")
    parser.add_argument("--output", required=True, help="Comparison CSV/TSV output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    identifier_rows = read_table(Path(args.identifiers))
    review_rows = read_table(Path(args.review))
    comparison_rows = compare_rows(review_rows, extracted_identifiers_by_strain(identifier_rows))
    write_table(Path(args.output), comparison_rows)

    counts: dict[str, int] = {}
    missing_rows = 0
    for row in comparison_rows:
        counts[row["comparison_verdict"]] = counts.get(row["comparison_verdict"], 0) + 1
        if row["missing_from_script"]:
            missing_rows += 1
    print(f"Wrote {len(comparison_rows)} comparison rows to {args.output}")
    print(f"Verdicts: {counts}")
    print(f"Rows with missing identifiers: {missing_rows}")


if __name__ == "__main__":
    main()
