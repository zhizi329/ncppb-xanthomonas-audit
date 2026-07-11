from __future__ import annotations

import re
from collections import defaultdict

from .common import clean_text, sha256_text, stable_json, write_table
from .identifiers import collection_prefix


QUERY_COLUMNS = [
    "query_id",
    "ncppb_number",
    "query_track",
    "query_tier",
    "identifier_raw",
    "identifier_normalized",
    "identifier_type",
    "identifier_strength",
    "expected_genus",
    "retrieval_strategy",
    "query_variants_json",
    "local_match_variants_json",
    "ncbi_database",
    "query_term",
    "page_size",
    "max_records",
]


def ncbi_quote(value: str) -> str:
    return value.replace('"', "")


def identifier_variants(value: str, identifier_type: str) -> list[str]:
    raw = clean_text(value)
    if identifier_type == "ncppb_number":
        digits_match = re.search(r"\d+", raw)
        if not digits_match:
            return [raw]
        digits = digits_match.group(0)
        return [f"NCPPB {digits}", f"NCPPB{digits}", f"NCPPB:{digits}"]

    match = re.match(r"^([A-Za-z][A-Za-z0-9-]{1,15})\s*[-:_]?\s*(.+)$", raw)
    if match and re.search(r"\d", match.group(2)):
        prefix = match.group(1)
        suffix = clean_text(match.group(2))
        variants = [f"{prefix} {suffix}", f"{prefix}{suffix}", f"{prefix}:{suffix}"]
    else:
        variants = [raw]
    seen: set[str] = set()
    return [value for value in variants if value and not (value.upper() in seen or seen.add(value.upper()))]


def build_query_term(variants: list[str], genus: str = "") -> str:
    phrase_terms = [f'"{ncbi_quote(value)}"[All Fields]' for value in variants]
    identifier_term = f"({' OR '.join(phrase_terms)})"
    if genus:
        return f'{identifier_term} AND "{ncbi_quote(genus)}"[Organism]'
    return identifier_term


def build_exact_ncppb_term(variants: list[str]) -> str:
    # [All Fields] invokes NCBI automatic term mapping for some strain names
    # (for example, NCPPB 1974 expands to an organism query).  [Text Word]
    # keeps each complete identifier literal while still indexing compact
    # aliases such as NCPPB4346.
    return "(" + " OR ".join(f'"{ncbi_quote(value)}"[Text Word]' for value in variants) + ")"


def build_medium_retrieval_term(value: str, genus: str) -> str:
    chunks = re.findall(r"[A-Za-z]+|\d+", clean_text(value))
    identifier_term = " AND ".join(f"{ncbi_quote(chunk)}[All Fields]" for chunk in chunks)
    if genus:
        return f'({identifier_term}) AND "{ncbi_quote(genus)}"[Organism]'
    return f"({identifier_term})"


