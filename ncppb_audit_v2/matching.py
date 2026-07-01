from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .common import clean_text, unique_join, write_table


IDENTITY_FIELDS = [
    "strain",
    "isolate",
    "culture_collection",
    "bio_material",
    "sample_name",
    "identity_aliases",
    "identifiers",
]

MATCH_COLUMNS = [
    "ncppb_number",
    "biosample_accession",
    "ncbi_uid",
    "discovery_tracks",
    "discovery_tiers",
    "organism",
    "taxid",
    "matched_identifier",
    "matched_identifier_type",
    "identifier_strength",
    "matched_field",
    "evidence_class",
    "identity_match_status",
    "taxonomy_status",
    "identity_review_required",
    "taxonomy_review_required",
    "manual_review_required",
    "decision",
    "review_reason",
    "conflicting_ncppb_numbers",
    "source_url",
]

SUPERVISOR_COLUMNS = [
    "ncppb_number",
    "ncppb_current_name",
    "snapshot_status",
    "all_searchable_identifiers",
    "confirmed_biosample_accessions",
    "provisional_biosample_accessions",
    "ncppb_track_biosample_accessions",
    "other_references_track_biosample_accessions",
    "historical_v1_recheck_biosample_accessions",
    "assembly_accessions",
    "assembly_levels",
    "sra_run_accessions",
    "bioproject_accessions",
    "provisional_assembly_accessions",
    "provisional_sra_run_accessions",
    "provisional_bioproject_accessions",
    "sequence_availability_category",
    "identity_match_status",
    "taxonomy_consistency_status",
    "taxonomy_review_required",
    "manual_review_required",
    "review_reason",
    "accepted_candidate_count",
    "review_candidate_count",
    "rejected_candidate_count",
]

COMPARISON_COLUMNS = [
    "ncppb_number",
    "snapshot_status",
    "v1_sequence_category",
    "v2_sequence_category",
    "sequence_category_changed",
    "v1_biosample_accessions",
    "v2_biosample_accessions",
    "biosample_accessions_changed",
    "v1_assembly_accessions",
    "v2_assembly_accessions",
    "assembly_accessions_changed",
    "v1_sra_run_accessions",
    "v2_sra_run_accessions",
    "sra_accessions_changed",
    "v2_ncppb_track_matches",
    "v2_other_references_track_matches",
]


def identifier_pattern(value: str) -> re.Pattern[str] | None:
    chunks = re.findall(r"[A-Za-z]+|\d+", clean_text(value))
    if not chunks:
        return None
    body = r"[\s:._/\-]*".join(re.escape(chunk) for chunk in chunks)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


def exact_field_match(identifier: str, candidate: dict[str, str]) -> str:
    pattern = identifier_pattern(identifier)
    if pattern is None:
        return ""
    for field in IDENTITY_FIELDS:
        if pattern.search(candidate.get(field, "")):
            return field
    return ""


def title_match(identifier: str, candidate: dict[str, str]) -> bool:
    pattern = identifier_pattern(identifier)
    return bool(pattern and pattern.search(candidate.get("title", "")))


def separated_terms_only(identifier: str, candidate: dict[str, str]) -> bool:
    chunks = [chunk.upper() for chunk in re.findall(r"[A-Za-z0-9]+", identifier)]
    if len(chunks) < 2:
        return False
    combined = " ".join(candidate.get(field, "") for field in [*IDENTITY_FIELDS, "title"])
    upper = combined.upper()
    return all(re.search(rf"(?<![A-Z0-9]){re.escape(chunk)}(?![A-Z0-9])", upper) for chunk in chunks)


def binomial(value: str) -> str:
    match = re.search(r"\b([A-Z][A-Za-z-]+)\s+([a-z][A-Za-z0-9_-]+)", value or "")
    return f"{match.group(1).lower()} {match.group(2).lower()}" if match else ""


def binomials(value: str) -> list[str]:
    return [
        f"{genus.lower()} {species.lower()}"
        for genus, species in re.findall(r"\b([A-Z][A-Za-z-]+)\s+([a-z][A-Za-z0-9_-]+)", value or "")
    ]


