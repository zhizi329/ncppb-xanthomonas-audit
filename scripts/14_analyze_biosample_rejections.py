#!/usr/bin/env python3
"""Summarise BioSample rejection output to guide NCBI query optimisation."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REJECTION_REASON_COLUMNS = ["reject_reason", "rows", "unique_target_strains"]
PREFIX_COLUMNS = [
    "prefix",
    "review_rows",
    "accepted_rows",
    "unique_target_strains",
    "non_xanthomonas_rows",
    "no_hit_rows",
    "conflict_rows",
    "taxon_only_rows",
    "review_rows_per_accepted_row",
]
SEARCH_TERM_COLUMNS = [
    "query_profile",
    "query_source",
    "search_term",
    "rule_name",
    "confidence",
    "prefix",
    "review_rows",
    "accepted_rows",
    "unique_review_strains",
    "unique_accepted_strains",
    "non_xanthomonas_rows",
    "no_hit_rows",
    "conflict_rows",
    "taxon_only_rows",
    "retmax_saturated_rows",
    "first_ncppb_number",
    "first_organism",
    "first_title",
]
STRAIN_COLUMNS = [
    "ncppb_number",
    "review_rows",
    "accepted_rows",
    "non_xanthomonas_rows",
    "no_hit_rows",
    "conflict_rows",
    "taxon_only_rows",
    "top_reject_reason",
]
MANUAL_REVIEW_COLUMNS = [
    "priority",
    "ncppb_number",
    "ncbi_accession",
    "organism",
    "evidence_level",
    "reject_reason",
    "query_profile",
    "query_source",
    "search_term",
    "title",
    "source_url",
]


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def table_delimiter(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=table_delimiter(path))
        return [{key: value or "" for key, value in row.items()} for row in reader]


def write_table(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=table_delimiter(path))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def numeric_sort_value(ncppb_number: str) -> int:
    match = re.search(r"\d+", ncppb_number or "")
    return int(match.group(0)) if match else 0


def prefix_from_search_term(search_term: str) -> str:
    match = re.search(r"\(?\s*([A-Za-z0-9-]+)\[(?:All Fields|Text Word|Title|Attribute)", search_term or "")
    return match.group(1).upper() if match else ""


def row_prefix(row: dict[str, str]) -> str:
    return clean_text(row.get("prefix", "")).upper() or prefix_from_search_term(row.get("search_term", ""))


def identifier_lookup(identifier_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    lookup: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in identifier_rows:
        ncppb = clean_text(row.get("ncppb_number", ""))
        for key in [
            (ncppb, "normalized_identifier", clean_text(row.get("normalized_identifier", ""))),
            (ncppb, "prefix_suffix", f"{clean_text(row.get('prefix', '')).upper()}::{clean_text(row.get('suffix', '')).upper()}"),
            (ncppb, "search_term", clean_text(row.get("biosample_query", ""))),
        ]:
            if key[0] and key[2]:
                lookup[key] = row
    return lookup


def enrich_row(row: dict[str, str], lookup: dict[tuple[str, str, str], dict[str, str]]) -> dict[str, str]:
    enriched = dict(row)
    ncppb = clean_text(row.get("ncppb_number", ""))
    prefix_suffix = f"{row_prefix(row)}::{clean_text(row.get('suffix', '')).upper()}"
    candidates = [
        lookup.get((ncppb, "normalized_identifier", clean_text(row.get("normalized_identifier", "")))),
        lookup.get((ncppb, "prefix_suffix", prefix_suffix)),
        lookup.get((ncppb, "search_term", clean_text(row.get("search_term", "")))),
    ]
    meta = next((candidate for candidate in candidates if candidate), {})
    for field in ["rule_name", "confidence", "normalized_identifier", "prefix", "suffix"]:
        if not clean_text(enriched.get(field, "")) and meta:
            enriched[field] = clean_text(meta.get(field, ""))
    if not clean_text(enriched.get("prefix", "")):
        enriched["prefix"] = row_prefix(row)
    if not clean_text(enriched.get("query_profile", "")):
        enriched["query_profile"] = "current_all_fields" if "[All Fields]" in enriched.get("search_term", "") else ""
    return enriched


def is_non_xanthomonas(row: dict[str, str]) -> bool:
    return row.get("reject_reason", "") in {"non_xanthomonas_organism", "weak_identifier_match_non_xanthomonas_organism"}


def is_no_hit(row: dict[str, str]) -> bool:
    return row.get("status", "") == "no_hit" or row.get("reject_reason", "") == "query_returned_no_biosample_records"


def is_conflict(row: dict[str, str]) -> bool:
    return row.get("reject_reason", "").startswith("conflicting_ncppb_number")


def is_taxon_only(row: dict[str, str]) -> bool:
    return row.get("evidence_level", "") == "taxon_level_only" or row.get("reject_reason", "") == "no_exact_strain_identifier_match"


def saturated(row: dict[str, str]) -> bool:
    return clean_text(row.get("retmax_saturated", "")).lower() == "yes"


def rejection_reason_summary(review_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = Counter(row.get("reject_reason", "") or "<blank>" for row in review_rows)
    strains: dict[str, set[str]] = defaultdict(set)
    for row in review_rows:
        strains[row.get("reject_reason", "") or "<blank>"].add(row.get("ncppb_number", ""))
    return [
        {"reject_reason": reason, "rows": count, "unique_target_strains": len(strains[reason] - {""})}
        for reason, count in counts.most_common()
    ]


def prefix_summary(review_rows: list[dict[str, str]], match_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    prefixes = sorted({row_prefix(row) for row in [*review_rows, *match_rows] if row_prefix(row)})
    rows: list[dict[str, Any]] = []
    for prefix in prefixes:
        review = [row for row in review_rows if row_prefix(row) == prefix]
        matches = [row for row in match_rows if row_prefix(row) == prefix]
        accepted = len(matches)
        rows.append(
            {
                "prefix": prefix,
                "review_rows": len(review),
                "accepted_rows": accepted,
                "unique_target_strains": len({row.get("ncppb_number", "") for row in review + matches if row.get("ncppb_number", "")}),
                "non_xanthomonas_rows": sum(1 for row in review if is_non_xanthomonas(row)),
                "no_hit_rows": sum(1 for row in review if is_no_hit(row)),
                "conflict_rows": sum(1 for row in review if is_conflict(row)),
                "taxon_only_rows": sum(1 for row in review if is_taxon_only(row)),
                "review_rows_per_accepted_row": f"{len(review) / accepted:.2f}" if accepted else "",
            }
        )
    return sorted(rows, key=lambda row: (-int(row["review_rows"]), row["prefix"]))


def term_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        clean_text(row.get("query_profile", "")),
        clean_text(row.get("query_source", "")),
        clean_text(row.get("search_term", "")),
        clean_text(row.get("rule_name", "")),
        clean_text(row.get("confidence", "")),
        row_prefix(row),
    )


def search_term_productivity(review_rows: list[dict[str, str]], match_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped_review: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    grouped_match: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in review_rows:
        grouped_review[term_key(row)].append(row)
    for row in match_rows:
        grouped_match[term_key(row)].append(row)
    keys = set(grouped_review) | set(grouped_match)
    rows: list[dict[str, Any]] = []
    for key in keys:
        query_profile, query_source, search_term, rule_name, confidence, prefix = key
        review = grouped_review.get(key, [])
        matches = grouped_match.get(key, [])
        sample = (review or matches or [{}])[0]
        rows.append(
            {
                "query_profile": query_profile,
                "query_source": query_source,
                "search_term": search_term,
                "rule_name": rule_name,
                "confidence": confidence,
                "prefix": prefix,
                "review_rows": len(review),
                "accepted_rows": len(matches),
                "unique_review_strains": len({row.get("ncppb_number", "") for row in review if row.get("ncppb_number", "")}),
                "unique_accepted_strains": len({row.get("ncppb_number", "") for row in matches if row.get("ncppb_number", "")}),
                "non_xanthomonas_rows": sum(1 for row in review if is_non_xanthomonas(row)),
                "no_hit_rows": sum(1 for row in review if is_no_hit(row)),
                "conflict_rows": sum(1 for row in review if is_conflict(row)),
                "taxon_only_rows": sum(1 for row in review if is_taxon_only(row)),
                "retmax_saturated_rows": sum(1 for row in [*review, *matches] if saturated(row)),
                "first_ncppb_number": sample.get("ncppb_number", ""),
                "first_organism": sample.get("organism", ""),
                "first_title": sample.get("title", ""),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["review_rows"]), -int(row["accepted_rows"]), row["search_term"]))


def strain_summary(review_rows: list[dict[str, str]], match_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    review_by_strain: dict[str, list[dict[str, str]]] = defaultdict(list)
    match_counts: Counter[str] = Counter()
    for row in review_rows:
        review_by_strain[row.get("ncppb_number", "")].append(row)
    for row in match_rows:
        match_counts[row.get("ncppb_number", "")] += 1
    strains = sorted((set(review_by_strain) | set(match_counts)) - {""}, key=numeric_sort_value)
    rows: list[dict[str, Any]] = []
    for strain in strains:
        review = review_by_strain.get(strain, [])
        reason_counts = Counter(row.get("reject_reason", "") or "<blank>" for row in review)
        rows.append(
            {
                "ncppb_number": strain,
                "review_rows": len(review),
                "accepted_rows": match_counts[strain],
                "non_xanthomonas_rows": sum(1 for row in review if is_non_xanthomonas(row)),
                "no_hit_rows": sum(1 for row in review if is_no_hit(row)),
                "conflict_rows": sum(1 for row in review if is_conflict(row)),
                "taxon_only_rows": sum(1 for row in review if is_taxon_only(row)),
                "top_reject_reason": reason_counts.most_common(1)[0][0] if reason_counts else "",
            }
        )
    return rows


def manual_review_candidates(review_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in review_rows:
        priority = ""
        if is_taxon_only(row):
            priority = "P1_taxon_level_only_check"
        elif is_conflict(row):
            priority = "P2_conflicting_ncppb_number_check"
        elif row.get("evidence_level", "") == "probable_strain_match":
            priority = "P3_probable_identifier_check"
        if not priority:
            continue
        selected.append(
            {
                "priority": priority,
                "ncppb_number": row.get("ncppb_number", ""),
                "ncbi_accession": row.get("ncbi_accession", ""),
                "organism": row.get("organism", ""),
                "evidence_level": row.get("evidence_level", ""),
                "reject_reason": row.get("reject_reason", ""),
                "query_profile": row.get("query_profile", ""),
                "query_source": row.get("query_source", ""),
                "search_term": row.get("search_term", ""),
                "title": row.get("title", ""),
                "source_url": row.get("source_url", ""),
            }
        )
    return sorted(selected, key=lambda row: (row["priority"], numeric_sort_value(row["ncppb_number"]), row["ncbi_accession"]))


def enrich_rows(rows: Iterable[dict[str, str]], lookup: dict[tuple[str, str, str], dict[str, str]]) -> list[dict[str, str]]:
    return [enrich_row(row, lookup) for row in rows]


def build_analysis_tables(
    match_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    identifier_rows: list[dict[str, str]] | None = None,
) -> dict[str, tuple[list[dict[str, Any]], list[str]]]:
    lookup = identifier_lookup(identifier_rows or [])
    matches = enrich_rows(match_rows, lookup)
    review = enrich_rows(review_rows, lookup)
    return {
        "rejection_counts_by_reason.tsv": (rejection_reason_summary(review), REJECTION_REASON_COLUMNS),
        "prefix_noise_summary.tsv": (prefix_summary(review, matches), PREFIX_COLUMNS),
        "search_term_productivity.tsv": (search_term_productivity(review, matches), SEARCH_TERM_COLUMNS),
        "strain_rejection_summary.tsv": (strain_summary(review, matches), STRAIN_COLUMNS),
        "manual_review_priority_candidates.tsv": (manual_review_candidates(review), MANUAL_REVIEW_COLUMNS),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches", required=True, help="Accepted BioSample matches TSV/CSV from script 11")
    parser.add_argument("--review", required=True, help="Rejected/review BioSample rows TSV/CSV from script 11")
    parser.add_argument("--output-dir", required=True, help="Directory for analysis TSV outputs")
    parser.add_argument("--identifiers", default="", help="Optional identifier candidate TSV/CSV from script 09")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    matches_path = Path(args.matches)
    review_path = Path(args.review)
    if not matches_path.exists():
        raise SystemExit(f"Matches input not found: {matches_path}")
    if not review_path.exists():
        raise SystemExit(f"Review input not found: {review_path}")
    identifier_rows = read_table(Path(args.identifiers)) if args.identifiers else []
    tables = build_analysis_tables(read_table(matches_path), read_table(review_path), identifier_rows)
    output_dir = Path(args.output_dir)
    for filename, (rows, columns) in tables.items():
        write_table(output_dir / filename, rows, columns)
    print(f"Wrote {len(tables)} rejection analysis tables to {output_dir}")


if __name__ == "__main__":
    main()
