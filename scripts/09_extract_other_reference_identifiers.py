#!/usr/bin/env python3
"""Extract identifier-like search terms from NCPPB Other references text."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path


KNOWN_COLLECTION_PREFIXES = {
    "ATCC",
    "BCCM",
    "CCUG",
    "CFBP",
    "CIP",
    "DSM",
    "DSMZ",
    "IBSP",
    "ICMP",
    "ICPB",
    "IMI",
    "ISPAVE-B",
    "ITCC",
    "JCM",
    "LMG",
    "NBC",
    "NCTC",
    "NIB",
    "NRRL",
    "PD",
    "PDDCC",
    "RIV",
    "UQM",
    "VKM",
    "WDCM",
    "ATTCC",
}

STOPWORD_PREFIXES = {
    "A",
    "AN",
    "AND",
    "AS",
    "AT",
    "BY",
    "COLLECTION",
    "COLLECTIONS",
    "DONOR",
    "EX",
    "FOR",
    "FROM",
    "IN",
    "IS",
    "ISOLATE",
    "NO",
    "OF",
    "ON",
    "OR",
    "REFERENCE",
    "SOURCE",
    "THE",
    "THIS",
    "TO",
    "WAS",
    "WITH",
}

CONTEXT_TRIGGERS = (
    "donor reference",
    "donor ref",
    "reference is",
    "reference was",
    "also in the collections",
    "also in collections",
    "in the collections",
    "collection",
    "accession",
)

SOURCE_TRIGGERS = (
    "isolated by",
    "source of this isolate",
    "the source",
    "received from",
    "obtained from",
)

KNOWN_PREFIX_RE = re.compile(
    rf"(?<![A-Za-z0-9])({'|'.join(re.escape(prefix) for prefix in sorted(KNOWN_COLLECTION_PREFIXES, key=len, reverse=True))})"
    r"\s*[-:_/.]?\s*([A-Za-z]*[-_/]?\d[A-Za-z0-9./-]*)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

GENERAL_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z]{1,10}(?:[-/][A-Za-z]{1,10})*)\s*[-:_/.]?\s*(\d[A-Za-z0-9]*(?:[/.-][A-Za-z0-9]+)*)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

EMBEDDED_CODE_RES = [
    re.compile(
        r"(?<![A-Za-z0-9])\d+[/-]([A-Za-z]{1,10})[/-](\d[A-Za-z0-9.-]*)(?![A-Za-z0-9])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![A-Za-z0-9])[A-Za-z]{1,10}[-/]([A-Za-z]{1,10})[-/]?(\d[A-Za-z0-9.-]*)(?![A-Za-z0-9])",
        re.IGNORECASE,
    ),
]

OUTPUT_COLUMNS = [
    "ncppb_number",
    "other_references",
    "matched_text",
    "normalized_identifier",
    "prefix",
    "suffix",
    "rule_name",
    "confidence",
    "include_for_search",
    "biosample_query",
    "context",
]

CONFIDENCE_RANK = {"none": 0, "reject": 1, "low": 2, "medium": 3, "high": 4}


@dataclass(frozen=True)
class Candidate:
    ncppb_number: str
    other_references: str
    matched_text: str
    normalized_identifier: str
    prefix: str
    suffix: str
    rule_name: str
    confidence: str
    include_for_search: str
    biosample_query: str
    context: str


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def table_delimiter(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=table_delimiter(path))
        return [{key: value or "" for key, value in row.items()} for row in reader]


def write_table(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, delimiter=table_delimiter(path))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def normalise_identifier(prefix: str, suffix: str) -> tuple[str, str, str]:
    norm_prefix = clean_text(prefix).upper()
    norm_suffix = clean_text(suffix).upper().strip(".,;:")
    norm_suffix = re.sub(r"\s+", "", norm_suffix)
    return norm_prefix, norm_suffix, f"{norm_prefix} {norm_suffix}".strip()


def query_from_identifier(prefix: str, suffix: str) -> str:
    prefix_terms = [part for part in re.split(r"[^A-Za-z0-9]+", prefix.upper()) if part]
    suffix_terms = [part for part in re.split(r"[^A-Za-z0-9]+", suffix.upper()) if part]
    terms = [*prefix_terms, *suffix_terms]
    return " AND ".join(f"{term}[All Fields]" for term in terms)


def context_window(text: str, start: int, end: int, radius: int = 80) -> str:
    return clean_text(text[max(0, start - radius) : min(len(text), end + radius)])


def has_trigger(context: str, triggers: tuple[str, ...]) -> bool:
    lowered = context.lower()
    return any(trigger in lowered for trigger in triggers)


def has_initials_before_prefix(context: str, raw_prefix: str, matched_text: str) -> bool:
    escaped_prefix = re.escape(raw_prefix)
    escaped_match = re.escape(matched_text)
    pattern = re.compile(rf"(?:\b[A-Z]\.\s*){{1,4}}{escaped_prefix}\s+{escaped_match.split(r'\ ', 1)[-1]}", re.IGNORECASE)
    return bool(pattern.search(context))


def classify_candidate(
    prefix: str,
    suffix: str,
    raw_prefix: str,
    matched_text: str,
    context: str,
    known_prefix: bool,
) -> tuple[str, str, str]:
    if len(prefix) == 1 and (has_trigger(context, SOURCE_TRIGGERS) or has_trigger(context, CONTEXT_TRIGGERS)):
        return "source_context_single_letter_code", "low", "yes"
    if prefix == "NO" and has_trigger(context, SOURCE_TRIGGERS):
        return "source_context_number_label", "low", "yes"
    if prefix in STOPWORD_PREFIXES:
        return "stopword_prefix", "reject", "no"
    if known_prefix:
        return "known_collection_prefix", "high", "yes"
    if has_initials_before_prefix(context, raw_prefix, matched_text) and len(prefix) > 1:
        return "person_or_local_reference_code", "low", "yes"
    if has_trigger(context, CONTEXT_TRIGGERS):
        return "contextual_reference_code", "medium", "yes"
    if raw_prefix.isupper() and len(prefix) >= 2:
        return "uppercase_general_code", "medium", "yes"
    if len(prefix) == 1:
        return "single_letter_code", "low", "yes"
    return "general_code_candidate", "low", "yes"


def make_candidate(
    ncppb_number: str,
    other_references: str,
    match: re.Match[str],
    known_prefix: bool,
) -> Candidate:
    raw_prefix, raw_suffix = match.group(1), match.group(2)
    prefix, suffix, normalized = normalise_identifier(raw_prefix, raw_suffix)
    context = context_window(other_references, match.start(), match.end())
    rule_name, confidence, include = classify_candidate(
        prefix=prefix,
        suffix=suffix,
        raw_prefix=raw_prefix,
        matched_text=match.group(0),
        context=context,
        known_prefix=known_prefix,
    )
    query = query_from_identifier(prefix, suffix) if include == "yes" else ""
    return Candidate(
        ncppb_number=ncppb_number,
        other_references=other_references,
        matched_text=clean_text(match.group(0)),
        normalized_identifier=normalized,
        prefix=prefix,
        suffix=suffix,
        rule_name=rule_name,
        confidence=confidence,
        include_for_search=include,
        biosample_query=query,
        context=context,
    )


def better_candidate(existing: Candidate, new: Candidate) -> Candidate:
    old_rank = CONFIDENCE_RANK.get(existing.confidence, 0)
    new_rank = CONFIDENCE_RANK.get(new.confidence, 0)
    if new_rank > old_rank:
        return new
    if new_rank == old_rank and existing.include_for_search == "no" and new.include_for_search == "yes":
        return new
    return existing


def extract_candidates(ncppb_number: str, other_references: str) -> list[Candidate]:
    text = clean_text(other_references)
    candidates: dict[str, Candidate] = {}

    for match in KNOWN_PREFIX_RE.finditer(text):
        candidate = make_candidate(ncppb_number, text, match, known_prefix=True)
        candidates[candidate.normalized_identifier] = candidate

    for match in GENERAL_CODE_RE.finditer(text):
        candidate = make_candidate(ncppb_number, text, match, known_prefix=False)
        existing = candidates.get(candidate.normalized_identifier)
        candidates[candidate.normalized_identifier] = (
            better_candidate(existing, candidate) if existing else candidate
        )

    for pattern in EMBEDDED_CODE_RES:
        for match in pattern.finditer(text):
            candidate = make_candidate(ncppb_number, text, match, known_prefix=False)
            existing = candidates.get(candidate.normalized_identifier)
            candidates[candidate.normalized_identifier] = (
                better_candidate(existing, candidate) if existing else candidate
            )

    return list(candidates.values())


def no_identifier_row(ncppb_number: str, other_references: str) -> dict[str, str]:
    return {
        "ncppb_number": ncppb_number,
        "other_references": other_references,
        "matched_text": "",
        "normalized_identifier": "",
        "prefix": "",
        "suffix": "",
        "rule_name": "no_identifier_found",
        "confidence": "none",
        "include_for_search": "no",
        "biosample_query": "",
        "context": "",
    }


def candidate_to_row(candidate: Candidate) -> dict[str, str]:
    return {
        "ncppb_number": candidate.ncppb_number,
        "other_references": candidate.other_references,
        "matched_text": candidate.matched_text,
        "normalized_identifier": candidate.normalized_identifier,
        "prefix": candidate.prefix,
        "suffix": candidate.suffix,
        "rule_name": candidate.rule_name,
        "confidence": candidate.confidence,
        "include_for_search": candidate.include_for_search,
        "biosample_query": candidate.biosample_query,
        "context": candidate.context,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Two-column NCPPB Other references CSV/TSV")
    parser.add_argument("--output", required=True, help="Identifier candidate CSV/TSV output path")
    parser.add_argument(
        "--drop-empty-rows",
        action="store_true",
        help="Do not write no_identifier_found rows for strains without any identifier-like text",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Input table not found: {input_path}")

    source_rows = read_table(input_path)
    output_rows: list[dict[str, str]] = []
    included = 0
    rejected = 0

    for row in source_rows:
        ncppb_number = clean_text(row.get("ncppb_number", ""))
        other_references = clean_text(row.get("other_references", ""))
        candidates = extract_candidates(ncppb_number, other_references)
        if not candidates and not args.drop_empty_rows:
            output_rows.append(no_identifier_row(ncppb_number, other_references))
            continue
        for candidate in candidates:
            output_rows.append(candidate_to_row(candidate))
            if candidate.include_for_search == "yes":
                included += 1
            else:
                rejected += 1

    write_table(output_path, output_rows)
    print(
        f"Wrote {len(output_rows)} rows to {output_path} "
        f"({included} included identifiers, {rejected} rejected candidates)"
    )


if __name__ == "__main__":
    main()
