#!/usr/bin/env python3
"""Group accepted NCBI matches into BioSample-centred record sets.

This is the Week 3 post-processing step. It reads accepted matches and review
rows that were already classified locally, then creates:

1. one table of grouped NCBI record sets; and
2. one strain-level audit summary for the pilot strains.

The script does not query NCBI.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


ASSEMBLY_CATEGORY_PRIORITY = {
    "complete_genome_available": 5,
    "chromosome_level_assembly_available": 4,
    "draft_assembly_available": 3,
    "reads_only": 2,
    "biosample_only": 1,
    "confirmed_metadata_only": 1,
    "no_confirmed_public_data_found": 0,
}


def compact_spaces(value: object) -> str:
    return " ".join(str(value or "").split())


def table_separator(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=table_separator(path))
        return [{key: value or "" for key, value in row.items()} for row in reader]


def write_table(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=table_separator(path))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def first_unique(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    selected: list[str] = []
    for value in values:
        value = compact_spaces(value)
        if not value or value in seen:
            continue
        seen.add(value)
        selected.append(value)
        if limit > 0 and len(selected) >= limit:
            break
    return selected


def join_unique(values: list[str]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        value = compact_spaces(value)
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return "; ".join(output)


def truthy(value: bool) -> str:
    return "yes" if value else "no"


def ncppb_sort_value(ncppb_number: str) -> int:
    digits = "".join(character for character in ncppb_number if character.isdigit())
    return int(digits) if digits else 0


def select_strains(strain_order_path: Path, limit: int) -> list[str]:
    rows = read_table(strain_order_path)
    return first_unique([row.get("ncppb_number", "") for row in rows], limit)


def record_set_key(row: dict[str, str]) -> tuple[str, str]:
    """Use BioSample when available, otherwise fall back to the NCBI record."""
    biosample = compact_spaces(row.get("biosample_accession", ""))
    if biosample:
        return (compact_spaces(row.get("ncppb_number", "")), biosample)
    fallback = compact_spaces(row.get("ncbi_accession", "")) or compact_spaces(row.get("ncbi_uid", ""))
    db = compact_spaces(row.get("ncbi_db", ""))
    return (compact_spaces(row.get("ncppb_number", "")), f"{db}:{fallback}")


def assembly_category(assembly_levels: list[str], has_sra: bool, has_biosample: bool) -> str:
    levels = " ".join(assembly_levels).lower()
    if "complete genome" in levels:
        return "complete_genome_available"
    if "chromosome" in levels:
        return "chromosome_level_assembly_available"
    if "scaffold" in levels or "contig" in levels:
        return "draft_assembly_available"
    if has_sra:
        return "reads_only"
    if has_biosample:
        return "biosample_only"
    return "confirmed_metadata_only"


def better_category(left: str, right: str) -> str:
    if ASSEMBLY_CATEGORY_PRIORITY.get(right, 0) > ASSEMBLY_CATEGORY_PRIORITY.get(left, 0):
        return right
    return left


def group_matches(matches: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in matches:
        grouped.setdefault(record_set_key(row), []).append(row)

    record_sets: list[dict[str, Any]] = []
    for (ncppb_number, record_set_id), rows in sorted(
        grouped.items(), key=lambda item: (ncppb_sort_value(item[0][0]), item[0][1])
    ):
        data_types = [row.get("data_type", "") for row in rows]
        assembly_accessions = [
            row.get("ncbi_accession", "") for row in rows if row.get("ncbi_db", "") == "assembly"
        ]
        sra_accessions = [row.get("ncbi_accession", "") for row in rows if row.get("ncbi_db", "") == "sra"]
        biosample_accessions = [
            row.get("biosample_accession", "") or row.get("ncbi_accession", "")
            for row in rows
            if row.get("biosample_accession", "") or row.get("ncbi_db", "") == "biosample"
        ]
        assembly_levels = [row.get("assembly_level", "") for row in rows]
        has_biosample = bool(join_unique(biosample_accessions))
        has_sra = bool(join_unique(sra_accessions)) or any(value.startswith("SRA") for value in data_types)
        category = assembly_category(assembly_levels, has_sra=has_sra, has_biosample=has_biosample)

        record_sets.append(
            {
                "ncppb_number": ncppb_number,
                "record_set_id": record_set_id,
                "best_data_category": category,
                "record_count": len(rows),
                "organism": join_unique([row.get("organism", "") for row in rows]),
                "taxid": join_unique([row.get("taxid", "") for row in rows]),
                "matched_identifiers": join_unique([row.get("matched_identifier", "") for row in rows]),
                "matched_identifier_types": join_unique(
                    [row.get("matched_identifier_type", "") for row in rows]
                ),
                "data_types": join_unique(data_types),
                "biosample_accessions": join_unique(biosample_accessions),
                "assembly_accessions": join_unique(assembly_accessions),
                "assembly_levels": join_unique(assembly_levels),
                "sra_accessions": join_unique(sra_accessions),
                "sra_library_strategies": join_unique(
                    [row.get("sra_library_strategy", "") for row in rows]
                ),
                "source_urls": join_unique([row.get("source_url", "") for row in rows]),
            }
        )
    return record_sets


def review_counts_by_strain(review_rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in review_rows:
        ncppb = compact_spaces(row.get("ncppb_number", ""))
        if not ncppb:
            continue
        reason = row.get("reject_reason", "")
        evidence = row.get("evidence_level", "")
        strain_counts = counts.setdefault(
            ncppb,
            {
                "review_candidate_count": 0,
                "taxon_level_only_count": 0,
                "conflicting_identifier_count": 0,
                "non_xanthomonas_count": 0,
            },
        )
        if reason != "no_accepted_strain_level_match":
            strain_counts["review_candidate_count"] += 1
        if evidence == "taxon_level_only":
            strain_counts["taxon_level_only_count"] += 1
        if reason.startswith("conflicting_ncppb_number"):
            strain_counts["conflicting_identifier_count"] += 1
        if reason == "non_xanthomonas_organism":
            strain_counts["non_xanthomonas_count"] += 1
    return counts


def strain_summary(
    selected_strains: list[str],
    master_rows: dict[str, dict[str, str]],
    record_sets: list[dict[str, Any]],
    review_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    by_strain: dict[str, list[dict[str, Any]]] = {}
    for record_set in record_sets:
        by_strain.setdefault(record_set["ncppb_number"], []).append(record_set)

    review_counts = review_counts_by_strain(review_rows)
    summaries: list[dict[str, Any]] = []
    for ncppb_number in selected_strains:
        strain_sets = by_strain.get(ncppb_number, [])
        best_category = "no_confirmed_public_data_found"
        for record_set in strain_sets:
            best_category = better_category(best_category, record_set.get("best_data_category", ""))

        row = master_rows.get(ncppb_number, {})
        counts = review_counts.get(ncppb_number, {})
        summaries.append(
            {
                "ncppb_number": ncppb_number,
                "current_name": row.get("current_name", ""),
                "name_as_received": row.get("name_as_received", ""),
                "confirmed_record_sets": len(strain_sets),
                "best_audit_category": best_category,
                "has_biosample": truthy(any(record_set.get("biosample_accessions", "") for record_set in strain_sets)),
                "has_assembly": truthy(any(record_set.get("assembly_accessions", "") for record_set in strain_sets)),
                "has_sra": truthy(any(record_set.get("sra_accessions", "") for record_set in strain_sets)),
                "biosample_accessions": join_unique(
                    [record_set.get("biosample_accessions", "") for record_set in strain_sets]
                ),
                "assembly_accessions": join_unique(
                    [record_set.get("assembly_accessions", "") for record_set in strain_sets]
                ),
                "assembly_levels": join_unique(
                    [record_set.get("assembly_levels", "") for record_set in strain_sets]
                ),
                "sra_accessions": join_unique(
                    [record_set.get("sra_accessions", "") for record_set in strain_sets]
                ),
                "review_candidate_count": counts.get("review_candidate_count", 0),
                "taxon_level_only_count": counts.get("taxon_level_only_count", 0),
                "conflicting_identifier_count": counts.get("conflicting_identifier_count", 0),
                "non_xanthomonas_count": counts.get("non_xanthomonas_count", 0),
                "needs_manual_review": truthy(
                    bool(strain_sets)
                    or counts.get("taxon_level_only_count", 0) > 0
                    or counts.get("conflicting_identifier_count", 0) > 0
                ),
            }
        )
    return summaries


def record_set_columns() -> list[str]:
    return [
        "ncppb_number",
        "record_set_id",
        "best_data_category",
        "record_count",
        "organism",
        "taxid",
        "matched_identifiers",
        "matched_identifier_types",
        "data_types",
        "biosample_accessions",
        "assembly_accessions",
        "assembly_levels",
        "sra_accessions",
        "sra_library_strategies",
        "source_urls",
    ]


def strain_summary_columns() -> list[str]:
    return [
        "ncppb_number",
        "current_name",
        "name_as_received",
        "confirmed_record_sets",
        "best_audit_category",
        "has_biosample",
        "has_assembly",
        "has_sra",
        "biosample_accessions",
        "assembly_accessions",
        "assembly_levels",
        "sra_accessions",
        "review_candidate_count",
        "taxon_level_only_count",
        "conflicting_identifier_count",
        "non_xanthomonas_count",
        "needs_manual_review",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches", required=True, help="Accepted matches TSV/CSV")
    parser.add_argument("--review", required=True, help="Review candidates TSV/CSV")
    parser.add_argument("--master", required=True, help="NCPPB master CSV")
    parser.add_argument("--strain-order", required=True, help="Search terms TSV/CSV used for strain order")
    parser.add_argument("--limit-strains", type=int, default=30, help="Number of ordered strains to summarize")
    parser.add_argument("--record-sets-output", required=True, help="Grouped record sets TSV/CSV")
    parser.add_argument("--strain-summary-output", required=True, help="Strain-level summary TSV/CSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected = select_strains(Path(args.strain_order), args.limit_strains)
    selected_set = set(selected)
    matches = [
        row for row in read_table(Path(args.matches)) if not selected_set or row.get("ncppb_number", "") in selected_set
    ]
    review = [
        row for row in read_table(Path(args.review)) if not selected_set or row.get("ncppb_number", "") in selected_set
    ]
    master_rows = {
        row.get("ncppb_number", ""): row
        for row in read_table(Path(args.master))
        if not selected_set or row.get("ncppb_number", "") in selected_set
    }

    record_sets = group_matches(matches)
    summaries = strain_summary(selected, master_rows, record_sets, review)
    write_table(Path(args.record_sets_output), record_sets, record_set_columns())
    write_table(Path(args.strain_summary_output), summaries, strain_summary_columns())
    confirmed = sum(1 for row in summaries if row["confirmed_record_sets"] > 0)
    print(
        f"Wrote {len(record_sets)} record sets to {args.record_sets_output}; "
        f"{confirmed}/{len(summaries)} strains have accepted record sets"
    )


if __name__ == "__main__":
    main()
