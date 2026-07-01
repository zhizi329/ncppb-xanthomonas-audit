from __future__ import annotations

import re
from collections import defaultdict

from .common import canonical_identifier, clean_text, normalized_ncppb, write_table


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
    "WHRI",
    "CPBF",
    "GBBC",
    "IBSBF",
    "CSL",
    "NBRC",
    "MAFF",
}

KNOWN_SOURCE_IDENTIFIER_RE = re.compile(
    rf"(?<![A-Za-z0-9])({'|'.join(re.escape(value) for value in sorted(KNOWN_COLLECTION_PREFIXES, key=len, reverse=True))})"
    r"\s*[-:_]?\s*([A-Za-z0-9][A-Za-z0-9./-]*)",
    re.IGNORECASE,
)

SOURCE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9./-]*")

IDENTIFIER_COLUMNS = [
    "ncppb_number",
    "identifier_raw",
    "identifier_normalized",
    "identifier_type",
    "clause_type",
    "clause_order",
    "source_start",
    "source_end",
    "normalization_status",
    "validation_status",
    "identifier_strength",
    "risk_level",
    "search_eligible",
    "review_reason",
    "collision_strain_count",
    "collision_strains",
]

REVIEW_COLUMNS = [
    "ncppb_number",
    "review_type",
    "risk_level",
    "raw_text",
    "proposed_value",
    "review_reason",
    "reviewer_decision",
    "reviewer_notes",
]


def collection_prefix(value: str) -> str:
    match = re.match(r"^([A-Za-z][A-Za-z0-9-]{1,15})\b", clean_text(value))
    if not match:
        return ""
    prefix = match.group(1).upper()
    return prefix if prefix in KNOWN_COLLECTION_PREFIXES else ""


def split_collection_payload(value: str) -> list[str]:
    parts = re.split(
        r"\s*(?:,|;|\band\b|\.\s+(?=[A-Za-z][A-Za-z0-9-]*\s*\d))\s*",
        value,
        flags=re.IGNORECASE,
    )
    return [clean_text(part) for part in parts if clean_text(part)]


def identifier_strength(raw_value: str, identifier_type: str) -> str:
    if identifier_type == "ncppb_number":
        return "primary"
    if identifier_type == "collection_number":
        return "strong"
    if identifier_type in {"donor_reference", "isolate_code"}:
        compact = canonical_identifier(raw_value)
        letters = len(re.findall(r"[A-Z]", compact))
        digits = len(re.findall(r"\d", compact))
        if len(compact) >= 4 and (letters >= 2 or digits >= 2):
            return "medium"
        return "weak"
    return "not_searchable"


def source_clause_identifiers(value: str) -> list[tuple[str, str]]:
    """Return conservative searchable identifiers while preserving the full source text separately."""
    found: list[tuple[str, str]] = []
    occupied: list[tuple[int, int]] = []
    for match in KNOWN_SOURCE_IDENTIFIER_RE.finditer(value):
        raw = clean_text(match.group(0))
        found.append((raw, "collection_number"))
        occupied.append(match.span())
    tokens = list(SOURCE_TOKEN_RE.finditer(value))
    for index, match in enumerate(tokens):
        if any(start <= match.start() and match.end() <= end for start, end in occupied):
            continue
        token = match.group(0).strip(" -.,;")
        has_letter = bool(re.search(r"[A-Za-z]", token))
        has_digit = bool(re.search(r"\d", token))
        raw = ""
        if has_letter and has_digit:
            raw = token
        elif token.isdigit() and index > 0:
            previous = tokens[index - 1]
            previous_token = previous.group(0).strip(" -.,;")
            if (
                previous_token.isalpha()
                and previous_token.isupper()
                and len(previous_token) <= 10
                and not any(start <= previous.start() and previous.end() <= end for start, end in occupied)
            ):
                raw = f"{previous_token} {token}"
        if not raw:
            continue
        found.append((raw, "isolate_code"))
    deduplicated: dict[str, tuple[str, str]] = {}
    for raw, identifier_type in found:
        deduplicated.setdefault(canonical_identifier(raw), (raw, identifier_type))
    return list(deduplicated.values())


def identifier_row(
    clause: dict[str, str],
    raw_value: str,
    identifier_type: str,
    risk_level: str,
    search_eligible: str,
    review_reason: str = "",
) -> dict[str, str]:
    normalized = canonical_identifier(raw_value)
    clause_text = clause.get("raw_clause", "")
    local_start = clause_text.find(raw_value)
    clause_start = int(clause.get("text_start", "0") or 0)
    source_start = clause_start + max(local_start, 0)
    source_end = source_start + len(raw_value)
    strength = identifier_strength(raw_value, identifier_type)
    if strength in {"weak", "not_searchable"}:
        search_eligible = "no"
        review_reason = review_reason or "identifier_too_weak_for_automatic_search"
    return {
        "ncppb_number": clause.get("ncppb_number", ""),
        "identifier_raw": raw_value,
        "identifier_normalized": normalized,
        "identifier_type": identifier_type,
        "clause_type": clause.get("clause_type", ""),
        "clause_order": clause.get("clause_order", ""),
        "source_start": str(source_start),
        "source_end": str(source_end),
        "normalization_status": "comparison_only_no_source_edit",
        "validation_status": "auto_validated" if search_eligible == "yes" else "review_required",
        "identifier_strength": strength,
        "risk_level": risk_level,
        "search_eligible": search_eligible,
        "review_reason": review_reason,
        "collision_strain_count": "1",
        "collision_strains": clause.get("ncppb_number", ""),
    }


