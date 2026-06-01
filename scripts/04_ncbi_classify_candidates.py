#!/usr/bin/env python3
"""Classify harvested NCBI metadata candidates for NCPPB strains.

This script is the local filtering step. It reads the raw candidate TSV written
by 03_ncbi_harvest_candidates.py and produces accepted matches plus review
candidates without making any NCBI network requests.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


def load_core() -> Any:
    script_path = Path(__file__).resolve().with_name("03_ncbi_smoke_test.py")
    spec = importlib.util.spec_from_file_location("ncbi_smoke_test_core", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load core script from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


core = load_core()


def linked_biosample_accession(row: dict[str, str]) -> str:
    biosample = core.compact_spaces(row.get("biosample_accession", ""))
    if biosample:
        return biosample
    if row.get("ncbi_db", "") == "biosample":
        return core.compact_spaces(row.get("ncbi_accession", ""))
    return ""


def can_promote_linked_row(row: dict[str, Any]) -> bool:
    if row.get("status") != "ok" or core.is_match_row(row):
        return False
    reject_reason = row.get("reject_reason", "")
    if reject_reason == "non_xanthomonas_organism":
        return False
    if reject_reason.startswith("conflicting_ncppb_number"):
        return False
    return bool(linked_biosample_accession(row))


def promote_rows_linked_to_accepted_biosamples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted_by_biosample: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not core.is_match_row(row):
            continue
        biosample = linked_biosample_accession(row)
        if not biosample:
            continue
        accepted_by_biosample.setdefault((row.get("ncppb_number", ""), biosample), row)

    promoted_rows: list[dict[str, Any]] = []
    for row in rows:
        if not can_promote_linked_row(row):
            promoted_rows.append(row)
            continue

        biosample = linked_biosample_accession(row)
        parent = accepted_by_biosample.get((row.get("ncppb_number", ""), biosample))
        if parent is None:
            promoted_rows.append(row)
            continue

        updated = dict(row)
        updated.update(
            {
                "evidence_level": "strong_strain_match",
                "matched_identifier": parent.get("matched_identifier", ""),
                "matched_identifier_type": "linked_accepted_biosample",
                "reject_reason": "",
                "linked_from_db": parent.get("ncbi_db", ""),
                "linked_from_accession": parent.get("ncbi_accession", ""),
                "evidence_text": core.limit_text(
                    f"Linked to accepted {parent.get('ncbi_db', '')} "
                    f"{parent.get('ncbi_accession', '')} through BioSample {biosample}. "
                    f"{row.get('evidence_text', '')}"
                ),
            }
        )
        promoted_rows.append(updated)
    return promoted_rows


def classify_raw_row(context: Any, raw_row: dict[str, str]) -> dict[str, Any]:
    row = {
        "ncppb_number": context.ncppb_number,
        "ncbi_db": raw_row.get("ncbi_db", ""),
        "ncbi_uid": raw_row.get("ncbi_uid", ""),
        "ncbi_accession": raw_row.get("ncbi_accession", ""),
        "source_url": raw_row.get("source_url", ""),
        "data_type": raw_row.get("data_type", ""),
        "evidence_text": raw_row.get("evidence_text", ""),
        "organism": raw_row.get("organism", ""),
        "taxid": raw_row.get("taxid", ""),
        "title": raw_row.get("title", ""),
        "biosample_accession": raw_row.get("biosample_accession", ""),
        "assembly_level": raw_row.get("assembly_level", ""),
        "sra_library_strategy": raw_row.get("sra_library_strategy", ""),
        "linked_from_db": raw_row.get("linked_from_db", ""),
        "linked_from_accession": raw_row.get("linked_from_accession", ""),
        "status": raw_row.get("status", ""),
        "error": raw_row.get("error", ""),
    }

    if raw_row.get("status") != "ok":
        row.update(
            {
                "evidence_level": "ambiguous",
                "matched_identifier": "",
                "matched_identifier_type": "",
                "reject_reason": "query_error",
            }
        )
        return row

    classification = core.classify_candidate(context, raw_row)
    row.update(
        {
            "evidence_level": classification.evidence_level,
            "matched_identifier": classification.matched_identifier,
            "matched_identifier_type": classification.matched_identifier_type,
            "reject_reason": classification.reject_reason,
        }
    )
    return row


def selected_strains(raw_rows: list[dict[str, str]], strain_order: str, limit: int) -> list[str]:
    if strain_order:
        order_rows = core.read_table(Path(strain_order))
        limit_value = limit if limit > 0 else len(order_rows)
        return core.first_unique([row.get("ncppb_number", "") for row in order_rows], limit_value)
    return core.first_unique([row.get("ncppb_number", "") for row in raw_rows], len(raw_rows))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-input", required=True, help="Raw candidate TSV/CSV from harvest script")
    parser.add_argument("--master", required=True, help="NCPPB master CSV")
    parser.add_argument("--matches-output", required=True, help="Accepted strain-level matches TSV/CSV")
    parser.add_argument("--review-output", required=True, help="Rejected or review candidate TSV/CSV")
    parser.add_argument("--strain-order", default="", help="Optional search_terms TSV/CSV used to add no-match summaries")
    parser.add_argument("--limit-strains", type=int, default=0, help="Number of ordered strains to summarize")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_rows = core.read_table(Path(args.raw_input))
    selected = selected_strains(raw_rows, args.strain_order, args.limit_strains)
    selected_set = set(selected)

    master = core.read_table(Path(args.master))
    needed = selected_set or {row.get("ncppb_number", "") for row in raw_rows}
    master_rows = {row["ncppb_number"]: row for row in master if row.get("ncppb_number", "") in needed}

    classified_rows: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        ncppb = raw_row.get("ncppb_number", "")
        if selected_set and ncppb not in selected_set:
            continue
        context = core.make_strain_context(master_rows.get(ncppb, {"ncppb_number": ncppb}))
        classified_rows.append(classify_raw_row(context, raw_row))

    classified_rows = promote_rows_linked_to_accepted_biosamples(classified_rows)
    matches, review = core.split_match_review_rows(classified_rows)
    matched_strains = {row.get("ncppb_number", "") for row in matches}
    for ncppb in selected:
        if ncppb in matched_strains:
            continue
        review.append(
            {
                "ncppb_number": ncppb,
                "evidence_level": "no_public_data_found",
                "reject_reason": "no_accepted_strain_level_match",
                "status": "ok",
                "error": "",
            }
        )

    columns = core.output_columns()
    core.write_table(Path(args.matches_output), matches, columns)
    core.write_table(Path(args.review_output), review, columns)
    print(f"Wrote {len(matches)} accepted matches to {args.matches_output}; {len(review)} review rows to {args.review_output}")


if __name__ == "__main__":
    main()
