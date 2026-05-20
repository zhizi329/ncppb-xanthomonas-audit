#!/usr/bin/env python3
"""Filter raw BioSample rows against exact strain identifier patterns."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OUTPUT_COLUMNS = [
    "ncppb_number",
    "ncbi_db",
    "ncbi_uid",
    "ncbi_accession",
    "source_url",
    "title",
    "organism",
    "taxid",
    "evidence_level",
    "evidence_decision",
    "evidence_class",
    "evidence_score",
    "matched_identifier",
    "matched_identifier_type",
    "identifier_rule_name",
    "identifier_confidence",
    "reject_reason",
    "query_source",
    "search_term",
    "metadata_text",
    "status",
    "error",
]

XANTHOMONAS_RE = re.compile(r"\bXanthomonas\b", re.IGNORECASE)
NCPPB_NUMBER_RE = re.compile(
    r"\bNCPPB(?:\s*(?:No\.?|Number|#|:|-|_))?\s*0*(\d{1,5})(?!\d)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IdentifierPattern:
    value: str
    identifier_type: str
    pattern: re.Pattern[str]
    rule_name: str
    confidence: str


@dataclass(frozen=True)
class Evidence:
    evidence_level: str
    evidence_decision: str
    evidence_class: str
    evidence_score: int
    matched_identifier: str = ""
    matched_identifier_type: str = ""
    identifier_rule_name: str = ""
    identifier_confidence: str = ""
    reject_reason: str = ""


CONFIDENCE_SCORES = {
    "high": 90,
    "medium": 60,
    "low": 40,
    "none": 0,
    "reject": 0,
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


def ncppb_digits(value: str) -> str:
    match = re.search(r"\d+", value or "")
    return match.group(0) if match else ""


def ncppb_pattern(ncppb_number: str) -> IdentifierPattern | None:
    digits = ncppb_digits(ncppb_number)
    if not digits:
        return None
    pattern = re.compile(
        rf"\bNCPPB(?:\s*(?:No\.?|Number|#|:|-|_))?\s*0*{re.escape(digits)}(?!\d)",
        re.IGNORECASE,
    )
    return IdentifierPattern(f"NCPPB {digits}", "ncppb_number", pattern, "ncppb_number", "high")


def identifier_pattern(row: dict[str, str]) -> IdentifierPattern | None:
    value = row.get("normalized_identifier", "")
    text = clean_text(value).upper()
    match = re.match(r"^([A-Z]{1,12}(?:[-/][A-Z]{1,12})*)\s+(.+)$", text)
    if not match:
        return None
    prefix, suffix = match.groups()
    prefix_parts = [part for part in re.split(r"[^A-Z0-9]+", prefix) if part]
    suffix_parts = [part for part in re.split(r"[^A-Z0-9]+", suffix) if part]
    if not prefix_parts or not suffix_parts:
        return None
    prefix_pattern = r"\s*[:_./-]?\s*".join(re.escape(part) for part in prefix_parts)
    suffix_pattern = r"\s*[:_./-]?\s*".join(re.escape(part) for part in suffix_parts)
    pattern = re.compile(
        rf"(?<![A-Za-z0-9]){prefix_pattern}\s*[:_./-]?\s*{suffix_pattern}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    return IdentifierPattern(
        text,
        "other_reference_identifier",
        pattern,
        clean_text(row.get("rule_name", "")),
        clean_text(row.get("confidence", "")),
    )


def build_patterns(identifier_rows: list[dict[str, str]], include_ncppb_number: bool) -> dict[str, list[IdentifierPattern]]:
    patterns: dict[str, list[IdentifierPattern]] = {}
    seen: set[tuple[str, str]] = set()

    if include_ncppb_number:
        for row in identifier_rows:
            ncppb_number = clean_text(row.get("ncppb_number", ""))
            pattern = ncppb_pattern(ncppb_number)
            if pattern is None:
                continue
            key = (ncppb_number, pattern.value)
            if key in seen:
                continue
            seen.add(key)
            patterns.setdefault(ncppb_number, []).append(pattern)

    for row in identifier_rows:
        if clean_text(row.get("include_for_search", "")).lower() != "yes":
            continue
        ncppb_number = clean_text(row.get("ncppb_number", ""))
        pattern = identifier_pattern(row)
        if not ncppb_number or pattern is None:
            continue
        key = (ncppb_number, pattern.value)
        if key in seen:
            continue
        seen.add(key)
        patterns.setdefault(ncppb_number, []).append(pattern)

    return patterns


def find_ncppb_numbers(text: str) -> set[str]:
    return {match.group(1).lstrip("0") or "0" for match in NCPPB_NUMBER_RE.finditer(text or "")}


def row_metadata_text(row: dict[str, str]) -> str:
    metadata_text = clean_text(row.get("metadata_text", ""))
    if metadata_text:
        return metadata_text
    return clean_text(
        " ".join(
            [
                row.get("title", ""),
                row.get("organism", ""),
                row.get("identifiers", ""),
                row.get("infraspecies", ""),
                row.get("attributes", ""),
            ]
        )
    )


def identifier_score(identifier: IdentifierPattern) -> int:
    if identifier.identifier_type == "ncppb_number":
        return 100
    if identifier.rule_name == "known_collection_prefix":
        return 90
    return CONFIDENCE_SCORES.get(identifier.confidence, 30)


def best_matching_identifier(patterns: list[IdentifierPattern], metadata_text: str) -> IdentifierPattern | None:
    matches = [identifier for identifier in patterns if identifier.pattern.search(metadata_text)]
    if not matches:
        return None
    return sorted(matches, key=identifier_score, reverse=True)[0]


def evidence_for_identifier(identifier: IdentifierPattern) -> Evidence:
    score = identifier_score(identifier)
    if identifier.identifier_type == "ncppb_number":
        return Evidence(
            evidence_level="strong_strain_match",
            evidence_decision="accept",
            evidence_class="confirmed_ncppb_identifier",
            evidence_score=score,
            matched_identifier=identifier.value,
            matched_identifier_type=identifier.identifier_type,
            identifier_rule_name=identifier.rule_name,
            identifier_confidence=identifier.confidence,
        )
    if identifier.rule_name == "known_collection_prefix":
        return Evidence(
            evidence_level="strong_strain_match",
            evidence_decision="accept",
            evidence_class="confirmed_equivalent_collection_identifier",
            evidence_score=score,
            matched_identifier=identifier.value,
            matched_identifier_type=identifier.identifier_type,
            identifier_rule_name=identifier.rule_name,
            identifier_confidence=identifier.confidence,
        )
    return Evidence(
        evidence_level="probable_strain_match",
        evidence_decision="review",
        evidence_class="review_local_or_donor_identifier_only",
        evidence_score=score,
        matched_identifier=identifier.value,
        matched_identifier_type=identifier.identifier_type,
        identifier_rule_name=identifier.rule_name,
        identifier_confidence=identifier.confidence,
        reject_reason="local_or_donor_identifier_requires_manual_review",
    )


def is_strong_identifier(identifier: IdentifierPattern) -> bool:
    return identifier.identifier_type == "ncppb_number" or identifier.rule_name == "known_collection_prefix"


def evidence_with_identifier_context(
    base: Evidence,
    identifier: IdentifierPattern | None,
    evidence_class: str,
    reject_reason: str,
    decision: str = "review",
) -> Evidence:
    return Evidence(
        evidence_level=base.evidence_level,
        evidence_decision=decision,
        evidence_class=evidence_class,
        evidence_score=identifier_score(identifier) if identifier else base.evidence_score,
        matched_identifier=identifier.value if identifier else base.matched_identifier,
        matched_identifier_type=identifier.identifier_type if identifier else base.matched_identifier_type,
        identifier_rule_name=identifier.rule_name if identifier else base.identifier_rule_name,
        identifier_confidence=identifier.confidence if identifier else base.identifier_confidence,
        reject_reason=reject_reason,
    )


def classify_row(row: dict[str, str], patterns: list[IdentifierPattern]) -> Evidence:
    status = clean_text(row.get("status", ""))
    if status == "no_hit":
        return Evidence(
            "no_public_data_found",
            "no_data",
            "no_biosample_candidate",
            0,
            reject_reason="query_returned_no_biosample_records",
        )
    if status != "ok":
        return Evidence("ambiguous", "review", "review_query_error", 0, reject_reason="query_error")

    organism = clean_text(row.get("organism", ""))
    metadata_text = row_metadata_text(row)
    ncppb_number = clean_text(row.get("ncppb_number", ""))
    expected_digits = ncppb_digits(ncppb_number)
    conflicts = sorted(find_ncppb_numbers(metadata_text) - {expected_digits})
    best_identifier = best_matching_identifier(patterns, metadata_text)

    if conflicts:
        return evidence_with_identifier_context(
            Evidence("ambiguous", "reject", "reject_conflicting_identifier", 0),
            best_identifier,
            "reject_conflicting_identifier",
            f"conflicting_ncppb_number:{';'.join(conflicts)}",
            decision="reject",
        )

    if organism and not XANTHOMONAS_RE.search(organism):
        if best_identifier is not None:
            if is_strong_identifier(best_identifier):
                return evidence_with_identifier_context(
                    Evidence("probable_strain_match", "review", "review_strong_identifier_non_target_organism", 0),
                    best_identifier,
                    "review_strong_identifier_non_target_organism",
                    "strong_identifier_match_non_xanthomonas_organism",
                )
            return evidence_with_identifier_context(
                Evidence("ambiguous", "reject", "reject_weak_identifier_non_target_organism", 0),
                best_identifier,
                "reject_weak_identifier_non_target_organism",
                "weak_identifier_match_non_xanthomonas_organism",
                decision="reject",
            )
        return Evidence(
            "ambiguous",
            "reject",
            "reject_non_target_taxon",
            0,
            reject_reason="non_xanthomonas_organism",
        )

    if best_identifier is not None:
        return evidence_for_identifier(best_identifier)

    if organism and XANTHOMONAS_RE.search(organism):
        return Evidence(
            "taxon_level_only",
            "review",
            "review_taxon_only",
            20,
            reject_reason="no_exact_strain_identifier_match",
        )
    return Evidence(
        "ambiguous",
        "review",
        "review_no_organism_or_strain_identifier",
        0,
        reject_reason="no_organism_or_strain_identifier",
    )


def output_row(row: dict[str, str], evidence: Evidence) -> dict[str, str]:
    return {
        "ncppb_number": clean_text(row.get("ncppb_number", "")),
        "ncbi_db": clean_text(row.get("ncbi_db", "")),
        "ncbi_uid": clean_text(row.get("ncbi_uid", "")),
        "ncbi_accession": clean_text(row.get("ncbi_accession", "")),
        "source_url": clean_text(row.get("source_url", "")),
        "title": clean_text(row.get("title", "")),
        "organism": clean_text(row.get("organism", "")),
        "taxid": clean_text(row.get("taxid", "")),
        "evidence_level": evidence.evidence_level,
        "evidence_decision": evidence.evidence_decision,
        "evidence_class": evidence.evidence_class,
        "evidence_score": str(evidence.evidence_score),
        "matched_identifier": evidence.matched_identifier,
        "matched_identifier_type": evidence.matched_identifier_type,
        "identifier_rule_name": evidence.identifier_rule_name,
        "identifier_confidence": evidence.identifier_confidence,
        "reject_reason": evidence.reject_reason,
        "query_source": clean_text(row.get("query_source", "")),
        "search_term": clean_text(row.get("search_term", "")),
        "metadata_text": row_metadata_text(row),
        "status": clean_text(row.get("status", "")),
        "error": clean_text(row.get("error", "")),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-input", required=True, help="Raw BioSample CSV/TSV from script 10")
    parser.add_argument("--identifiers", required=True, help="Identifier candidate CSV/TSV from script 09")
    parser.add_argument("--matches-output", required=True, help="Accepted match CSV/TSV output path")
    parser.add_argument("--review-output", required=True, help="Rejected/review CSV/TSV output path")
    parser.add_argument(
        "--no-ncppb-number",
        action="store_true",
        help="Do not use NCPPB + number patterns during filtering",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_path = Path(args.raw_input)
    identifiers_path = Path(args.identifiers)
    if not raw_path.exists():
        raise SystemExit(f"Raw input not found: {raw_path}")
    if not identifiers_path.exists():
        raise SystemExit(f"Identifier input not found: {identifiers_path}")

    raw_rows = read_table(raw_path)
    identifier_rows = read_table(identifiers_path)
    patterns_by_strain = build_patterns(identifier_rows, include_ncppb_number=not args.no_ncppb_number)

    matches: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    for row in raw_rows:
        ncppb_number = clean_text(row.get("ncppb_number", ""))
        classified = output_row(row, classify_row(row, patterns_by_strain.get(ncppb_number, [])))
        if classified["evidence_decision"] == "accept":
            matches.append(classified)
        else:
            review.append(classified)

    write_table(Path(args.matches_output), matches)
    write_table(Path(args.review_output), review)
    print(f"Wrote {len(matches)} accepted rows and {len(review)} review rows")


if __name__ == "__main__":
    main()