def build_query_plan(
    strains: list[dict[str, str]], identifiers: list[dict[str, str]]
) -> list[dict[str, str]]:
    strain_map = {row["ncppb_number"]: row for row in strains}
    rows: list[dict[str, str]] = []
    # BioSample's Entrez index can report QuotedPhraseNotFound even when a
    # structured field contains "NCPPB 45". Harvest the trusted NCPPB prefix
    # once, then map complete bounded identifiers locally in structured fields.
    genera = sorted({row.get("expected_genus", "") for row in strains if row.get("expected_genus", "")})
    prefix_tiers = [(f"expected_genus:{genus}", genus) for genus in genera]
    prefix_tiers.append(("unfiltered_fallback", ""))
    for tier, tier_genus in prefix_tiers:
        payload = {"track": "ncppb_number", "tier": tier, "genus": tier_genus, "strategy": "prefix_harvest"}
        term = "NCPPB[All Fields]"
        if tier_genus:
            term += f' AND "{ncbi_quote(tier_genus)}"[Organism]'
        rows.append(
            {
                "query_id": sha256_text(stable_json(payload))[:20],
                "ncppb_number": "ALL_NCPPB",
                "query_track": "ncppb_number",
                "query_tier": tier,
                "identifier_raw": "NCPPB",
                "identifier_normalized": "NCPPB",
                "identifier_type": "ncppb_prefix_harvest",
                "identifier_strength": "primary",
                "expected_genus": tier_genus,
                "retrieval_strategy": "trusted_prefix_harvest_then_structured_exact_local_mapping",
                "query_variants_json": stable_json(["NCPPB"]),
                "local_match_variants_json": stable_json(["NCPPB {number}", "NCPPB{number}", "NCPPB:{number}"]),
                "ncbi_database": "biosample",
                "query_term": term,
                "page_size": "5000",
                "max_records": "10000",
            }
        )

    # A prefix harvest is efficient, but Entrez tokenisation is not complete:
    # for example, an accession can be returned by NCPPB4346 while being absent
    # from NCPPB[All Fields].  Therefore every catalogue primary key also gets
    # one bounded full-identifier query.  This is not the forbidden
    # NCPPB[... ] AND number[...] construction.
    for strain in strains:
        number = strain.get("ncppb_number", "")
        variants = identifier_variants(number, "ncppb_number")
        payload = {
            "track": "ncppb_number",
            "tier": "exact_full_identifier",
            "number": number,
            "variants": variants,
        }
        rows.append(
            {
                "query_id": sha256_text(stable_json(payload))[:20],
                "ncppb_number": number,
                "query_track": "ncppb_number",
                "query_tier": "exact_full_identifier",
                "identifier_raw": number,
                "identifier_normalized": re.sub(r"\W+", "", number).upper(),
                "identifier_type": "ncppb_number",
                "identifier_strength": "primary",
                "expected_genus": strain.get("expected_genus", ""),
                "retrieval_strategy": "full_ncppb_identifier_variants_then_structured_exact_local_validation",
                "query_variants_json": stable_json(variants),
                "local_match_variants_json": stable_json(variants),
                "ncbi_database": "biosample",
                "query_term": build_exact_ncppb_term(variants),
                "page_size": "100",
                "max_records": "500",
            }
        )

    collection_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    seen_medium_retrievals: set[tuple[str, str, str]] = set()
    for identifier in identifiers:
        if identifier.get("search_eligible") != "yes" or identifier.get("identifier_type") != "collection_number":
            continue
        prefix = collection_prefix(identifier.get("identifier_raw", ""))
        genus = strain_map.get(identifier.get("ncppb_number", ""), {}).get("expected_genus", "")
        if prefix and genus:
            collection_groups[(prefix, genus)].append(identifier)

    for (prefix, genus), group in sorted(collection_groups.items()):
        payload = {
            "track": "other_references",
            "tier": f"collection_prefix:{prefix}:{genus}",
            "prefix": prefix,
            "genus": genus,
            "strategy": "collection_prefix_harvest",
        }
        rows.append(
            {
                "query_id": sha256_text(stable_json(payload))[:20],
                "ncppb_number": f"ALL_OTHER_PREFIX:{prefix}",
                "query_track": "other_references",
                "query_tier": f"expected_genus:{genus}",
                "identifier_raw": prefix,
                "identifier_normalized": prefix,
                "identifier_type": "collection_prefix_harvest",
                "identifier_strength": "strong",
                "expected_genus": genus,
                "retrieval_strategy": "trusted_collection_prefix_harvest_then_structured_exact_local_mapping",
                "query_variants_json": stable_json([prefix]),
                "local_match_variants_json": stable_json(sorted({item["identifier_raw"] for item in group})),
                "ncbi_database": "biosample",
                "query_term": f'{prefix}[All Fields] AND "{ncbi_quote(genus)}"[Organism]',
                "page_size": "5000",
                "max_records": "10000",
            }
        )

    for identifier in identifiers:
        if identifier.get("search_eligible") != "yes":
            continue
        number = identifier.get("ncppb_number", "")
        strain = strain_map.get(number, {})
        identifier_type = identifier.get("identifier_type", "")
        if identifier_type in {"ncppb_number", "collection_number"}:
            continue
        if identifier.get("identifier_strength") != "medium":
            continue
        track = "other_references"
        variants = identifier_variants(identifier.get("identifier_raw", ""), identifier_type)
        for tier, genus in [("expected_genus", strain.get("expected_genus", ""))]:
            retrieval_key = (number, identifier.get("identifier_normalized", ""), genus)
            if retrieval_key in seen_medium_retrievals:
                continue
            seen_medium_retrievals.add(retrieval_key)
            payload = {
                "ncppb_number": number,
                "track": track,
                "tier": tier,
                "identifier": identifier.get("identifier_normalized", ""),
                "variants": variants,
                "genus": genus,
            }
            rows.append(
                {
                    "query_id": sha256_text(stable_json(payload))[:20],
                    "ncppb_number": number,
                    "query_track": track,
                    "query_tier": tier,
                    "identifier_raw": identifier.get("identifier_raw", ""),
                    "identifier_normalized": identifier.get("identifier_normalized", ""),
                    "identifier_type": identifier_type,
                    "identifier_strength": identifier.get("identifier_strength", "medium"),
                    "expected_genus": strain.get("expected_genus", ""),
                    "retrieval_strategy": "bounded_terms_candidate_retrieval_then_structured_exact_local_mapping",
                    "query_variants_json": stable_json(variants),
                    "local_match_variants_json": stable_json(variants),
                    "ncbi_database": "biosample",
                    "query_term": build_medium_retrieval_term(identifier.get("identifier_raw", ""), genus),
                    "page_size": "500",
                    "max_records": "2000",
                }
            )
    return rows


def write_query_plan(outdir, rows) -> None:
    write_table(outdir / "ncbi_query_plan.tsv", rows, QUERY_COLUMNS)