def taxonomy_status(strain: dict[str, str], candidate: dict[str, str]) -> str:
    observed = binomial(candidate.get("organism", ""))
    expected_values = [
        strain.get("canonical_name", ""),
        strain.get("current_name_raw", ""),
        strain.get("name_as_received", ""),
        strain.get("alternative_names", ""),
    ]
    expected: list[str] = []
    for value in expected_values:
        for name in binomials(value):
            if name not in expected:
                expected.append(name)
    if not observed or not expected:
        return "taxonomy_unresolved"
    if observed == expected[0]:
        return "same_name"
    if observed in expected[1:]:
        return "compatible_synonym"
    observed_genus = observed.split()[0]
    expected_genera = {value.split()[0] for value in expected}
    if observed_genus in expected_genera:
        return "same_genus_different_species"
    return "different_lineage"


def find_conflicting_ncppb(candidate: dict[str, str], expected_number: str) -> list[str]:
    expected_match = re.search(r"\d+", expected_number)
    expected = expected_match.group(0) if expected_match else ""
    combined = " ".join(candidate.get(field, "") for field in IDENTITY_FIELDS)
    found = set(re.findall(r"\bNCPPB\s*[-:_]?\s*(\d+)\b", combined, flags=re.IGNORECASE))
    return sorted(found - {expected}, key=int)


def effective_identifier_strength(identifier: dict[str, str]) -> str:
    """Keep old/test rows safe while treating the catalogue primary key as primary evidence."""
    explicit = identifier.get("identifier_strength", "")
    if explicit:
        return explicit
    identifier_type = identifier.get("identifier_type", "")
    if identifier_type == "ncppb_number":
        return "primary"
    if identifier_type == "collection_number":
        return "strong"
    return "medium"


def classify_candidate(
    strain: dict[str, str], candidate: dict[str, str], identifiers: list[dict[str, str]]
) -> dict[str, str]:
    if candidate.get("status") == "error":
        return {
            "evidence_class": "query_or_fetch_error",
            "identity_match_status": "unresolved_query_error",
            "taxonomy_status": "taxonomy_unresolved",
            "identity_review_required": "yes",
            "taxonomy_review_required": "yes",
            "manual_review_required": "yes",
            "decision": "review",
            "review_reason": candidate.get("error", "query_or_fetch_error"),
        }
    conflicts = find_conflicting_ncppb(candidate, strain.get("ncppb_number", ""))
    searchable = [row for row in identifiers if row.get("search_eligible") == "yes"]
    strength_rank = {"primary": 0, "strong": 1, "medium": 2, "weak": 3, "not_searchable": 4}
    searchable.sort(key=lambda row: strength_rank.get(effective_identifier_strength(row), 9))
    for identifier in searchable:
        raw = identifier.get("identifier_raw", "")
        field = exact_field_match(raw, candidate)
        if not field:
            continue
        tax_status = taxonomy_status(strain, candidate)
        strength = effective_identifier_strength(identifier)
        strong_identifier = strength in {"primary", "strong"}
        taxonomy_review = tax_status not in {"same_name", "compatible_synonym"}
        if conflicts:
            decision = "review"
            reason = "conflicting_ncppb_identifier"
        elif strong_identifier:
            decision = "accept"
            reason = tax_status if taxonomy_review else ""
        else:
            decision = "review"
            reason = "medium_identifier_requires_corroboration"
            if taxonomy_review:
                reason += f"; {tax_status}"
        identity_status = (
            "confirmed_exact_ncppb_identifier"
            if strength == "primary" and not conflicts
            else "confirmed_exact_collection_identifier"
            if strength == "strong" and not conflicts
            else "provisional_exact_other_reference_identifier"
            if not conflicts
            else "conflicting_exact_identifier"
        )
        identity_review = bool(conflicts) or not strong_identifier
        return {
            "matched_identifier": raw,
            "matched_identifier_type": identifier.get("identifier_type", ""),
            "identifier_strength": strength,
            "matched_field": field,
            "evidence_class": "structured_exact_identifier",
            "identity_match_status": identity_status,
            "taxonomy_status": tax_status,
            "identity_review_required": "yes" if identity_review else "no",
            "taxonomy_review_required": "yes" if taxonomy_review else "no",
            "manual_review_required": "yes" if identity_review or taxonomy_review else "no",
            "decision": decision,
            "review_reason": reason,
            "conflicting_ncppb_numbers": "; ".join(conflicts),
        }

    for identifier in searchable:
        raw = identifier.get("identifier_raw", "")
        if title_match(raw, candidate):
            strength = effective_identifier_strength(identifier)
            strong_identifier = strength in {"primary", "strong"}
            return {
                "matched_identifier": raw,
                "matched_identifier_type": identifier.get("identifier_type", ""),
                "identifier_strength": strength,
                "matched_field": "title",
                "evidence_class": "unstructured_exact_identifier",
                "identity_match_status": "unstructured_exact_identifier_only",
                "taxonomy_status": taxonomy_status(strain, candidate),
                "identity_review_required": "yes",
                "taxonomy_review_required": "yes" if taxonomy_status(strain, candidate) not in {"same_name", "compatible_synonym"} else "no",
                "manual_review_required": "yes",
                "decision": "review",
                "review_reason": "exact_identifier_only_in_title",
                "conflicting_ncppb_numbers": "; ".join(conflicts),
            }
    if any(separated_terms_only(row.get("identifier_raw", ""), candidate) for row in searchable):
        evidence = "separated_query_terms_only"
    else:
        evidence = "no_exact_identifier"
    return {
        "evidence_class": evidence,
        "identity_match_status": evidence,
        "taxonomy_status": taxonomy_status(strain, candidate),
        "identity_review_required": "no",
        "taxonomy_review_required": "no",
        "manual_review_required": "no",
        "decision": "reject",
        "review_reason": evidence,
        "conflicting_ncppb_numbers": "; ".join(conflicts),
    }


