#!/usr/bin/env python3
"""Analyse rejected BioSample rows by metadata field and attribute evidence.

This complements the keyword/prefix analysis.  It asks where an old
`[All Fields]` hit came from inside the BioSample record, which is the practical
question behind replacing broad queries with fielded BioSample searches.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable


OVERVIEW_COLUMNS = [
    "metric",
    "value",
    "interpretation",
]

FIELD_COLUMNS = [
    "metadata_field",
    "rows",
    "unique_strains",
    "unique_accessions",
    "prior_accepted_rows",
    "non_accepted_rows",
    "non_target_rows",
    "target_rows",
    "clear_noise_rows",
    "supports_review_rows",
    "possible_rescue_rows",
    "query_no_hit_rows",
    "conflict_rows",
    "taxon_only_rows",
    "query_terms_only_rows",
    "prefix_only_rows",
    "suffix_only_rows",
    "local_identifier_rows",
    "accepted_rate",
    "non_target_rate",
    "example_ncppb_number",
    "example_accession",
    "example_title",
]

IDENTIFIER_EVIDENCE_COLUMNS = [
    "keyword_match_class",
    "raw_audit_decision",
    "audit_reason",
    "prior_reject_reason",
    "organism_class",
    "rows",
    "unique_strains",
    "unique_accessions",
    "prior_accepted_rows",
    "non_target_rows",
    "target_rows",
    "conflict_rows",
    "taxon_only_rows",
    "example_ncppb_number",
    "example_accession",
    "example_title",
]

ATTRIBUTE_COLUMNS = [
    "attribute_key",
    "attribute_category",
    "rows",
    "unique_strains",
    "unique_accessions",
    "prior_accepted_rows",
    "non_accepted_rows",
    "non_target_rows",
    "target_rows",
    "clear_noise_rows",
    "supports_review_rows",
    "possible_rescue_rows",
    "accepted_rate",
    "non_target_rate",
    "example_ncppb_number",
    "example_accession",
    "example_value",
]

RECOMMENDATION_COLUMNS = [
    "priority",
    "affected_script_or_stage",
    "current_issue",
    "recommended_change",
    "implementation_detail",
    "evidence",
    "expected_effect",
]

REPORT_SUMMARY_COLUMNS = [
    "section",
    "finding",
    "value",
    "evidence_table",
    "reporting_sentence",
]

EXACT_FIELD_RE = re.compile(r":(?P<fields>[A-Za-z0-9_, -]+)(?:;|$)")
ATTRIBUTE_PAIR_RE = re.compile(r"([^:;]+):\s*([^;]*)")
NCPPB_RE = re.compile(r"\bNCPPB(?:\s*(?:No\.?|Number|#|:|-|_))?\s*0*(\d{1,5})(?!\d)", re.IGNORECASE)


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


def rate(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.4f}" if denominator else ""


def row_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        clean_text(row.get("ncppb_number", "")),
        clean_text(row.get("ncbi_uid", "")),
        clean_text(row.get("ncbi_accession", "")),
        clean_text(row.get("search_term", "")),
        clean_text(row.get("status", "")),
    )


def merge_raw_and_audit(raw_rows: list[dict[str, str]], audit_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Attach raw attributes/infraspecies to raw-audit rows.

    The raw and audit files usually preserve row order, but joining by a queue
    per key keeps the script stable if that changes.
    """

    raw_by_key: dict[tuple[str, str, str, str, str], deque[dict[str, str]]] = defaultdict(deque)
    for row in raw_rows:
        raw_by_key[row_key(row)].append(row)

    merged: list[dict[str, str]] = []
    for audit in audit_rows:
        raw = raw_by_key.get(row_key(audit), deque())
        raw_row = raw.popleft() if raw else {}
        row = dict(audit)
        for key in ["identifiers", "infraspecies", "attributes", "metadata_text"]:
            row[f"raw_{key}"] = raw_row.get(key, audit.get(key, ""))
        merged.append(row)
    return merged


def is_all_fields(row: dict[str, str]) -> bool:
    return "[All Fields]" in clean_text(row.get("search_term", ""))


def is_prior_accepted(row: dict[str, str]) -> bool:
    return clean_text(row.get("prior_classification", "")) == "accepted"


def is_non_accepted(row: dict[str, str]) -> bool:
    return not is_prior_accepted(row)


