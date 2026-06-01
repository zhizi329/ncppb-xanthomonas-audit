#!/usr/bin/env python3
"""Build an 898-strain BioSample search-result review table.

This is a no-network consolidation step. It answers the immediate "has / has
not / needs review" question for every NCPPB strain using the current BioSample
matches, review rows, identifier candidates, and raw-candidate audit output.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


OUTPUT_COLUMNS = [
    "ncppb_number",
    "current_name",
    "name_as_received",
    "other_references",
    "other_collection_numbers",
    "identifier_candidates",
    "current_search_identifiers",
    "high_confidence_identifiers",
    "manual_only_identifiers",
    "has_confirmed_biosample",
    "accepted_biosample_count",
    "accepted_biosample_accessions",
    "accepted_biosample_organisms",
    "accepted_biosample_titles",
    "matched_identifiers",
    "matched_identifier_types",
    "review_candidate_count",
    "non_xanthomonas_review_rows",
    "no_hit_rows",
    "conflict_rows",
    "conflicting_accessions",
    "taxon_only_rows",
    "taxon_only_accessions",
    "rescue_candidate_count",
    "rescue_candidate_accessions",
    "accepted_needs_review_count",
    "accepted_needs_review_accessions",
    "top_reject_reasons",
    "search_result_review_status",
    "review_priority",
    "review_note",
]

MANUAL_RULES = {
    "source_context_single_letter_code",
    "single_letter_code",
    "source_context_number_label",
    "person_or_local_reference_code",
    "general_code_candidate",
    "stopword_prefix",
}


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


def ncppb_sort_value(ncppb_number: str) -> int:
    match = re.search(r"\d+", ncppb_number or "")
    return int(match.group(0)) if match else 0


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def join_unique(values: Iterable[str], limit: int = 0) -> str:
    selected = unique(values)
    if limit > 0:
        selected = selected[:limit]
    return "; ".join(selected)


def truthy(value: bool) -> str:
    return "yes" if value else "no"


def group_by_strain(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        ncppb = clean_text(row.get("ncppb_number", ""))
        if ncppb:
            grouped[ncppb].append(row)
    return grouped


def identifier_groups(identifier_rows: list[dict[str, str]]) -> dict[str, dict[str, list[str]]]:
    grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in identifier_rows:
        ncppb = clean_text(row.get("ncppb_number", ""))
        identifier = clean_text(row.get("normalized_identifier", ""))
        rule_name = clean_text(row.get("rule_name", ""))
        if not ncppb:
            continue
        if not identifier or rule_name == "no_identifier_found":
            grouped[ncppb]["no_identifier_found"].append("no_identifier_found")
            continue
        grouped[ncppb]["identifier_candidates"].append(identifier)
        if clean_text(row.get("include_for_search", "")).lower() == "yes":
            grouped[ncppb]["current_search_identifiers"].append(identifier)
        if row.get("confidence", "") == "high" or rule_name == "known_collection_prefix":
            grouped[ncppb]["high_confidence_identifiers"].append(identifier)
        if (
            clean_text(row.get("include_for_search", "")).lower() != "yes"
            or row.get("confidence", "") in {"low", "reject", "none"}
            or rule_name in MANUAL_RULES
        ):
            grouped[ncppb]["manual_only_identifiers"].append(identifier)
    return grouped


def reject_reason_counts(rows: list[dict[str, str]]) -> str:
    counts = Counter(clean_text(row.get("reject_reason", "")) or "<blank>" for row in rows)
    return "; ".join(f"{reason}:{count}" for reason, count in counts.most_common(6))


def is_conflict(row: dict[str, str]) -> bool:
    return clean_text(row.get("reject_reason", "")).startswith("conflicting_ncppb_number")


def is_taxon_only(row: dict[str, str]) -> bool:
    return (
        clean_text(row.get("evidence_level", "")) == "taxon_level_only"
        or clean_text(row.get("reject_reason", "")) == "no_exact_strain_identifier_match"
    )


def is_no_hit(row: dict[str, str]) -> bool:
    return (
        clean_text(row.get("status", "")) == "no_hit"
        or clean_text(row.get("reject_reason", "")) == "query_returned_no_biosample_records"
    )


def accepted_rows_needing_review(raw_audit_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    flagged: list[dict[str, str]] = []
    for row in raw_audit_rows:
        if clean_text(row.get("prior_classification", "")) != "accepted":
            continue
        if clean_text(row.get("raw_audit_decision", "")) == "supports_accept" and not clean_text(
            row.get("conflicting_ncppb_numbers", "")
        ):
            continue
        flagged.append(row)
    return flagged


def review_status(
    accepted_count: int,
    conflict_count: int,
    taxon_only_count: int,
    rescue_count: int,
    accepted_needs_review_count: int,
) -> tuple[str, str, str]:
    if accepted_needs_review_count > 0:
        return (
            "manual_review_required",
            "P1_conflicting_accepted_match",
            "At least one currently accepted BioSample has a conflict or audit warning.",
        )
    if conflict_count > 0:
        return (
            "manual_review_required",
            "P2_conflicting_identifier_review",
            "Rejected/review candidates include conflicting NCPPB numbers.",
        )
    if taxon_only_count > 0:
        return (
            "manual_review_required",
            "P3_taxon_only_review",
            "Target-taxon BioSample candidates exist but no exact strain identifier was found.",
        )
    if rescue_count > 0:
        return (
            "manual_review_required",
            "P4_false_negative_rescue_review",
            "Raw audit found target-taxon query-only or low-confidence rescue candidates.",
        )
    if accepted_count > 0:
        return (
            "confirmed_biosample_match",
            "confirmed_current_algorithmic_match",
            "At least one accepted BioSample match and no current high-priority review flag.",
        )
    return (
        "no_confirmed_match_yet",
        "no_confirmed_biosample_match",
        "No accepted BioSample match in the current local-evidence filter output.",
    )


def build_review_table(
    master_rows: list[dict[str, str]],
    identifier_rows: list[dict[str, str]],
    match_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    raw_audit_rows: list[dict[str, str]] | None = None,
    rescue_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    identifiers = identifier_groups(identifier_rows)
    matches_by_strain = group_by_strain(match_rows)
    review_by_strain = group_by_strain(review_rows)
    audit_by_strain = group_by_strain(raw_audit_rows or [])
    rescue_by_strain = group_by_strain(rescue_rows or [])

    output_rows: list[dict[str, Any]] = []
    for master in sorted(master_rows, key=lambda row: ncppb_sort_value(row.get("ncppb_number", ""))):
        ncppb = clean_text(master.get("ncppb_number", ""))
        if not ncppb:
            continue
        matches = matches_by_strain.get(ncppb, [])
        review = review_by_strain.get(ncppb, [])
        audit = audit_by_strain.get(ncppb, [])
        rescue = rescue_by_strain.get(ncppb, [])
        accepted_needs_review = accepted_rows_needing_review(audit)
        conflict_rows = [row for row in review if is_conflict(row)]
        taxon_only_rows = [row for row in review if is_taxon_only(row)]
        no_hit_rows = [row for row in review if is_no_hit(row)]
        non_xanthomonas_rows = [
            row
            for row in review
            if clean_text(row.get("reject_reason", "")) in {"non_xanthomonas_organism", "weak_identifier_match_non_xanthomonas_organism"}
        ]
        status, priority, note = review_status(
            accepted_count=len(matches),
            conflict_count=len(conflict_rows),
            taxon_only_count=len(taxon_only_rows),
            rescue_count=len(rescue),
            accepted_needs_review_count=len(accepted_needs_review),
        )
        id_group = identifiers.get(ncppb, {})

        output_rows.append(
            {
                "ncppb_number": ncppb,
                "current_name": clean_text(master.get("current_name", "")),
                "name_as_received": clean_text(master.get("name_as_received", "")),
                "other_references": clean_text(master.get("other_references", "")),
                "other_collection_numbers": clean_text(master.get("other_collection_numbers", "")),
                "identifier_candidates": join_unique(id_group.get("identifier_candidates", [])),
                "current_search_identifiers": join_unique(id_group.get("current_search_identifiers", [])),
                "high_confidence_identifiers": join_unique(id_group.get("high_confidence_identifiers", [])),
                "manual_only_identifiers": join_unique(id_group.get("manual_only_identifiers", [])),
                "has_confirmed_biosample": truthy(bool(matches)),
                "accepted_biosample_count": len(matches),
                "accepted_biosample_accessions": join_unique([row.get("ncbi_accession", "") for row in matches]),
                "accepted_biosample_organisms": join_unique([row.get("organism", "") for row in matches], limit=8),
                "accepted_biosample_titles": join_unique([row.get("title", "") for row in matches], limit=8),
                "matched_identifiers": join_unique([row.get("matched_identifier", "") for row in matches]),
                "matched_identifier_types": join_unique([row.get("matched_identifier_type", "") for row in matches]),
                "review_candidate_count": len(review),
                "non_xanthomonas_review_rows": len(non_xanthomonas_rows),
                "no_hit_rows": len(no_hit_rows),
                "conflict_rows": len(conflict_rows),
                "conflicting_accessions": join_unique([row.get("ncbi_accession", "") for row in conflict_rows]),
                "taxon_only_rows": len(taxon_only_rows),
                "taxon_only_accessions": join_unique([row.get("ncbi_accession", "") for row in taxon_only_rows]),
                "rescue_candidate_count": len(rescue),
                "rescue_candidate_accessions": join_unique([row.get("ncbi_accession", "") for row in rescue]),
                "accepted_needs_review_count": len(accepted_needs_review),
                "accepted_needs_review_accessions": join_unique([row.get("ncbi_accession", "") for row in accepted_needs_review]),
                "top_reject_reasons": reject_reason_counts(review),
                "search_result_review_status": status,
                "review_priority": priority,
                "review_note": note,
            }
        )
    return output_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", required=True, help="NCPPB master table CSV/TSV")
    parser.add_argument("--identifiers", required=True, help="Other references identifier candidate CSV/TSV")
    parser.add_argument("--matches", required=True, help="Accepted BioSample matches CSV/TSV")
    parser.add_argument("--review", required=True, help="BioSample review/rejected rows CSV/TSV")
    parser.add_argument("--output", required=True, help="898-strain search result review CSV/TSV")
    parser.add_argument("--raw-audit", default="", help="Optional raw candidate audit CSV/TSV")
    parser.add_argument("--rescue-candidates", default="", help="Optional false-negative rescue candidate CSV/TSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    master_path = Path(args.master)
    identifiers_path = Path(args.identifiers)
    matches_path = Path(args.matches)
    review_path = Path(args.review)
    for path in [master_path, identifiers_path, matches_path, review_path]:
        if not path.exists():
            raise SystemExit(f"Input not found: {path}")

    raw_audit = read_table(Path(args.raw_audit)) if args.raw_audit else []
    rescue = read_table(Path(args.rescue_candidates)) if args.rescue_candidates else []
    rows = build_review_table(
        master_rows=read_table(master_path),
        identifier_rows=read_table(identifiers_path),
        match_rows=read_table(matches_path),
        review_rows=read_table(review_path),
        raw_audit_rows=raw_audit,
        rescue_rows=rescue,
    )
    write_table(Path(args.output), rows)
    counts = Counter(row["search_result_review_status"] for row in rows)
    print(f"Wrote {len(rows)} strain review rows to {args.output}")
    print(f"Review status counts: {dict(counts)}")


if __name__ == "__main__":
    main()
