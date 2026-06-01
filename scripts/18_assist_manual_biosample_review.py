#!/usr/bin/env python3
"""Create an assisted manual-review table for BioSample "has/has-not" calls.

This script does not change accepted/rejected source tables. It narrows the
manual-review queue into curator-facing decisions using the 898-strain review
table and the raw-candidate audit.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


OUTPUT_COLUMNS = [
    "ncppb_number",
    "current_name",
    "has_confirmed_biosample",
    "current_review_status",
    "current_review_priority",
    "assistant_audit_decision",
    "recommended_has_status",
    "decision_confidence",
    "accepted_biosample_accessions",
    "accepted_to_keep",
    "accepted_to_curator_check",
    "secondary_review_accessions",
    "conflict_rows",
    "taxon_only_rows",
    "rescue_candidate_count",
    "manual_review_focus",
    "assistant_note",
]


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


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


def split_values(value: str) -> list[str]:
    return [clean_text(part) for part in value.split(";") if clean_text(part)]


def join_values(values: list[str]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)
    return "; ".join(output)


def int_value(value: str) -> int:
    try:
        return int(clean_text(value) or "0")
    except ValueError:
        return 0


def assisted_decision(row: dict[str, str]) -> dict[str, str]:
    has_confirmed = clean_text(row.get("has_confirmed_biosample", "")) == "yes"
    accepted = split_values(row.get("accepted_biosample_accessions", ""))
    accepted_to_check = split_values(row.get("accepted_needs_review_accessions", ""))
    conflict_accessions = split_values(row.get("conflicting_accessions", ""))
    taxon_only_accessions = split_values(row.get("taxon_only_accessions", ""))
    rescue_accessions = split_values(row.get("rescue_candidate_accessions", ""))
    conflict_rows = int_value(row.get("conflict_rows", ""))
    taxon_only_rows = int_value(row.get("taxon_only_rows", ""))
    rescue_count = int_value(row.get("rescue_candidate_count", ""))

    if accepted_to_check:
        return {
            "assistant_audit_decision": "curator_check_accepted_conflict",
            "recommended_has_status": "curator_review_required_before_counting",
            "decision_confidence": "high",
            "accepted_to_keep": join_values([value for value in accepted if value not in set(accepted_to_check)]),
            "accepted_to_curator_check": join_values(accepted_to_check),
            "secondary_review_accessions": join_values(conflict_accessions + taxon_only_accessions + rescue_accessions),
            "manual_review_focus": "accepted_biosample_conflict",
            "assistant_note": "At least one currently accepted BioSample is flagged by raw audit; do not count it as final confirmed until curator review.",
        }

    if has_confirmed:
        return {
            "assistant_audit_decision": "keep_confirmed_match_review_side_hits",
            "recommended_has_status": "confirmed_biosample_match",
            "decision_confidence": "medium",
            "accepted_to_keep": join_values(accepted),
            "accepted_to_curator_check": "",
            "secondary_review_accessions": join_values(conflict_accessions + taxon_only_accessions + rescue_accessions),
            "manual_review_focus": "side_hit_review_only",
            "assistant_note": "Existing accepted BioSample is not itself flagged; conflicting/taxon-only/rescue accessions are side candidates from broad retrieval and should not overturn the current has-call.",
        }

    if conflict_rows > 0:
        return {
            "assistant_audit_decision": "no_confirmed_match_reject_conflicting_candidates",
            "recommended_has_status": "no_confirmed_match_yet",
            "decision_confidence": "high",
            "accepted_to_keep": "",
            "accepted_to_curator_check": "",
            "secondary_review_accessions": join_values(conflict_accessions + rescue_accessions),
            "manual_review_focus": "conflicting_rejected_candidates",
            "assistant_note": "Only conflicting candidates are present; these point to other NCPPB numbers and should not be counted as this strain.",
        }

    if taxon_only_rows > 0 or rescue_count > 0:
        return {
            "assistant_audit_decision": "no_confirmed_match_review_taxon_or_rescue",
            "recommended_has_status": "no_confirmed_match_pending_review",
            "decision_confidence": "medium",
            "accepted_to_keep": "",
            "accepted_to_curator_check": "",
            "secondary_review_accessions": join_values(taxon_only_accessions + rescue_accessions),
            "manual_review_focus": "possible_false_negative_or_taxon_only",
            "assistant_note": "Target-taxon or rescue candidates exist but no exact strain identifier is present in current metadata.",
        }

    return {
        "assistant_audit_decision": "no_manual_issue_detected",
        "recommended_has_status": "confirmed_biosample_match" if has_confirmed else "no_confirmed_match_yet",
        "decision_confidence": "medium",
        "accepted_to_keep": join_values(accepted),
        "accepted_to_curator_check": "",
        "secondary_review_accessions": "",
        "manual_review_focus": "",
        "assistant_note": "No high-priority manual-review issue in the current review table.",
    }


def build_assisted_review_rows(review_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    manual_rows = [
        row for row in review_rows if clean_text(row.get("search_result_review_status", "")) == "manual_review_required"
    ]
    output: list[dict[str, str]] = []
    for row in manual_rows:
        decision = assisted_decision(row)
        output.append(
            {
                "ncppb_number": clean_text(row.get("ncppb_number", "")),
                "current_name": clean_text(row.get("current_name", "")),
                "has_confirmed_biosample": clean_text(row.get("has_confirmed_biosample", "")),
                "current_review_status": clean_text(row.get("search_result_review_status", "")),
                "current_review_priority": clean_text(row.get("review_priority", "")),
                "conflict_rows": clean_text(row.get("conflict_rows", "")),
                "taxon_only_rows": clean_text(row.get("taxon_only_rows", "")),
                "rescue_candidate_count": clean_text(row.get("rescue_candidate_count", "")),
                "accepted_biosample_accessions": clean_text(row.get("accepted_biosample_accessions", "")),
                **decision,
            }
        )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-table", required=True, help="898-strain search result review table")
    parser.add_argument("--output", required=True, help="Assisted manual-review TSV/CSV output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.review_table)
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")
    rows = build_assisted_review_rows(read_table(input_path))
    write_table(Path(args.output), rows)
    print(f"Wrote {len(rows)} assisted manual-review rows to {args.output}")


if __name__ == "__main__":
    main()