def match_candidates(
    strains: list[dict[str, str]],
    identifiers: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> list[dict[str, str]]:
    strain_map = {row["ncppb_number"]: row for row in strains}
    ids_by_strain: dict[str, list[dict[str, str]]] = defaultdict(list)
    for identifier in identifiers:
        ids_by_strain[identifier["ncppb_number"]].append(identifier)
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for candidate in candidates:
        accession_key = candidate.get("biosample_accession", "") or candidate.get("ncbi_uid", "")
        if candidate.get("status") == "no_hit" or not accession_key:
            continue
        grouped[(candidate.get("ncppb_number", ""), accession_key)].append(candidate)

    rows: list[dict[str, str]] = []
    for (number, _), discoveries in grouped.items():
        representative = next((row for row in discoveries if row.get("status") == "ok"), discoveries[0])
        evidence = classify_candidate(strain_map.get(number, {}), representative, ids_by_strain.get(number, []))
        rows.append(
            {
                "ncppb_number": number,
                "biosample_accession": representative.get("biosample_accession", ""),
                "ncbi_uid": representative.get("ncbi_uid", ""),
                "discovery_tracks": unique_join(row.get("query_track", "") for row in discoveries),
                "discovery_tiers": unique_join(row.get("query_tier", "") for row in discoveries),
                "organism": representative.get("organism", ""),
                "taxid": representative.get("taxid", ""),
                **evidence,
                "source_url": representative.get("source_url", ""),
            }
        )
    return rows


def sequence_category(assembly_levels: list[str], has_sra: bool, has_biosample: bool) -> str:
    lowered = " ".join(assembly_levels).lower()
    if "complete genome" in lowered or re.search(r"\bcomplete\b", lowered):
        return "complete_genome_available"
    if "chromosome" in lowered:
        return "chromosome_level_assembly_available"
    if assembly_levels:
        return "draft_assembly_available"
    if has_sra:
        return "raw_reads_only"
    if has_biosample:
        return "biosample_metadata_only_no_linked_sequence"
    return "no_confirmed_public_data"


def sequence_bioproject_accessions(link_rows: list[dict[str, str]]) -> list[str]:
    """Return projects embedded in Assembly/SRA provenance, excluding generic ELink-only projects."""
    projects: list[str] = []
    for row in link_rows:
        record = {}
        try:
            record = json.loads(row.get("extra_json", "") or "{}")
        except json.JSONDecodeError:
            pass
        if row.get("linked_database") == "assembly":
            for item in record.get("gb_bioprojects", []) if isinstance(record, dict) else []:
                if isinstance(item, dict) and item.get("bioprojectaccn"):
                    projects.append(clean_text(item["bioprojectaccn"]))
        elif row.get("linked_database") == "sra":
            expxml = str(record.get("expxml", "")) if isinstance(record, dict) else ""
            projects.extend(re.findall(r"<Bioproject>([^<]+)</Bioproject>", expxml, flags=re.IGNORECASE))
    return projects


def build_supervisor_table(
    strains: list[dict[str, str]],
    identifiers: list[dict[str, str]],
    match_rows: list[dict[str, str]],
    linked_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    ids_by_strain: dict[str, list[str]] = defaultdict(list)
    for identifier in identifiers:
        if identifier.get("search_eligible") == "yes":
            ids_by_strain[identifier["ncppb_number"]].append(identifier["identifier_raw"])
    matches_by_strain: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in match_rows:
        matches_by_strain[row["ncppb_number"]].append(row)
    links_by_strain: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in linked_rows:
        if row.get("status") == "ok":
            links_by_strain[row["ncppb_number"]].append(row)

    output: list[dict[str, str]] = []
    for strain in strains:
        number = strain["ncppb_number"]
        strain_matches = matches_by_strain.get(number, [])
        accepted = [row for row in strain_matches if row.get("decision") == "accept"]
        review = [row for row in strain_matches if row.get("decision") == "review"]
        rejected = [row for row in strain_matches if row.get("decision") == "reject"]
        accepted_accessions = [row.get("biosample_accession", "") for row in accepted]
        provisional_accessions = [row.get("biosample_accession", "") for row in review]
        ncppb_track = [
            row.get("biosample_accession", "")
            for row in accepted
            if "ncppb_number" in row.get("discovery_tracks", "")
        ]
        other_track = [
            row.get("biosample_accession", "")
            for row in accepted
            if "other_references" in row.get("discovery_tracks", "")
        ]
        historical_track = [
            row.get("biosample_accession", "")
            for row in accepted
            if "historical_v1_recheck" in row.get("discovery_tracks", "")
        ]
        accepted_set = set(accepted_accessions)
        provisional_set = set(provisional_accessions)
        links = [row for row in links_by_strain.get(number, []) if row.get("biosample_accession", "") in accepted_set]
        provisional_links = [
            row for row in links_by_strain.get(number, []) if row.get("biosample_accession", "") in provisional_set
        ]
        assemblies = [row for row in links if row.get("linked_database") == "assembly"]
        sra = [row for row in links if row.get("linked_database") == "sra"]
        projects = sequence_bioproject_accessions(links)
        provisional_assemblies = [row for row in provisional_links if row.get("linked_database") == "assembly"]
        provisional_sra = [row for row in provisional_links if row.get("linked_database") == "sra"]
        provisional_projects = sequence_bioproject_accessions(provisional_links)
        levels = [row.get("assembly_level", "") for row in assemblies if row.get("assembly_level", "")]
        category = sequence_category(levels, bool(sra), bool(accepted))
        if review and not accepted:
            category = "ambiguous_needs_review"
        taxonomy_values = [row.get("taxonomy_status", "") for row in [*accepted, *review]]
        manual_rows = [row for row in [*accepted, *review] if row.get("manual_review_required") == "yes"]
        identity_values = [row.get("identity_match_status", "") for row in [*accepted, *review]]
        output.append(
            {
                "ncppb_number": number,
                "ncppb_current_name": strain.get("current_name_raw", ""),
                "snapshot_status": "present_in_v2_snapshot",
                "all_searchable_identifiers": unique_join(ids_by_strain.get(number, [])),
                "confirmed_biosample_accessions": unique_join(accepted_accessions),
                "provisional_biosample_accessions": unique_join(provisional_accessions),
                "ncppb_track_biosample_accessions": unique_join(ncppb_track),
                "other_references_track_biosample_accessions": unique_join(other_track),
                "historical_v1_recheck_biosample_accessions": unique_join(historical_track),
                "assembly_accessions": unique_join(row.get("linked_accession", "") for row in assemblies),
                "assembly_levels": unique_join(levels),
                "sra_run_accessions": unique_join(row.get("linked_accession", "") for row in sra),
                "bioproject_accessions": unique_join(projects),
                "provisional_assembly_accessions": unique_join(row.get("linked_accession", "") for row in provisional_assemblies),
                "provisional_sra_run_accessions": unique_join(row.get("linked_accession", "") for row in provisional_sra),
                "provisional_bioproject_accessions": unique_join(provisional_projects),
                "sequence_availability_category": category,
                "identity_match_status": unique_join(identity_values) or "no_confirmed_identity_match",
                "taxonomy_consistency_status": unique_join(taxonomy_values) or "not_assessed_no_confirmed_match",
                "taxonomy_review_required": "yes" if any(row.get("taxonomy_review_required") == "yes" for row in [*accepted, *review]) else "no",
                "manual_review_required": "yes" if manual_rows else "no",
                "review_reason": unique_join(row.get("review_reason", "") for row in manual_rows),
                "accepted_candidate_count": str(len(accepted)),
                "review_candidate_count": str(len(review)),
                "rejected_candidate_count": str(len(rejected)),
            }
        )
    return output


def compare_v1_v2(
    v1_rows: list[dict[str, str]],
    v2_rows: list[dict[str, str]],
    snapshot_diff: list[dict[str, str]],
) -> list[dict[str, str]]:
    old = {row.get("ncppb_number", ""): row for row in v1_rows}
    new = {row.get("ncppb_number", ""): row for row in v2_rows}
    statuses = {row.get("ncppb_number", ""): row.get("snapshot_status", "") for row in snapshot_diff}
    numbers = sorted(set(old) | set(new), key=lambda value: int(re.search(r"\d+", value).group(0)))
    output: list[dict[str, str]] = []
    category_aliases = {
        "no_confirmed_public_sequence_data": "no_confirmed_public_data",
        "ambiguous_candidate_records_need_review": "ambiguous_needs_review",
    }

    def normalized_category(value: str) -> str:
        return category_aliases.get(clean_text(value), clean_text(value))

    def accession_set(value: str) -> set[str]:
        return {clean_text(item) for item in re.split(r"\s*;\s*", value or "") if clean_text(item)}

    for number in numbers:
        v1 = old.get(number, {})
        v2 = new.get(number, {})
        v1_category = v1.get("sequence_data_category", v1.get("sequence_availability_category", ""))
        v2_category = v2.get("sequence_availability_category", "")
        v1_bio = v1.get("biosample_accessions", v1.get("confirmed_biosample_accessions", ""))
        v2_bio = v2.get("confirmed_biosample_accessions", "")
        v1_assembly = v1.get("assembly_accessions", "")
        v2_assembly = v2.get("assembly_accessions", "")
        v1_sra = v1.get("run_accessions", v1.get("sra_run_accessions", ""))
        v2_sra = v2.get("sra_run_accessions", "")
        present_both = number in old and number in new
        output.append(
            {
                "ncppb_number": number,
                "snapshot_status": statuses.get(number, "present_in_both" if present_both else ""),
                "v1_sequence_category": v1_category,
                "v2_sequence_category": v2_category,
                "sequence_category_changed": "yes" if present_both and normalized_category(v1_category) != normalized_category(v2_category) else "no",
                "v1_biosample_accessions": v1_bio,
                "v2_biosample_accessions": v2_bio,
                "biosample_accessions_changed": "yes" if present_both and accession_set(v1_bio) != accession_set(v2_bio) else "no",
                "v1_assembly_accessions": v1_assembly,
                "v2_assembly_accessions": v2_assembly,
                "assembly_accessions_changed": "yes" if present_both and accession_set(v1_assembly) != accession_set(v2_assembly) else "no",
                "v1_sra_run_accessions": v1_sra,
                "v2_sra_run_accessions": v2_sra,
                "sra_accessions_changed": "yes" if present_both and accession_set(v1_sra) != accession_set(v2_sra) else "no",
                "v2_ncppb_track_matches": v2.get("ncppb_track_biosample_accessions", ""),
                "v2_other_references_track_matches": v2.get("other_references_track_biosample_accessions", ""),
            }
        )
    return output


def write_matching_outputs(outdir: Path, match_rows, supervisor_rows, comparison_rows) -> None:
    write_table(outdir / "biosample_match_decisions.tsv", match_rows, MATCH_COLUMNS)
    write_table(outdir / "supervisor_sequence_availability.tsv", supervisor_rows, SUPERVISOR_COLUMNS)
    write_table(outdir / "v1_v2_comparison.tsv", comparison_rows, COMPARISON_COLUMNS)
