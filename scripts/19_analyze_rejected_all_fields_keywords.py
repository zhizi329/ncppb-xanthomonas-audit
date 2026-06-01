#!/usr/bin/env python3
"""Analyse rejected/raw BioSample results from All Fields queries.

The goal is to decide whether old `[All Fields]` queries should be retained,
field-restricted, moved to fallback, or disabled.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


OVERVIEW_COLUMNS = [
    "metric",
    "value",
]

PREFIX_COLUMNS = [
    "prefix",
    "rule_name",
    "confidence",
    "all_fields_raw_rows",
    "prior_accepted_rows",
    "clear_noise_rows",
    "non_target_organism_rows",
    "target_organism_rows",
    "query_no_hit_rows",
    "supports_review_rows",
    "non_target_rate",
    "accepted_rate",
    "current_policy_recommendation",
    "field_strategy_recommendation",
    "recommendation_reason",
]

QUERY_COLUMNS = [
    "search_term",
    "prefix",
    "rule_name",
    "confidence",
    "all_fields_raw_rows",
    "prior_accepted_rows",
    "non_target_organism_rows",
    "target_organism_rows",
    "clear_noise_rows",
    "current_policy_recommendation",
    "field_strategy_recommendation",
    "example_title",
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


def int_value(value: str) -> int:
    try:
        return int(clean_text(value) or "0")
    except ValueError:
        return 0


def rate(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.4f}" if denominator else ""


def all_fields_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if "[All Fields]" in clean_text(row.get("search_term", ""))]


def policy_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], str]:
    lookup: dict[tuple[str, str, str], str] = {}
    for row in rows:
        key = (
            clean_text(row.get("prefix", "")),
            clean_text(row.get("rule_name", "")),
            clean_text(row.get("confidence", "")),
        )
        policy = clean_text(row.get("keyword_policy_recommendation", ""))
        if key[0] or key[1]:
            lookup[key] = policy
    return lookup


def field_strategy(prefix: str, rule_name: str, confidence: str, raw: int, accepted: int, non_target: int) -> tuple[str, str]:
    non_target_fraction = non_target / raw if raw else 0.0
    accepted_fraction = accepted / raw if raw else 0.0

    if rule_name == "ncppb_number":
        return (
            "replace_all_fields_with_text_word_and_organism",
            "NCPPB numbers are core identifiers, but All Fields returns side hits; use Text Word plus organism filter.",
        )
    if rule_name == "known_collection_prefix" and accepted > 0:
        return (
            "replace_all_fields_with_text_word_and_organism_then_pilot_attribute",
            "Known collection IDs remain useful; test Attribute/Text Word under organism filter before full rerun.",
        )
    if accepted == 0 and raw >= 20 and non_target_fraction >= 0.8:
        return (
            "disable_default_do_not_replace_with_biosample",
            "All Fields hits are dominated by non-target records and have no accepted productivity.",
        )
    if accepted > 0 and non_target_fraction >= 0.8:
        return (
            "fallback_only_text_word_and_organism",
            "Some accepted rows exist, but noise is too high for default search.",
        )
    if confidence in {"low", "reject", "none"}:
        return (
            "manual_review_only",
            "Low-confidence identifiers should not be converted into default fielded searches.",
        )
    if accepted_fraction > 0:
        return (
            "replace_all_fields_with_text_word_and_organism",
            "The query has accepted productivity; field restriction should be tested in pilot.",
        )
    return (
        "manual_review_only",
        "Insufficient evidence for default search; keep only as review evidence.",
    )


def overview_rows(raw_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    all_rows = all_fields_rows(raw_rows)
    return [
        {"metric": "all_fields_raw_rows", "value": len(all_rows)},
        {"metric": "prior_accepted_rows", "value": sum(1 for row in all_rows if row.get("prior_classification") == "accepted")},
        {"metric": "clear_noise_rows", "value": sum(1 for row in all_rows if row.get("raw_audit_decision") == "clear_noise")},
        {"metric": "query_no_hit_rows", "value": sum(1 for row in all_rows if row.get("raw_audit_decision") == "query_no_hit")},
        {"metric": "supports_review_rows", "value": sum(1 for row in all_rows if row.get("raw_audit_decision") == "supports_review")},
        {"metric": "non_target_organism_rows", "value": sum(1 for row in all_rows if row.get("organism_class") == "non_target_organism")},
        {"metric": "target_organism_rows", "value": sum(1 for row in all_rows if row.get("organism_class") == "target_organism")},
        {"metric": "query_terms_present_separately_rows", "value": sum(1 for row in all_rows if row.get("keyword_match_class") == "query_terms_present_separately")},
    ]


def prefix_rows(raw_rows: list[dict[str, str]], prefix_policy_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    policies = policy_lookup(prefix_policy_rows)
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in all_fields_rows(raw_rows):
        grouped[
            (
                clean_text(row.get("prefix", "")),
                clean_text(row.get("rule_name", "")),
                clean_text(row.get("confidence", "")),
            )
        ].append(row)

    rows: list[dict[str, Any]] = []
    for (prefix, rule_name, confidence), group in grouped.items():
        raw = len(group)
        accepted = sum(1 for row in group if row.get("prior_classification") == "accepted")
        non_target = sum(1 for row in group if row.get("organism_class") == "non_target_organism")
        target = sum(1 for row in group if row.get("organism_class") == "target_organism")
        clear_noise = sum(1 for row in group if row.get("raw_audit_decision") == "clear_noise")
        no_hit = sum(1 for row in group if row.get("raw_audit_decision") == "query_no_hit")
        supports_review = sum(1 for row in group if row.get("raw_audit_decision") == "supports_review")
        strategy, reason = field_strategy(prefix, rule_name, confidence, raw, accepted, non_target)
        rows.append(
            {
                "prefix": prefix,
                "rule_name": rule_name,
                "confidence": confidence,
                "all_fields_raw_rows": raw,
                "prior_accepted_rows": accepted,
                "clear_noise_rows": clear_noise,
                "non_target_organism_rows": non_target,
                "target_organism_rows": target,
                "query_no_hit_rows": no_hit,
                "supports_review_rows": supports_review,
                "non_target_rate": rate(non_target, raw),
                "accepted_rate": rate(accepted, raw),
                "current_policy_recommendation": policies.get((prefix, rule_name, confidence), ""),
                "field_strategy_recommendation": strategy,
                "recommendation_reason": reason,
            }
        )
    return sorted(rows, key=lambda row: (-int(row["all_fields_raw_rows"]), row["prefix"], row["rule_name"]))


def query_rows(keyword_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in keyword_rows:
        if "[All Fields]" not in row.get("search_term", ""):
            continue
        raw = int_value(row.get("raw_rows", ""))
        accepted = int_value(row.get("prior_accepted_rows", ""))
        non_target = int_value(row.get("non_target_organism_rows", ""))
        strategy, _reason = field_strategy(
            clean_text(row.get("prefix", "")),
            clean_text(row.get("rule_name", "")),
            clean_text(row.get("confidence", "")),
            raw,
            accepted,
            non_target,
        )
        rows.append(
            {
                "search_term": row.get("search_term", ""),
                "prefix": row.get("prefix", ""),
                "rule_name": row.get("rule_name", ""),
                "confidence": row.get("confidence", ""),
                "all_fields_raw_rows": raw,
                "prior_accepted_rows": accepted,
                "non_target_organism_rows": non_target,
                "target_organism_rows": int_value(row.get("target_organism_rows", "")),
                "clear_noise_rows": int_value(row.get("clear_noise_rows", "")),
                "current_policy_recommendation": row.get("keyword_policy_recommendation", ""),
                "field_strategy_recommendation": strategy,
                "example_title": row.get("example_title", ""),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["non_target_organism_rows"]), -int(row["all_fields_raw_rows"]), row["search_term"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-audit", required=True, help="Raw candidate audit TSV/CSV")
    parser.add_argument("--keyword-summary", required=True, help="Keyword audit summary TSV/CSV")
    parser.add_argument("--prefix-recommendations", required=True, help="Prefix keyword recommendations TSV/CSV")
    parser.add_argument("--output-dir", required=True, help="Directory for All Fields analysis TSV outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_rows = read_table(Path(args.raw_audit))
    keyword_summary = read_table(Path(args.keyword_summary))
    prefix_recommendations = read_table(Path(args.prefix_recommendations))
    output_dir = Path(args.output_dir)

    tables = {
        "all_fields_overview.tsv": (overview_rows(raw_rows), OVERVIEW_COLUMNS),
        "all_fields_prefix_analysis.tsv": (prefix_rows(raw_rows, prefix_recommendations), PREFIX_COLUMNS),
        "all_fields_query_analysis.tsv": (query_rows(keyword_summary), QUERY_COLUMNS),
    }
    for filename, (rows, columns) in tables.items():
        write_table(output_dir / filename, rows, columns)
    print(f"Wrote {len(tables)} All Fields analysis tables to {output_dir}")


if __name__ == "__main__":
    main()