def extract_identifiers(
    strains: list[dict[str, str]], clauses: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    identifiers: list[dict[str, str]] = []
    reviews: list[dict[str, str]] = []

    for strain in strains:
        number = normalized_ncppb(strain.get("ncppb_number", ""))
        identifiers.append(
            {
                "ncppb_number": number,
                "identifier_raw": number,
                "identifier_normalized": canonical_identifier(number),
                "identifier_type": "ncppb_number",
                "clause_type": "catalogue_primary_key",
                "clause_order": "0",
                "source_start": "",
                "source_end": "",
                "normalization_status": "generated_from_catalogue_number",
                "validation_status": "auto_validated",
                "identifier_strength": "primary",
                "risk_level": "lowest",
                "search_eligible": "yes",
                "review_reason": "",
                "collision_strain_count": "1",
                "collision_strains": number,
            }
        )

    for clause in clauses:
        clause_type = clause.get("clause_type", "")
        raw_value = clean_text(clause.get("raw_value", ""))
        if clause_type == "collection_list":
            for item in split_collection_payload(raw_value):
                prefix = collection_prefix(item)
                eligible = "yes" if prefix and re.search(r"\d", item) else "no"
                reason = "" if eligible == "yes" else "unrecognised_or_digit_free_collection_identifier"
                identifiers.append(
                    identifier_row(
                        clause,
                        item,
                        "collection_number" if prefix else "collection_candidate",
                        "low" if eligible == "yes" else "high",
                        eligible,
                        reason,
                    )
                )
        elif clause_type == "donor_reference" and raw_value:
            donor_parts = split_collection_payload(raw_value)
            for donor_value in donor_parts:
                prefix = collection_prefix(donor_value)
                has_digit = bool(re.search(r"\d", donor_value))
                eligible = "yes" if has_digit else "no"
                reason = "" if eligible == "yes" else "digit_free_donor_reference_requires_review_before_search"
                identifiers.append(
                    identifier_row(
                        clause,
                        donor_value,
                        "collection_number" if prefix else "donor_reference",
                        "low" if prefix and has_digit else "medium" if has_digit else "high",
                        eligible,
                        reason,
                    )
                )
        elif clause_type in {"isolated_by", "source_of_isolate"}:
            # The complete payload is retained but never searched as a person/source phrase.
            identifiers.append(
                identifier_row(
                    clause,
                    raw_value,
                    "source_reference_raw",
                    "low",
                    "no",
                    "preserved_source_text_not_a_search_identifier",
                )
            )
            for source_identifier, identifier_type in source_clause_identifiers(raw_value):
                identifiers.append(
                    identifier_row(
                        clause,
                        source_identifier,
                        identifier_type,
                        "low" if identifier_type == "collection_number" else "medium",
                        "yes",
                    )
                )
        elif clause.get("parse_status") != "parsed":
            reviews.append(
                {
                    "ncppb_number": clause.get("ncppb_number", ""),
                    "review_type": "other_reference_clause",
                    "risk_level": clause.get("risk_level", "high"),
                    "raw_text": clause.get("raw_clause", ""),
                    "proposed_value": raw_value,
                    "review_reason": clause.get("review_reason", "") or "clause_not_searchable_automatically",
                    "reviewer_decision": "",
                    "reviewer_notes": "",
                }
            )

    collision_map: dict[str, set[str]] = defaultdict(set)
    for row in identifiers:
        if (
            row["identifier_type"] != "ncppb_number"
            and row["identifier_normalized"]
            and row["search_eligible"] == "yes"
        ):
            collision_map[row["identifier_normalized"]].add(row["ncppb_number"])

    for row in identifiers:
        strains_for_id = sorted(collision_map.get(row["identifier_normalized"], {row["ncppb_number"]}))
        row["collision_strain_count"] = str(len(strains_for_id))
        row["collision_strains"] = "; ".join(strains_for_id)
        if len(strains_for_id) > 1:
            row["validation_status"] = "review_required"
            row["risk_level"] = "high"
            row["search_eligible"] = "no"
            row["review_reason"] = "identifier_collision"
            reviews.append(
                {
                    "ncppb_number": row["ncppb_number"],
                    "review_type": "identifier_collision",
                    "risk_level": "high",
                    "raw_text": row["identifier_raw"],
                    "proposed_value": row["identifier_normalized"],
                    "review_reason": f"identifier_maps_to:{row['collision_strains']}",
                    "reviewer_decision": "",
                    "reviewer_notes": "",
                }
            )

    deduplicated: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in identifiers:
        key = (row["ncppb_number"], row["identifier_normalized"], row["identifier_type"])
        deduplicated.setdefault(key, row)
    return list(deduplicated.values()), reviews


def write_identifier_outputs(outdir, identifiers, reviews) -> None:
    write_table(outdir / "strain_identifiers.tsv", identifiers, IDENTIFIER_COLUMNS)
    write_table(outdir / "parser_review_queue.tsv", reviews, REVIEW_COLUMNS)