def ncppb_digits(value: str) -> set[str]:
    return {match.group(1).lstrip("0") or "0" for match in NCPPB_RE.finditer(value or "")}


def parse_query_term_fields(value: str) -> set[str]:
    fields: set[str] = set()
    for part in clean_text(value).split(";"):
        part = part.strip()
        if ":" not in part:
            continue
        _term, field_text = part.split(":", 1)
        for field in re.split(r"[,/|]", field_text):
            cleaned = clean_text(field).lower().replace(" ", "_")
            if cleaned:
                fields.add(cleaned)
    return fields


def exact_metadata_fields(row: dict[str, str]) -> set[str]:
    fields = parse_query_term_fields(row.get("query_term_fields", ""))
    best_fields = parse_query_term_fields("best:" + row.get("best_identifier_fields", ""))
    fields.update(best_fields)
    if not fields:
        decision = clean_text(row.get("raw_audit_decision", ""))
        if decision == "query_no_hit":
            fields.add("no_hit")
        elif clean_text(row.get("status", "")) and clean_text(row.get("status", "")) != "ok":
            fields.add("query_error")
        else:
            fields.add("unresolved_metadata_text")
    return fields


def parse_attribute_pairs(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for match in ATTRIBUTE_PAIR_RE.finditer(text or ""):
        key = clean_text(match.group(1)).strip(" .").lower()
        value = clean_text(match.group(2)).strip()
        if key:
            pairs.append((key, value))
    return pairs


def attribute_category(key: str) -> str:
    key_lower = key.lower()
    if "culture_collection" in key_lower or "culture collection" in key_lower:
        return "culture_collection_or_voucher"
    if "specimen_voucher" in key_lower or "voucher" in key_lower or "bio_material" in key_lower:
        return "culture_collection_or_voucher"
    if "strain" in key_lower or "isolate" in key_lower:
        return "strain_or_isolate"
    if "sample name" in key_lower or "sample_name" in key_lower or "submitter id" in key_lower or "external id" in key_lower:
        return "sample_or_submitter_id"
    if "organism" in key_lower or "scientific_name" in key_lower or "tax" in key_lower:
        return "organism_or_taxonomy"
    if "host" in key_lower:
        return "host"
    if "geo" in key_lower or "country" in key_lower or "latitude" in key_lower or "longitude" in key_lower:
        return "geography"
    if "collection_date" in key_lower or "collection date" in key_lower or key_lower == "date":
        return "collection_date"
    if "environment" in key_lower or key_lower.startswith("env_") or "isolation_source" in key_lower:
        return "environment_or_source"
    if "center" in key_lower or "insdc" in key_lower or "ena" in key_lower:
        return "submission_metadata"
    return "other_attribute"


def summary_counts(group: list[dict[str, str]]) -> dict[str, int]:
    return {
        "rows": len(group),
        "unique_strains": len({row.get("ncppb_number", "") for row in group if row.get("ncppb_number", "")}),
        "unique_accessions": len({row.get("ncbi_accession", "") for row in group if row.get("ncbi_accession", "")}),
        "prior_accepted_rows": sum(1 for row in group if is_prior_accepted(row)),
        "non_accepted_rows": sum(1 for row in group if is_non_accepted(row)),
        "non_target_rows": sum(1 for row in group if row.get("organism_class") == "non_target_organism"),
        "target_rows": sum(1 for row in group if row.get("organism_class") == "target_organism"),
        "clear_noise_rows": sum(1 for row in group if row.get("raw_audit_decision") == "clear_noise"),
        "supports_review_rows": sum(1 for row in group if row.get("raw_audit_decision") == "supports_review"),
        "possible_rescue_rows": sum(1 for row in group if row.get("raw_audit_decision") == "possible_false_negative_rescue"),
        "query_no_hit_rows": sum(1 for row in group if row.get("raw_audit_decision") == "query_no_hit"),
        "conflict_rows": sum(1 for row in group if clean_text(row.get("conflicting_ncppb_numbers", ""))),
        "taxon_only_rows": sum(1 for row in group if row.get("prior_reject_reason") == "no_exact_strain_identifier_match"),
        "query_terms_only_rows": sum(1 for row in group if row.get("keyword_match_class") == "query_terms_present_separately"),
        "prefix_only_rows": sum(1 for row in group if row.get("keyword_match_class") == "prefix_only_match"),
        "suffix_only_rows": sum(1 for row in group if row.get("keyword_match_class") == "suffix_only_match"),
        "local_identifier_rows": sum(1 for row in group if row.get("best_identifier_type") == "local_or_donor_identifier"),
    }


def first_example(group: list[dict[str, str]]) -> dict[str, str]:
    for row in group:
        if clean_text(row.get("ncbi_accession", "")) or clean_text(row.get("title", "")):
            return {
                "example_ncppb_number": row.get("ncppb_number", ""),
                "example_accession": row.get("ncbi_accession", ""),
                "example_title": row.get("title", ""),
            }
    return {"example_ncppb_number": "", "example_accession": "", "example_title": ""}


def metadata_field_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if not is_all_fields(row) or is_prior_accepted(row):
            continue
        for field in exact_metadata_fields(row):
            grouped[field].append(row)

    output: list[dict[str, Any]] = []
    for field, group in grouped.items():
        counts = summary_counts(group)
        output.append(
            {
                "metadata_field": field,
                **counts,
                "accepted_rate": rate(counts["prior_accepted_rows"], counts["rows"]),
                "non_target_rate": rate(counts["non_target_rows"], counts["rows"]),
                **first_example(group),
            }
        )
    return sorted(output, key=lambda row: (-int(row["rows"]), row["metadata_field"]))


def identifier_evidence_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if not is_all_fields(row) or is_prior_accepted(row):
            continue
        key = (
            clean_text(row.get("keyword_match_class", "")) or "blank",
            clean_text(row.get("raw_audit_decision", "")) or "blank",
            clean_text(row.get("audit_reason", "")) or "blank",
            clean_text(row.get("prior_reject_reason", "")) or "blank",
            clean_text(row.get("organism_class", "")) or "blank",
        )
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    for (match_class, decision, audit_reason, prior_reject_reason, organism_class), group in grouped.items():
        counts = summary_counts(group)
        output.append(
            {
                "keyword_match_class": match_class,
                "raw_audit_decision": decision,
                "audit_reason": audit_reason,
                "prior_reject_reason": prior_reject_reason,
                "organism_class": organism_class,
                "rows": counts["rows"],
                "unique_strains": counts["unique_strains"],
                "unique_accessions": counts["unique_accessions"],
                "prior_accepted_rows": counts["prior_accepted_rows"],
                "non_target_rows": counts["non_target_rows"],
                "target_rows": counts["target_rows"],
                "conflict_rows": counts["conflict_rows"],
                "taxon_only_rows": counts["taxon_only_rows"],
                **first_example(group),
            }
        )
    return sorted(output, key=lambda row: (-int(row["rows"]), row["keyword_match_class"], row["raw_audit_decision"]))


def attribute_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    example_values: dict[tuple[str, str], str] = {}
    for row in rows:
        if not is_all_fields(row):
            continue
        pairs = parse_attribute_pairs(row.get("raw_attributes", ""))
        pairs.extend(parse_attribute_pairs(row.get("raw_infraspecies", "")))
        seen: set[tuple[str, str]] = set()
        for key, value in pairs:
            category = attribute_category(key)
            group_key = (key, category)
            if group_key in seen:
                continue
            seen.add(group_key)
            grouped[group_key].append(row)
            if group_key not in example_values and value:
                example_values[group_key] = value[:240]

    output: list[dict[str, Any]] = []
    for (key, category), group in grouped.items():
        counts = summary_counts(group)
        output.append(
            {
                "attribute_key": key,
                "attribute_category": category,
                **counts,
                "accepted_rate": rate(counts["prior_accepted_rows"], counts["rows"]),
                "non_target_rate": rate(counts["non_target_rows"], counts["rows"]),
                **first_example(group),
                "example_value": example_values.get((key, category), ""),
            }
        )
    return sorted(output, key=lambda row: (-int(row["rows"]), row["attribute_category"], row["attribute_key"]))


def overview_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    all_rows = [row for row in rows if is_all_fields(row)]
    non_accepted = [row for row in all_rows if is_non_accepted(row)]
    field_counter: Counter[str] = Counter()
    attribute_key_counter: Counter[str] = Counter()
    attribute_category_counter: Counter[str] = Counter()
    ncppb_in_non_target = 0
    ncppb_conflict_in_non_target = 0
    for row in non_accepted:
        for field in exact_metadata_fields(row):
            field_counter[field] += 1
        if row.get("organism_class") == "non_target_organism" and ncppb_digits(row.get("raw_metadata_text", "")):
            ncppb_in_non_target += 1
            if clean_text(row.get("conflicting_ncppb_numbers", "")):
                ncppb_conflict_in_non_target += 1
        for key, _value in parse_attribute_pairs(row.get("raw_attributes", "")):
            attribute_key_counter[key] += 1
            attribute_category_counter[attribute_category(key)] += 1

    top_field = field_counter.most_common(1)[0] if field_counter else ("", 0)
    top_attribute = attribute_key_counter.most_common(1)[0] if attribute_key_counter else ("", 0)
    return [
        {
            "metric": "all_fields_raw_rows",
            "value": len(all_rows),
            "interpretation": "Rows produced by the legacy All Fields BioSample harvest.",
        },
        {
            "metric": "all_fields_non_accepted_rows",
            "value": len(non_accepted),
            "interpretation": "Rows not accepted by current strict BioSample filtering.",
        },
        {
            "metric": "all_fields_prior_accepted_rows",
            "value": sum(1 for row in all_rows if is_prior_accepted(row)),
            "interpretation": "Confirmed accepted rows used as the recall floor for query redesign.",
        },
        {
            "metric": "non_target_organism_non_accepted_rows",
            "value": sum(1 for row in non_accepted if row.get("organism_class") == "non_target_organism"),
            "interpretation": "Main false-positive burden that fielded queries should reduce.",
        },
        {
            "metric": "target_organism_non_accepted_rows",
            "value": sum(1 for row in non_accepted if row.get("organism_class") == "target_organism"),
            "interpretation": "Rows to keep available for review/rescue, not automatic acceptance.",
        },
        {
            "metric": "query_no_hit_rows",
            "value": sum(1 for row in non_accepted if row.get("raw_audit_decision") == "query_no_hit"),
            "interpretation": "No-hit rows retained for per-strain search coverage accounting.",
        },
        {
            "metric": "query_terms_present_separately_rows",
            "value": sum(1 for row in non_accepted if row.get("keyword_match_class") == "query_terms_present_separately"),
            "interpretation": "Typical All Fields artefact: prefix and number appear somewhere, but not as one identifier.",
        },
        {
            "metric": "top_non_accepted_hit_field",
            "value": f"{top_field[0]}:{top_field[1]}",
            "interpretation": "Most common metadata field where rejected query terms were observed.",
        },
        {
            "metric": "top_attribute_key_in_non_accepted_rows",
            "value": f"{top_attribute[0]}:{top_attribute[1]}",
            "interpretation": "Most common BioSample attribute key among rejected rows.",
        },
        {
            "metric": "non_target_rows_with_ncppb_like_metadata",
            "value": ncppb_in_non_target,
            "interpretation": "Non-target records can still contain NCPPB-like text; organism and conflict checks must remain after retrieval.",
        },
        {
            "metric": "non_target_rows_with_conflicting_ncppb_number",
            "value": ncppb_conflict_in_non_target,
            "interpretation": "These explain why query hit alone cannot prove strain identity.",
        },
    ]


def recommendation_rows(rows: list[dict[str, str]], field_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_rows = [row for row in rows if is_all_fields(row)]
    non_accepted = [row for row in all_rows if is_non_accepted(row)]
    non_target = sum(1 for row in non_accepted if row.get("organism_class") == "non_target_organism")
    target_review = sum(1 for row in non_accepted if row.get("organism_class") == "target_organism")
    query_terms_only = sum(1 for row in non_accepted if row.get("keyword_match_class") == "query_terms_present_separately")
    no_hit = sum(1 for row in non_accepted if row.get("raw_audit_decision") == "query_no_hit")
    ncppb_accepted = sum(1 for row in all_rows if row.get("rule_name") == "ncppb_number" and is_prior_accepted(row))
    top_field = field_summary[0]["metadata_field"] if field_summary else "metadata_text"

    return [
        {
            "priority": "P0",
            "affected_script_or_stage": "scripts/10_harvest_biosample_raw.py query profile",
            "current_issue": "Legacy current_all_fields profile is too broad for default BioSample harvest.",
            "recommended_change": "Keep current_all_fields only for reproducibility; make strict_xanthomonas or query-plan generated strict profile the default before the next full rerun.",
            "implementation_detail": "For NCPPB and trusted equivalent IDs emit (PREFIX[Text Word] AND NUMBER[Text Word]) AND Xanthomonas[Organism].",
            "evidence": f"{non_target} non-accepted All Fields rows are non-target organisms; {query_terms_only} rows only contain query terms separately.",
            "expected_effect": "Large false-positive reduction while preserving accepted rows through exact local metadata filtering.",
        },
        {
            "priority": "P0",
            "affected_script_or_stage": "BioSample field choice",
            "current_issue": "Replacing [All Fields] with a hypothetical [BioSample] field would not target strain identifiers.",
            "recommended_change": "Use the BioSample database plus documented fields: [Text Word], [Organism], [Attribute], [Title], [Accession].",
            "implementation_detail": "Do not emit PREFIX[BioSample]. Use [Accession] only for SAMN/SAMEA/SAMD accessions; pilot [Attribute] for high-confidence collection IDs.",
            "evidence": f"Rejected hits are distributed across BioSample metadata fields, with top rejected field '{top_field}', so database name is not a useful strain-identifier field.",
            "expected_effect": "Avoids a non-specific field substitution and keeps queries aligned to BioSample search semantics.",
        },
        {
            "priority": "P1",
            "affected_script_or_stage": "scripts/09_extract_other_reference_identifiers.py and curated identifier table",
            "current_issue": "Short local/person/source codes can be extracted correctly but become noisy when searched by default.",
            "recommended_change": "Keep all candidates in the curated identifier table, but only trusted collection prefixes and NCPPB numbers enter default search.",
            "implementation_detail": "Set B/X/S/XP/XC/PATEL-like local or person/source-context rules to fallback_only, manual_review_only, or reject_noise based on rejected-result policy.",
            "evidence": "Existing All Fields prefix analysis shows short/local prefixes dominate rejected non-target rows.",
            "expected_effect": "Reduces false positives without losing manual evidence for future false-negative rescue.",
        },
        {
            "priority": "P1",
            "affected_script_or_stage": "raw-data screening after harvest",
            "current_issue": "A fielded query can still retrieve side hits, especially when the same NCPPB number appears in another organism or conflict record.",
            "recommended_change": "Keep post-harvest acceptance based on local exact identifier evidence, organism compatibility, and conflicting-NCPPB checks.",
            "implementation_detail": "Do not accept any row solely because the query returned it; require exact NCPPB or trusted equivalent identifier in title/infraspecies/attributes/identifiers/metadata_text.",
            "evidence": f"{ncppb_accepted} accepted NCPPB-number rows coexist with non-target/conflicting All Fields hits.",
            "expected_effect": "Controls both false positives and suspected catalogue/NCBI metadata inconsistencies.",
        },
        {
            "priority": "P2",
            "affected_script_or_stage": "fallback/rescue workflow",
            "current_issue": "Strict default search may miss records where BioSample uses local isolate codes only.",
            "recommended_change": "Create a separate fallback query plan for local codes, never merged into accepted output without manual evidence review.",
            "implementation_detail": "Fallback terms should still use Text Word + Xanthomonas[Organism], and results should be labelled rescue candidates.",
            "evidence": f"{target_review} target-organism non-accepted rows and {no_hit} no-hit rows define the manual review/rescue pool.",
            "expected_effect": "Preserves recall channels while keeping the default 898-strain table clean.",
        },
    ]


def report_summary_rows(
    rows: list[dict[str, str]],
    field_summary: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    all_rows = [row for row in rows if is_all_fields(row)]
    non_accepted = [row for row in all_rows if is_non_accepted(row)]
    accepted = sum(1 for row in all_rows if is_prior_accepted(row))
    non_target = sum(1 for row in non_accepted if row.get("organism_class") == "non_target_organism")
    target = sum(1 for row in non_accepted if row.get("organism_class") == "target_organism")
    no_hit = sum(1 for row in non_accepted if row.get("raw_audit_decision") == "query_no_hit")
    query_terms_only = sum(1 for row in non_accepted if row.get("keyword_match_class") == "query_terms_present_separately")
    top_fields = "; ".join(f"{row['metadata_field']}={row['rows']}" for row in field_summary[:5])
    p0_recommendations = "; ".join(row["recommended_change"] for row in recommendations if row.get("priority") == "P0")

    return [
        {
            "section": "current_result",
            "finding": "legacy_all_fields_raw_rows",
            "value": len(all_rows),
            "evidence_table": "rejected_biosample_metadata_overview.tsv",
            "reporting_sentence": "旧 All Fields BioSample harvest 共得到 33,829 rows，可作为旧策略的完整复现基线。",
        },
        {
            "section": "current_result",
            "finding": "accepted_rows_preserved",
            "value": accepted,
            "evidence_table": "rejected_biosample_metadata_overview.tsv",
            "reporting_sentence": "当前严格筛选已确认 612 accepted BioSample rows，这些是下一轮 strict query 需要保留的召回底线。",
        },
        {
            "section": "rejected_burden",
            "finding": "non_accepted_rows",
            "value": len(non_accepted),
            "evidence_table": "rejected_biosample_metadata_overview.tsv",
            "reporting_sentence": "旧策略产生 33,217 non-accepted rows，需要用 rejected-result 分析反向优化检索参数。",
        },
        {
            "section": "rejected_burden",
            "finding": "non_target_organism_rows",
            "value": non_target,
            "evidence_table": "rejected_biosample_metadata_overview.tsv",
            "reporting_sentence": "31,827 个 non-accepted rows 是 non-Xanthomonas organism，说明主要问题是假阳性而不是人工审核不足。",
        },
        {
            "section": "all_fields_failure_mode",
            "finding": "query_terms_present_separately_rows",
            "value": query_terms_only,
            "evidence_table": "rejected_by_identifier_evidence.tsv",
            "reporting_sentence": "30,707 个 rows 只是 prefix 与 number 在记录中分散出现，不构成 exact strain identifier match。",
        },
        {
            "section": "metadata_location",
            "finding": "top_rejected_metadata_fields",
            "value": top_fields,
            "evidence_table": "rejected_by_metadata_field.tsv",
            "reporting_sentence": "rejected query terms 主要出现在 metadata_text、attributes、identifiers、title 和 infraspecies，而这些字段中的命中并不都能证明 strain identity。",
        },
        {
            "section": "manual_review_pool",
            "finding": "target_review_and_no_hit_rows",
            "value": f"target_non_accepted={target}; no_hit={no_hit}",
            "evidence_table": "rejected_biosample_metadata_overview.tsv",
            "reporting_sentence": "148 个 target-organism non-accepted rows 和 1,242 个 no-hit rows 应保留为 manual review/rescue 池，而不是直接作为 accepted。",
        },
        {
            "section": "search_change",
            "finding": "primary_script_recommendation",
            "value": p0_recommendations,
            "evidence_table": "search_script_modification_recommendations.tsv",
            "reporting_sentence": "下一轮默认检索应使用 Text Word + Organism 的 strict profile，不应把 [All Fields] 机械替换成 [BioSample]。",
        },
    ]


def build_tables(raw_rows: list[dict[str, str]], audit_rows: list[dict[str, str]]) -> dict[str, tuple[list[dict[str, Any]], list[str]]]:
    rows = merge_raw_and_audit(raw_rows, audit_rows)
    field_summary = metadata_field_rows(rows)
    recommendations = recommendation_rows(rows, field_summary)
    return {
        "rejected_biosample_metadata_overview.tsv": (overview_rows(rows), OVERVIEW_COLUMNS),
        "rejected_by_metadata_field.tsv": (field_summary, FIELD_COLUMNS),
        "rejected_by_identifier_evidence.tsv": (identifier_evidence_rows(rows), IDENTIFIER_EVIDENCE_COLUMNS),
        "rejected_by_biosample_attribute.tsv": (attribute_rows(rows), ATTRIBUTE_COLUMNS),
        "search_script_modification_recommendations.tsv": (recommendations, RECOMMENDATION_COLUMNS),
        "report_ready_rejected_analysis_summary.tsv": (
            report_summary_rows(rows, field_summary, recommendations),
            REPORT_SUMMARY_COLUMNS,
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True, help="Raw BioSample harvest TSV/CSV")
    parser.add_argument("--raw-audit", required=True, help="Raw candidate audit TSV/CSV")
    parser.add_argument("--output-dir", required=True, help="Directory for metadata analysis TSV outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_rows = read_table(Path(args.raw))
    audit_rows = read_table(Path(args.raw_audit))
    output_dir = Path(args.output_dir)

    tables = build_tables(raw_rows, audit_rows)
    for filename, (rows, columns) in tables.items():
        write_table(output_dir / filename, rows, columns)
    print(f"Wrote {len(tables)} BioSample metadata analysis tables to {output_dir}")


if __name__ == "__main__":
    main()
