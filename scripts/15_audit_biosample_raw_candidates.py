#!/usr/bin/env python3
"""Audit raw BioSample candidates and translate rejected results into search policy.

This script sits between raw harvest and final matching. It explains why a raw
row was retrieved, whether local strain evidence is present, and which search
terms should be kept, restricted, downgraded, or disabled in future runs.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


TARGET_ORGANISM_DEFAULT = "Xanthomonas"

RAW_AUDIT_COLUMNS = [
    "ncppb_number",
    "ncbi_accession",
    "ncbi_uid",
    "status",
    "organism",
    "taxid",
    "title",
    "query_profile",
    "query_source",
    "normalized_identifier",
    "prefix",
    "suffix",
    "rule_name",
    "confidence",
    "target_organism_filter",
    "search_term",
    "count_returned",
    "ids_fetched",
    "retmax_saturated",
    "prior_classification",
    "prior_evidence_level",
    "prior_reject_reason",
    "prior_matched_identifier",
    "organism_class",
    "target_ncppb_numbers_in_metadata",
    "conflicting_ncppb_numbers",
    "best_identifier_match",
    "best_identifier_type",
    "best_identifier_rule_name",
    "best_identifier_confidence",
    "best_identifier_include_for_search",
    "best_identifier_fields",
    "query_terms",
    "query_terms_found",
    "query_term_fields",
    "keyword_match_class",
    "raw_audit_decision",
    "audit_reason",
    "keyword_policy_signal",
    "metadata_excerpt",
    "source_url",
]

KEYWORD_SUMMARY_COLUMNS = [
    "query_profile",
    "query_source",
    "search_term",
    "normalized_identifier",
    "prefix",
    "suffix",
    "rule_name",
    "confidence",
    "target_organism_filter",
    "raw_rows",
    "ok_rows",
    "no_hit_rows",
    "target_organism_rows",
    "non_target_organism_rows",
    "conflict_rows",
    "target_ncppb_identifier_rows",
    "equivalent_collection_identifier_rows",
    "local_identifier_rows",
    "query_terms_only_rows",
    "prefix_only_rows",
    "suffix_only_rows",
    "no_query_term_rows",
    "prior_accepted_rows",
    "prior_review_rows",
    "possible_rescue_rows",
    "clear_noise_rows",
    "retmax_saturated_rows",
    "unique_target_strains",
    "unique_accessions",
    "non_target_rate",
    "review_rows_per_accepted_row",
    "keyword_policy_recommendation",
    "recommendation_reason",
    "example_ncppb_number",
    "example_accession",
    "example_title",
]

PREFIX_RECOMMENDATION_COLUMNS = [
    "prefix",
    "rule_name",
    "confidence",
    "raw_rows",
    "ok_rows",
    "no_hit_rows",
    "target_organism_rows",
    "non_target_organism_rows",
    "conflict_rows",
    "prior_accepted_rows",
    "prior_review_rows",
    "possible_rescue_rows",
    "clear_noise_rows",
    "unique_target_strains",
    "unique_search_terms",
    "non_target_rate",
    "review_rows_per_accepted_row",
    "keyword_policy_recommendation",
    "recommendation_reason",
    "example_search_term",
]

STRAIN_SUMMARY_COLUMNS = [
    "ncppb_number",
    "raw_rows",
    "ok_rows",
    "no_hit_rows",
    "prior_accepted_rows",
    "prior_review_rows",
    "supports_accept_rows",
    "supports_review_rows",
    "possible_rescue_rows",
    "clear_noise_rows",
    "conflict_rows",
    "target_taxon_query_only_rows",
    "noisy_search_terms",
    "manual_review_priority",
    "example_accessions",
]

RESCUE_COLUMNS = [
    "priority",
    "ncppb_number",
    "ncbi_accession",
    "organism",
    "title",
    "best_identifier_match",
    "best_identifier_rule_name",
    "best_identifier_confidence",
    "best_identifier_include_for_search",
    "keyword_match_class",
    "prior_classification",
    "raw_audit_decision",
    "audit_reason",
    "query_profile",
    "query_source",
    "search_term",
    "source_url",
]

NCPPB_NUMBER_RE = re.compile(
    r"\bNCPPB(?:\s*(?:No\.?|Number|#|:|-|_))?\s*0*(\d{1,5})(?!\d)",
    re.IGNORECASE,
)
FIELD_TERM_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._/-]*)\[(All Fields|Text Word|Title|Attribute|Organism|Attribute Name)\]", re.IGNORECASE)

LOW_CONFIDENCE_RULES = {
    "source_context_single_letter_code",
    "source_context_number_label",
    "single_letter_code",
    "person_or_local_reference_code",
    "general_code_candidate",
    "stopword_prefix",
}


@dataclass(frozen=True)
class IdentifierPattern:
    value: str
    identifier_type: str
    pattern: re.Pattern[str]
    rule_name: str
    confidence: str
    include_for_search: str


@dataclass(frozen=True)
class PriorClassification:
    label: str = ""
    evidence_level: str = ""
    reject_reason: str = ""
    matched_identifier: str = ""


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


def ncppb_digits(value: str) -> str:
    match = re.search(r"\d+", value or "")
    return match.group(0).lstrip("0") if match else ""


def numeric_sort_value(ncppb_number: str) -> int:
    digits = ncppb_digits(ncppb_number)
    return int(digits) if digits else 0


def identifier_pattern_from_parts(prefix: str, suffix: str) -> re.Pattern[str] | None:
    prefix_parts = [part for part in re.split(r"[^A-Za-z0-9]+", clean_text(prefix).upper()) if part]
    suffix_parts = [part for part in re.split(r"[^A-Za-z0-9]+", clean_text(suffix).upper()) if part]
    if not prefix_parts or not suffix_parts:
        return None
    prefix_pattern = r"\s*[:_./-]?\s*".join(re.escape(part) for part in prefix_parts)
    suffix_pattern = r"\s*[:_./-]?\s*".join(re.escape(part) for part in suffix_parts)
    return re.compile(
        rf"(?<![A-Za-z0-9]){prefix_pattern}\s*[:_./-]?\s*{suffix_pattern}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def ncppb_identifier_pattern(ncppb_number: str) -> IdentifierPattern | None:
    digits = ncppb_digits(ncppb_number)
    if not digits:
        return None
    pattern = re.compile(
        rf"\bNCPPB(?:\s*(?:No\.?|Number|#|:|-|_))?\s*0*{re.escape(digits)}(?!\d)",
        re.IGNORECASE,
    )
    return IdentifierPattern(f"NCPPB {digits}", "ncppb_number", pattern, "ncppb_number", "high", "yes")


def identifier_pattern(row: dict[str, str]) -> IdentifierPattern | None:
    value = clean_text(row.get("normalized_identifier", "")).upper()
    if not value:
        return None
    prefix = clean_text(row.get("prefix", ""))
    suffix = clean_text(row.get("suffix", ""))
    if not prefix or not suffix:
        match = re.match(r"^([A-Z]{1,12}(?:[-/][A-Z]{1,12})*)\s+(.+)$", value)
        if not match:
            return None
        prefix, suffix = match.groups()
    pattern = identifier_pattern_from_parts(prefix, suffix)
    if pattern is None:
        return None
    return IdentifierPattern(
        value,
        "other_reference_identifier",
        pattern,
        clean_text(row.get("rule_name", "")),
        clean_text(row.get("confidence", "")),
        clean_text(row.get("include_for_search", "")) or "no",
    )


def identifier_score(identifier: IdentifierPattern) -> int:
    if identifier.identifier_type == "ncppb_number":
        return 100
    if identifier.rule_name == "known_collection_prefix":
        return 90
    return {"high": 85, "medium": 60, "low": 35, "reject": 0, "none": 0}.get(identifier.confidence, 25)


def build_identifier_patterns(identifier_rows: list[dict[str, str]], include_ncppb_number: bool = True) -> dict[str, list[IdentifierPattern]]:
    patterns: dict[str, list[IdentifierPattern]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()

    if include_ncppb_number:
        for row in identifier_rows:
            ncppb_number = clean_text(row.get("ncppb_number", ""))
            pattern = ncppb_identifier_pattern(ncppb_number)
            if pattern is None:
                continue
            key = (ncppb_number, pattern.identifier_type, pattern.value)
            if key in seen:
                continue
            seen.add(key)
            patterns[ncppb_number].append(pattern)

    for row in identifier_rows:
        ncppb_number = clean_text(row.get("ncppb_number", ""))
        pattern = identifier_pattern(row)
        if not ncppb_number or pattern is None:
            continue
        key = (ncppb_number, pattern.identifier_type, pattern.value)
        if key in seen:
            continue
        seen.add(key)
        patterns[ncppb_number].append(pattern)

    return dict(patterns)


def identifier_lookup(identifier_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    lookup: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in identifier_rows:
        ncppb = clean_text(row.get("ncppb_number", ""))
        normalized = clean_text(row.get("normalized_identifier", ""))
        prefix_suffix = f"{clean_text(row.get('prefix', '')).upper()}::{clean_text(row.get('suffix', '')).upper()}"
        search_term = clean_text(row.get("biosample_query", ""))
        for key_type, value in [
            ("normalized_identifier", normalized),
            ("prefix_suffix", prefix_suffix),
            ("search_term", search_term),
        ]:
            if ncppb and value and value != "::":
                lookup[(ncppb, key_type, value)] = row
    return lookup


def infer_query_profile(search_term: str) -> str:
    if "[All Fields]" in search_term:
        return "current_all_fields"
    if "[Organism]" in search_term and "[Text Word]" in search_term:
        return "strict_xanthomonas"
    if "[Text Word]" in search_term:
        return "broad_review"
    return ""


def enrich_query_metadata(row: dict[str, str], lookup: dict[tuple[str, str, str], dict[str, str]]) -> dict[str, str]:
    enriched = dict(row)
    ncppb = clean_text(enriched.get("ncppb_number", ""))
    search_term = clean_text(enriched.get("search_term", ""))
    prefix = clean_text(enriched.get("prefix", "")).upper()
    suffix = clean_text(enriched.get("suffix", "")).upper()
    normalized = clean_text(enriched.get("normalized_identifier", ""))

    if clean_text(enriched.get("query_source", "")) == "ncppb_number" or search_term.upper().startswith("NCPPB["):
        digits = ncppb_digits(ncppb) or suffix
        enriched.setdefault("normalized_identifier", f"NCPPB {digits}".strip())
        enriched.setdefault("prefix", "NCPPB")
        enriched.setdefault("suffix", digits)
        if not clean_text(enriched.get("rule_name", "")):
            enriched["rule_name"] = "ncppb_number"
        if not clean_text(enriched.get("confidence", "")):
            enriched["confidence"] = "high"
        prefix = clean_text(enriched.get("prefix", "")).upper()
        suffix = clean_text(enriched.get("suffix", "")).upper()
        normalized = clean_text(enriched.get("normalized_identifier", ""))

    candidates = [
        lookup.get((ncppb, "normalized_identifier", normalized)),
        lookup.get((ncppb, "prefix_suffix", f"{prefix}::{suffix}")),
        lookup.get((ncppb, "search_term", search_term)),
    ]
    meta = next((candidate for candidate in candidates if candidate), {})
    for field in ["normalized_identifier", "prefix", "suffix", "rule_name", "confidence"]:
        if not clean_text(enriched.get(field, "")) and meta:
            enriched[field] = clean_text(meta.get(field, ""))
    if not clean_text(enriched.get("query_profile", "")):
        enriched["query_profile"] = infer_query_profile(search_term)
    if not clean_text(enriched.get("target_organism_filter", "")) and "[Organism]" in search_term:
        organism_terms = [term for term, field in FIELD_TERM_RE.findall(search_term) if field.lower() == "organism"]
        enriched["target_organism_filter"] = organism_terms[-1] if organism_terms else ""
    return enriched


def field_texts(row: dict[str, str]) -> dict[str, str]:
    fields = {
        "title": clean_text(row.get("title", "")),
        "organism": clean_text(row.get("organism", "")),
        "identifiers": clean_text(row.get("identifiers", "")),
        "infraspecies": clean_text(row.get("infraspecies", "")),
        "attributes": clean_text(row.get("attributes", "")),
        "metadata_text": clean_text(row.get("metadata_text", "")),
    }
    if not fields["metadata_text"]:
        fields["metadata_text"] = clean_text(" ".join(fields.values()))
    return fields


def metadata_text(row: dict[str, str]) -> str:
    return field_texts(row)["metadata_text"]


def matched_fields(pattern: re.Pattern[str], fields: dict[str, str]) -> list[str]:
    ordered_fields = ["title", "identifiers", "infraspecies", "attributes", "organism", "metadata_text"]
    return [field for field in ordered_fields if fields.get(field) and pattern.search(fields[field])]


def best_matching_identifier(patterns: list[IdentifierPattern], fields: dict[str, str]) -> tuple[IdentifierPattern | None, list[str]]:
    matches: list[tuple[IdentifierPattern, list[str]]] = []
    for pattern in patterns:
        fields_matched = matched_fields(pattern.pattern, fields)
        if fields_matched:
            matches.append((pattern, fields_matched))
    if not matches:
        return None, []
    best, best_fields = sorted(matches, key=lambda item: identifier_score(item[0]), reverse=True)[0]
    return best, best_fields


def find_ncppb_numbers(text: str) -> set[str]:
    return {match.group(1).lstrip("0") or "0" for match in NCPPB_NUMBER_RE.finditer(text or "")}


def token_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", re.IGNORECASE)


def query_terms(row: dict[str, str], target_organism: str) -> list[str]:
    terms: list[str] = []
    organism = clean_text(target_organism).upper()
    for term, field in FIELD_TERM_RE.findall(clean_text(row.get("search_term", ""))):
        term_clean = clean_text(term).upper()
        if field.lower() == "organism" and term_clean == organism:
            continue
        if term_clean and term_clean not in terms:
            terms.append(term_clean)
    if terms:
        return terms
    for field in ["prefix", "suffix"]:
        for part in re.split(r"[^A-Za-z0-9]+", clean_text(row.get(field, "")).upper()):
            if part and part not in terms:
                terms.append(part)
    return terms


def query_term_presence(row: dict[str, str], fields: dict[str, str], target_organism: str) -> tuple[list[str], dict[str, list[str]]]:
    terms = query_terms(row, target_organism)
    found: dict[str, list[str]] = {}
    for term in terms:
        pattern = token_pattern(term)
        term_fields = matched_fields(pattern, fields)
        if term_fields:
            found[term] = term_fields
    return terms, found


def organism_class(row: dict[str, str], target_organism: str) -> str:
    if clean_text(row.get("status", "")) == "no_hit":
        return "no_hit"
    organism = clean_text(row.get("organism", ""))
    if not organism:
        return "missing_organism"
    target = clean_text(target_organism)
    if target and re.search(rf"\b{re.escape(target)}\b", organism, re.IGNORECASE):
        return "target_organism"
    return "non_target_organism"


def prior_keys(row: dict[str, str]) -> list[tuple[str, str, str, str, str]]:
    ncppb = clean_text(row.get("ncppb_number", ""))
    uid = clean_text(row.get("ncbi_uid", ""))
    accession = clean_text(row.get("ncbi_accession", ""))
    term = clean_text(row.get("search_term", ""))
    status = clean_text(row.get("status", ""))
    keys = [
        (ncppb, uid, accession, term, status),
        (ncppb, uid, accession, term, ""),
        (ncppb, uid, accession, "", ""),
        (ncppb, "", accession, term, ""),
        (ncppb, "", accession, "", ""),
        (ncppb, "", "", term, status),
        (ncppb, "", "", term, ""),
    ]
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped


def build_prior_lookup(match_rows: list[dict[str, str]], review_rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str], PriorClassification]:
    lookup: dict[tuple[str, str, str, str, str], PriorClassification] = {}
    for label, rows in [("accepted", match_rows), ("review", review_rows)]:
        for row in rows:
            prior = PriorClassification(
                label=label,
                evidence_level=clean_text(row.get("evidence_level", "")),
                reject_reason=clean_text(row.get("reject_reason", "")),
                matched_identifier=clean_text(row.get("matched_identifier", "")),
            )
            for key in prior_keys(row):
                lookup.setdefault(key, prior)
    return lookup


def lookup_prior(row: dict[str, str], prior_lookup: dict[tuple[str, str, str, str, str], PriorClassification]) -> PriorClassification:
    for key in prior_keys(row):
        prior = prior_lookup.get(key)
        if prior is not None:
            return prior
    return PriorClassification()


def keyword_match_class(
    status: str,
    best_identifier: IdentifierPattern | None,
    terms: list[str],
    found_terms: dict[str, list[str]],
) -> str:
    if status == "no_hit":
        return "no_hit"
    if best_identifier is not None:
        if best_identifier.identifier_type == "ncppb_number":
            return "target_ncppb_identifier_match"
        if best_identifier.rule_name == "known_collection_prefix":
            return "equivalent_collection_identifier_match"
        return "local_or_donor_identifier_match"
    if terms and len(found_terms) == len(terms):
        return "query_terms_present_separately"
    prefix_found = bool(terms[:1] and terms[0] in found_terms)
    suffix_found = bool(len(terms) > 1 and terms[-1] in found_terms)
    if prefix_found and not suffix_found:
        return "prefix_only"
    if suffix_found and not prefix_found:
        return "suffix_only"
    if found_terms:
        return "partial_query_terms_present"
    return "no_query_term_in_metadata"


def classify_raw_audit(
    row: dict[str, str],
    prior: PriorClassification,
    best_identifier: IdentifierPattern | None,
    organism_status: str,
    expected_digits: str,
    ncppb_numbers: set[str],
    match_class: str,
) -> tuple[str, str, str]:
    status = clean_text(row.get("status", ""))
    if status == "no_hit":
        return "query_no_hit", "query_returned_no_biosample_records", "no_hit"
    if status and status != "ok":
        return "supports_review", "query_error_or_incomplete_raw_row", "manual_review"

    conflicts = sorted(ncppb_numbers - {expected_digits}) if expected_digits else sorted(ncppb_numbers)
    if conflicts:
        return "supports_review", f"conflicting_ncppb_number:{';'.join(conflicts)}", "manual_review"

    if prior.label == "accepted":
        return "supports_accept", "accepted_by_existing_filter", "productive_exact"

    if best_identifier is not None:
        if best_identifier.identifier_type == "ncppb_number" or best_identifier.rule_name == "known_collection_prefix":
            if organism_status == "target_organism":
                return "supports_accept", "strong_local_identifier_in_target_organism", "productive_exact"
            return "supports_review", "strong_identifier_with_non_target_or_missing_organism", "manual_review"
        if organism_status == "target_organism":
            if best_identifier.include_for_search.lower() != "yes" or best_identifier.confidence in {"low", "reject", "none"}:
                return "possible_false_negative_rescue", "low_confidence_identifier_matches_target_organism_metadata", "rescue_candidate"
            return "supports_review", "local_identifier_requires_manual_review", "manual_review"
        return "clear_noise", "weak_identifier_in_non_target_or_missing_organism", "noise"

    if organism_status == "non_target_organism":
        return "clear_noise", "non_target_organism_without_local_identifier", "noise"
    if organism_status == "target_organism" and match_class in {"query_terms_present_separately", "partial_query_terms_present"}:
        return "supports_review", "target_taxon_query_terms_without_exact_identifier", "manual_review"
    if organism_status == "target_organism":
        return "supports_review", "target_taxon_without_exact_identifier", "manual_review"
    return "supports_review", "missing_organism_or_unclassified_candidate", "manual_review"


def metadata_excerpt(text: str, length: int = 320) -> str:
    text = clean_text(text)
    if len(text) <= length:
        return text
    return text[: length - 3].rstrip() + "..."


def audit_raw_rows(
    raw_rows: list[dict[str, str]],
    identifier_rows: list[dict[str, str]],
    match_rows: list[dict[str, str]] | None = None,
    review_rows: list[dict[str, str]] | None = None,
    target_organism: str = TARGET_ORGANISM_DEFAULT,
) -> list[dict[str, str]]:
    identifier_meta = identifier_lookup(identifier_rows)
    patterns_by_strain = build_identifier_patterns(identifier_rows, include_ncppb_number=True)
    prior_lookup = build_prior_lookup(match_rows or [], review_rows or [])
    audited: list[dict[str, str]] = []

    for raw_row in raw_rows:
        row = enrich_query_metadata(raw_row, identifier_meta)
        fields = field_texts(row)
        ncppb_number = clean_text(row.get("ncppb_number", ""))
        expected_digits = ncppb_digits(ncppb_number)
        ncppb_numbers = find_ncppb_numbers(fields["metadata_text"])
        conflicts = sorted(ncppb_numbers - {expected_digits}) if expected_digits else sorted(ncppb_numbers)
        best_identifier, best_fields = best_matching_identifier(patterns_by_strain.get(ncppb_number, []), fields)
        terms, found_terms = query_term_presence(row, fields, target_organism)
        organism_status = organism_class(row, target_organism)
        match_class = keyword_match_class(clean_text(row.get("status", "")), best_identifier, terms, found_terms)
        prior = lookup_prior(row, prior_lookup)
        decision, reason, signal = classify_raw_audit(
            row=row,
            prior=prior,
            best_identifier=best_identifier,
            organism_status=organism_status,
            expected_digits=expected_digits,
            ncppb_numbers=ncppb_numbers,
            match_class=match_class,
        )
        audited.append(
            {
                "ncppb_number": ncppb_number,
                "ncbi_accession": clean_text(row.get("ncbi_accession", "")),
                "ncbi_uid": clean_text(row.get("ncbi_uid", "")),
                "status": clean_text(row.get("status", "")),
                "organism": clean_text(row.get("organism", "")),
                "taxid": clean_text(row.get("taxid", "")),
                "title": clean_text(row.get("title", "")),
                "query_profile": clean_text(row.get("query_profile", "")),
                "query_source": clean_text(row.get("query_source", "")),
                "normalized_identifier": clean_text(row.get("normalized_identifier", "")),
                "prefix": clean_text(row.get("prefix", "")).upper(),
                "suffix": clean_text(row.get("suffix", "")).upper(),
                "rule_name": clean_text(row.get("rule_name", "")),
                "confidence": clean_text(row.get("confidence", "")),
                "target_organism_filter": clean_text(row.get("target_organism_filter", "")),
                "search_term": clean_text(row.get("search_term", "")),
                "count_returned": clean_text(row.get("count_returned", row.get("id_count_returned", ""))),
                "ids_fetched": clean_text(row.get("ids_fetched", "")),
                "retmax_saturated": clean_text(row.get("retmax_saturated", "")),
                "prior_classification": prior.label,
                "prior_evidence_level": prior.evidence_level,
                "prior_reject_reason": prior.reject_reason,
                "prior_matched_identifier": prior.matched_identifier,
                "organism_class": organism_status,
                "target_ncppb_numbers_in_metadata": ";".join(sorted(ncppb_numbers, key=lambda value: int(value) if value.isdigit() else 0)),
                "conflicting_ncppb_numbers": ";".join(conflicts),
                "best_identifier_match": best_identifier.value if best_identifier else "",
                "best_identifier_type": best_identifier.identifier_type if best_identifier else "",
                "best_identifier_rule_name": best_identifier.rule_name if best_identifier else "",
                "best_identifier_confidence": best_identifier.confidence if best_identifier else "",
                "best_identifier_include_for_search": best_identifier.include_for_search if best_identifier else "",
                "best_identifier_fields": ";".join(best_fields),
                "query_terms": ";".join(terms),
                "query_terms_found": ";".join(term for term in terms if term in found_terms),
                "query_term_fields": ";".join(f"{term}:{','.join(found_terms[term])}" for term in terms if term in found_terms),
                "keyword_match_class": match_class,
                "raw_audit_decision": decision,
                "audit_reason": reason,
                "keyword_policy_signal": signal,
                "metadata_excerpt": metadata_excerpt(fields["metadata_text"]),
                "source_url": clean_text(row.get("source_url", "")),
            }
        )
    return audited


def truthy_yes(value: str) -> bool:
    return clean_text(value).lower() == "yes"


def count_rows(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "raw_rows": len(rows),
        "ok_rows": sum(1 for row in rows if row.get("status") == "ok"),
        "no_hit_rows": sum(1 for row in rows if row.get("status") == "no_hit" or row.get("raw_audit_decision") == "query_no_hit"),
        "target_organism_rows": sum(1 for row in rows if row.get("organism_class") == "target_organism"),
        "non_target_organism_rows": sum(1 for row in rows if row.get("organism_class") == "non_target_organism"),
        "conflict_rows": sum(1 for row in rows if bool(row.get("conflicting_ncppb_numbers"))),
        "target_ncppb_identifier_rows": sum(1 for row in rows if row.get("keyword_match_class") == "target_ncppb_identifier_match"),
        "equivalent_collection_identifier_rows": sum(1 for row in rows if row.get("keyword_match_class") == "equivalent_collection_identifier_match"),
        "local_identifier_rows": sum(1 for row in rows if row.get("keyword_match_class") == "local_or_donor_identifier_match"),
        "query_terms_only_rows": sum(1 for row in rows if row.get("keyword_match_class") == "query_terms_present_separately"),
        "prefix_only_rows": sum(1 for row in rows if row.get("keyword_match_class") == "prefix_only"),
        "suffix_only_rows": sum(1 for row in rows if row.get("keyword_match_class") == "suffix_only"),
        "no_query_term_rows": sum(1 for row in rows if row.get("keyword_match_class") == "no_query_term_in_metadata"),
        "prior_accepted_rows": sum(1 for row in rows if row.get("prior_classification") == "accepted"),
        "prior_review_rows": sum(1 for row in rows if row.get("prior_classification") == "review"),
        "possible_rescue_rows": sum(1 for row in rows if row.get("raw_audit_decision") == "possible_false_negative_rescue"),
        "clear_noise_rows": sum(1 for row in rows if row.get("raw_audit_decision") == "clear_noise"),
        "retmax_saturated_rows": sum(1 for row in rows if truthy_yes(row.get("retmax_saturated", ""))),
    }


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.2f}" if denominator else ""


def rate(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.3f}" if denominator else ""


def representative(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = clean_text(row.get(field, ""))
        if value:
            return value
    return ""


def recommend_policy(rows: list[dict[str, str]], group_label: str = "keyword") -> tuple[str, str]:
    counts = count_rows(rows)
    raw = counts["raw_rows"]
    non_target = counts["non_target_organism_rows"]
    accepted = counts["prior_accepted_rows"]
    review = counts["prior_review_rows"]
    rescue = counts["possible_rescue_rows"]
    exact_strong = counts["target_ncppb_identifier_rows"] + counts["equivalent_collection_identifier_rows"]
    clear_noise = counts["clear_noise_rows"]
    no_hit = counts["no_hit_rows"]
    rule_names = {row.get("rule_name", "") for row in rows}
    confidences = {row.get("confidence", "") for row in rows}
    prefixes = {row.get("prefix", "") for row in rows}

    non_target_fraction = non_target / raw if raw else 0.0
    review_per_accept = review / accepted if accepted else None
    has_low_rule = bool(rule_names & LOW_CONFIDENCE_RULES) or "low" in confidences or "reject" in confidences

    if rule_names == {"ncppb_number"} or prefixes == {"NCPPB"}:
        return "keep_strict_profile", "NCPPB number is core evidence; keep Text Word plus organism-filtered profile."
    if no_hit == raw and raw > 0:
        return "no_hit_evidence_only", "The query currently returns no BioSample rows; keep as reproducible no-hit evidence, not as an expansion term."
    if accepted > 0 and exact_strong > 0 and (review_per_accept is None or review_per_accept <= 20) and non_target_fraction < 0.5:
        return "keep_default", "Accepted strain-level evidence is productive and noise is limited."
    if "known_collection_prefix" in rule_names and exact_strong > 0 and non_target_fraction < 0.8:
        return "keep_strict_profile", "Known collection identifier produces exact metadata evidence; keep under strict organism-filtered queries."
    if accepted > 0 and (review_per_accept is not None and review_per_accept > 100 or non_target_fraction >= 0.9):
        return "fallback_only", "It has accepted evidence but the rejected-result burden is too high for default runs."
    if rescue > 0:
        return "fallback_only", "Potential false-negative rescue rows exist; use only in targeted review batches."
    if has_low_rule and raw >= 10 and non_target_fraction >= 0.8:
        return "disable_default", "Low-confidence/local-code rule is dominated by non-target raw hits."
    if accepted == 0 and exact_strong == 0 and raw >= 20 and non_target_fraction >= 0.9:
        return "disable_default", "No accepted or exact identifier evidence and non-target raw hits dominate."
    if clear_noise >= 50 and accepted == 0:
        return "disable_default", "Rejected-result audit shows repeated clear noise without accepted evidence."
    if counts["target_organism_rows"] > 0 or counts["query_terms_only_rows"] > 0:
        return "manual_review_only", "Target-taxon or query-term-only rows need review but should not auto-accept."
    if prefixes == {"NCPPB"}:
        return "keep_strict_profile", "NCPPB prefix should remain available with strict fielded search."
    return "manual_review_only", "Insufficient accepted evidence for default search; keep for curated review decisions."


def summary_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str, str, str]:
    return (
        row.get("query_profile", ""),
        row.get("query_source", ""),
        row.get("search_term", ""),
        row.get("normalized_identifier", ""),
        row.get("prefix", ""),
        row.get("suffix", ""),
        row.get("rule_name", ""),
        row.get("confidence", ""),
        row.get("target_organism_filter", ""),
    )


def keyword_summary_rows(audited_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in audited_rows:
        grouped[summary_key(row)].append(row)
    rows: list[dict[str, Any]] = []
    for key, group in grouped.items():
        counts = count_rows(group)
        recommendation, reason = recommend_policy(group, "keyword")
        rows.append(
            {
                "query_profile": key[0],
                "query_source": key[1],
                "search_term": key[2],
                "normalized_identifier": key[3],
                "prefix": key[4],
                "suffix": key[5],
                "rule_name": key[6],
                "confidence": key[7],
                "target_organism_filter": key[8],
                **counts,
                "unique_target_strains": len({row.get("ncppb_number", "") for row in group if row.get("ncppb_number", "")}),
                "unique_accessions": len({row.get("ncbi_accession", "") for row in group if row.get("ncbi_accession", "")}),
                "non_target_rate": rate(counts["non_target_organism_rows"], counts["raw_rows"]),
                "review_rows_per_accepted_row": ratio(counts["prior_review_rows"], counts["prior_accepted_rows"]),
                "keyword_policy_recommendation": recommendation,
                "recommendation_reason": reason,
                "example_ncppb_number": representative(group, "ncppb_number"),
                "example_accession": representative(group, "ncbi_accession"),
                "example_title": representative(group, "title"),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["keyword_policy_recommendation"] != "disable_default",
            -int(row["raw_rows"]),
            row["prefix"],
            row["search_term"],
        ),
    )


def dominant_value(rows: list[dict[str, str]], field: str) -> str:
    counts = Counter(clean_text(row.get(field, "")) for row in rows if clean_text(row.get(field, "")))
    return counts.most_common(1)[0][0] if counts else ""


def prefix_recommendation_rows(audited_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in audited_rows:
        key = (row.get("prefix", ""), row.get("rule_name", ""), row.get("confidence", ""))
        if key[0] or key[1]:
            grouped[key].append(row)
    rows: list[dict[str, Any]] = []
    for key, group in grouped.items():
        counts = count_rows(group)
        recommendation, reason = recommend_policy(group, "prefix")
        rows.append(
            {
                "prefix": key[0],
                "rule_name": key[1],
                "confidence": key[2],
                **{
                    column: counts[column]
                    for column in [
                        "raw_rows",
                        "ok_rows",
                        "no_hit_rows",
                        "target_organism_rows",
                        "non_target_organism_rows",
                        "conflict_rows",
                        "prior_accepted_rows",
                        "prior_review_rows",
                        "possible_rescue_rows",
                        "clear_noise_rows",
                    ]
                },
                "unique_target_strains": len({row.get("ncppb_number", "") for row in group if row.get("ncppb_number", "")}),
                "unique_search_terms": len({row.get("search_term", "") for row in group if row.get("search_term", "")}),
                "non_target_rate": rate(counts["non_target_organism_rows"], counts["raw_rows"]),
                "review_rows_per_accepted_row": ratio(counts["prior_review_rows"], counts["prior_accepted_rows"]),
                "keyword_policy_recommendation": recommendation,
                "recommendation_reason": reason,
                "example_search_term": representative(group, "search_term"),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["raw_rows"]), row["prefix"], row["rule_name"]))


def strain_summary_rows(audited_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in audited_rows:
        grouped[row.get("ncppb_number", "")].append(row)
    rows: list[dict[str, Any]] = []
    for ncppb, group in grouped.items():
        if not ncppb:
            continue
        counts = count_rows(group)
        noisy_terms = sorted(
            {
                row.get("search_term", "")
                for row in group
                if row.get("raw_audit_decision") == "clear_noise" and row.get("search_term", "")
            }
        )
        example_accessions = sorted({row.get("ncbi_accession", "") for row in group if row.get("ncbi_accession", "")})[:10]
        if counts["possible_rescue_rows"]:
            priority = "P1_possible_false_negative_rescue"
        elif counts["conflict_rows"]:
            priority = "P2_conflicting_identifier_review"
        elif counts["query_terms_only_rows"] or counts["target_organism_rows"]:
            priority = "P3_target_taxon_without_exact_identifier"
        elif counts["prior_accepted_rows"]:
            priority = "confirmed_has_accepted_biosample"
        else:
            priority = "low_priority_noise_or_no_hit"
        rows.append(
            {
                "ncppb_number": ncppb,
                "raw_rows": counts["raw_rows"],
                "ok_rows": counts["ok_rows"],
                "no_hit_rows": counts["no_hit_rows"],
                "prior_accepted_rows": counts["prior_accepted_rows"],
                "prior_review_rows": counts["prior_review_rows"],
                "supports_accept_rows": sum(1 for row in group if row.get("raw_audit_decision") == "supports_accept"),
                "supports_review_rows": sum(1 for row in group if row.get("raw_audit_decision") == "supports_review"),
                "possible_rescue_rows": counts["possible_rescue_rows"],
                "clear_noise_rows": counts["clear_noise_rows"],
                "conflict_rows": counts["conflict_rows"],
                "target_taxon_query_only_rows": counts["query_terms_only_rows"],
                "noisy_search_terms": "; ".join(noisy_terms[:8]),
                "manual_review_priority": priority,
                "example_accessions": ";".join(example_accessions),
            }
        )
    return sorted(rows, key=lambda row: (row["manual_review_priority"], numeric_sort_value(row["ncppb_number"])))


def rescue_candidate_rows(audited_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in audited_rows:
        decision = row.get("raw_audit_decision", "")
        match_class = row.get("keyword_match_class", "")
        if decision == "possible_false_negative_rescue":
            priority = "P1_low_confidence_identifier_in_target_taxon"
        elif decision == "supports_review" and row.get("organism_class") == "target_organism" and match_class in {
            "query_terms_present_separately",
            "partial_query_terms_present",
        }:
            priority = "P2_target_taxon_query_terms_only"
        else:
            continue
        rows.append({"priority": priority, **{column: row.get(column, "") for column in RESCUE_COLUMNS if column != "priority"}})
    return sorted(rows, key=lambda row: (row["priority"], numeric_sort_value(row["ncppb_number"]), row["ncbi_accession"]))


def build_audit_tables(audited_rows: list[dict[str, str]]) -> dict[str, tuple[list[dict[str, Any]], list[str]]]:
    return {
        "raw_candidate_audit.tsv": (audited_rows, RAW_AUDIT_COLUMNS),
        "keyword_audit_summary.tsv": (keyword_summary_rows(audited_rows), KEYWORD_SUMMARY_COLUMNS),
        "prefix_keyword_recommendations.tsv": (prefix_recommendation_rows(audited_rows), PREFIX_RECOMMENDATION_COLUMNS),
        "strain_raw_audit_summary.tsv": (strain_summary_rows(audited_rows), STRAIN_SUMMARY_COLUMNS),
        "false_negative_rescue_candidates.tsv": (rescue_candidate_rows(audited_rows), RESCUE_COLUMNS),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-input", required=True, help="Raw BioSample TSV/CSV from script 10")
    parser.add_argument("--identifiers", required=True, help="Identifier candidate TSV/CSV from script 09")
    parser.add_argument("--output-dir", required=True, help="Directory for raw audit TSV outputs")
    parser.add_argument("--matches", default="", help="Optional accepted BioSample matches from script 11")
    parser.add_argument("--review", default="", help="Optional review/rejected BioSample rows from script 11")
    parser.add_argument("--target-organism", default=TARGET_ORGANISM_DEFAULT, help="Target organism name used for organism classification")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_path = Path(args.raw_input)
    identifiers_path = Path(args.identifiers)
    if not raw_path.exists():
        raise SystemExit(f"Raw input not found: {raw_path}")
    if not identifiers_path.exists():
        raise SystemExit(f"Identifier input not found: {identifiers_path}")

    match_rows = read_table(Path(args.matches)) if args.matches else []
    review_rows = read_table(Path(args.review)) if args.review else []
    audited_rows = audit_raw_rows(
        raw_rows=read_table(raw_path),
        identifier_rows=read_table(identifiers_path),
        match_rows=match_rows,
        review_rows=review_rows,
        target_organism=args.target_organism,
    )
    output_dir = Path(args.output_dir)
    for filename, (rows, columns) in build_audit_tables(audited_rows).items():
        write_table(output_dir / filename, rows, columns)
    print(f"Wrote raw BioSample audit for {len(audited_rows)} rows to {output_dir}")


if __name__ == "__main__":
    main()
