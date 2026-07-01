from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .common import clean_text, unique_join, write_table


MANUAL_REVIEW_COLUMNS = [
    "review_priority",
    "ncppb_number",
    "ncppb_current_name",
    "current_accepted_biosamples",
    "review_candidate_biosamples",
    "candidate_organisms",
    "matched_identifiers",
    "matched_identifier_types",
    "matched_fields",
    "evidence_classes",
    "taxonomy_statuses",
    "review_reasons",
    "discovery_tracks",
    "biosample_urls",
    "review_question",
    "reviewer_decision",
    "reviewer_notes",
]

ACCESSION_CHANGE_COLUMNS = [
    "ncppb_number",
    "biosample_accession",
    "change_type",
    "v2_decision",
    "v2_evidence_class",
    "v2_review_or_reject_reason",
    "v2_discovery_tracks",
    "v2_matched_identifier",
    "v2_matched_field",
]

V1_REGRESSION_COLUMNS = [
    "ncppb_number",
    "biosample_accession",
    "rediscovered_by_v2_1_search",
    "rediscovery_tracks",
    "historical_direct_recheck_needed",
    "v2_1_decision",
    "identity_match_status",
    "evidence_class",
    "matched_identifier",
    "matched_field",
    "taxonomy_status",
    "review_reason",
]


def split_values(value: str) -> set[str]:
    return {clean_text(item) for item in re.split(r"\s*;\s*", value or "") if clean_text(item)}


def review_priority(rows: list[dict[str, str]]) -> str:
    reasons = {row.get("review_reason", "") for row in rows}
    if "conflicting_ncppb_identifier" in reasons:
        return "P1"
    if "different_lineage" in reasons:
        return "P1"
    return "P2"


def review_question(rows: list[dict[str, str]]) -> str:
    reasons = {row.get("review_reason", "") for row in rows}
    if "conflicting_ncppb_identifier" in reasons:
        return "Does the BioSample refer to this NCPPB strain despite containing another NCPPB number?"
    if "different_lineage" in reasons:
        return "Is the lineage difference a documented taxonomic revision or a wrong strain link?"
    if "same_genus_different_species" in reasons:
        return "Can the NCPPB and NCBI species names be reconciled as historical/current names for the same strain?"
    if "exact_identifier_only_in_title" in reasons:
        return "Is the title-only exact identifier sufficient when structured identity fields are incomplete?"
    return "Does the structured evidence support retaining this BioSample as a strain-level match?"


def build_manual_review_queue(
    supervisor_rows: list[dict[str, str]], match_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    supervisor = {row["ncppb_number"]: row for row in supervisor_rows}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in match_rows:
        if row.get("manual_review_required") == "yes":
            grouped[row["ncppb_number"]].append(row)
    output: list[dict[str, str]] = []
    for number, rows in grouped.items():
        strain = supervisor.get(number, {})
        output.append(
            {
                "review_priority": review_priority(rows),
                "ncppb_number": number,
                "ncppb_current_name": strain.get("ncppb_current_name", ""),
                "current_accepted_biosamples": strain.get("confirmed_biosample_accessions", ""),
                "review_candidate_biosamples": unique_join(row.get("biosample_accession", "") for row in rows),
                "candidate_organisms": unique_join(row.get("organism", "") for row in rows),
                "matched_identifiers": unique_join(row.get("matched_identifier", "") for row in rows),
                "matched_identifier_types": unique_join(row.get("matched_identifier_type", "") for row in rows),
                "matched_fields": unique_join(row.get("matched_field", "") for row in rows),
                "evidence_classes": unique_join(row.get("evidence_class", "") for row in rows),
                "taxonomy_statuses": unique_join(row.get("taxonomy_status", "") for row in rows),
                "review_reasons": unique_join(row.get("review_reason", "") for row in rows),
                "discovery_tracks": unique_join(row.get("discovery_tracks", "") for row in rows),
                "biosample_urls": unique_join(row.get("source_url", "") for row in rows),
                "review_question": review_question(rows),
                "reviewer_decision": "",
                "reviewer_notes": "",
            }
        )
    return sorted(output, key=lambda row: (row["review_priority"], int(re.search(r"\d+", row["ncppb_number"]).group(0))))


def build_accession_changes(
    v1_rows: list[dict[str, str]],
    v2_rows: list[dict[str, str]],
    match_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    old = {row.get("ncppb_number", ""): split_values(row.get("biosample_accessions", "")) for row in v1_rows}
    new = {row.get("ncppb_number", ""): split_values(row.get("confirmed_biosample_accessions", "")) for row in v2_rows}
    decisions = {
        (row.get("ncppb_number", ""), row.get("biosample_accession", "")): row
        for row in match_rows
    }
    output: list[dict[str, str]] = []
    for number in sorted(set(old) | set(new), key=lambda value: int(re.search(r"\d+", value).group(0))):
        for accession, change_type in [
            *((value, "added_in_v2") for value in sorted(new.get(number, set()) - old.get(number, set()))),
            *((value, "removed_from_v2") for value in sorted(old.get(number, set()) - new.get(number, set()))),
        ]:
            decision = decisions.get((number, accession), {})
            output.append(
                {
                    "ncppb_number": number,
                    "biosample_accession": accession,
                    "change_type": change_type,
                    "v2_decision": decision.get("decision", "not_retrieved_under_v2") if change_type == "removed_from_v2" else decision.get("decision", "accept"),
                    "v2_evidence_class": decision.get("evidence_class", ""),
                    "v2_review_or_reject_reason": decision.get("review_reason", ""),
                    "v2_discovery_tracks": decision.get("discovery_tracks", ""),
                    "v2_matched_identifier": decision.get("matched_identifier", ""),
                    "v2_matched_field": decision.get("matched_field", ""),
                }
            )
    return output


def build_v1_regression_recall_audit(
    v1_rows: list[dict[str, str]], match_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Account for every historical V1 strain-accession pair without treating V1 as truth."""
    matches = {
        (row.get("ncppb_number", ""), row.get("biosample_accession", "").upper()): row
        for row in match_rows
        if row.get("biosample_accession", "")
    }
    output: list[dict[str, str]] = []
    for v1 in v1_rows:
        number = v1.get("ncppb_number", "")
        for accession in sorted(split_values(v1.get("biosample_accessions", ""))):
            row = matches.get((number, accession.upper()), {})
            tracks = split_values(row.get("discovery_tracks", ""))
            current_tracks = sorted(tracks & {"ncppb_number", "other_references"})
            output.append(
                {
                    "ncppb_number": number,
                    "biosample_accession": accession,
                    "rediscovered_by_v2_1_search": "yes" if current_tracks else "no",
                    "rediscovery_tracks": "; ".join(current_tracks),
                    "historical_direct_recheck_needed": "yes" if "historical_v1_recheck" in tracks else "no",
                    "v2_1_decision": row.get("decision", "not_evaluated"),
                    "identity_match_status": row.get("identity_match_status", ""),
                    "evidence_class": row.get("evidence_class", ""),
                    "matched_identifier": row.get("matched_identifier", ""),
                    "matched_field": row.get("matched_field", ""),
                    "taxonomy_status": row.get("taxonomy_status", ""),
                    "review_reason": row.get("review_reason", ""),
                }
            )
    return output


def write_analysis_outputs(
    outdir: Path,
    manual_rows: list[dict[str, str]],
    accession_changes: list[dict[str, str]],
    v1_rows: list[dict[str, str]],
    v2_rows: list[dict[str, str]],
    match_rows: list[dict[str, str]],
    v1_regression_rows: list[dict[str, str]],
) -> None:
    write_table(outdir / "manual_review_queue.tsv", manual_rows, MANUAL_REVIEW_COLUMNS)
    write_table(outdir / "v1_v2_accession_changes.tsv", accession_changes, ACCESSION_CHANGE_COLUMNS)
    write_table(outdir / "v1_regression_recall_audit.tsv", v1_regression_rows, V1_REGRESSION_COLUMNS)
    old_strains = {row["ncppb_number"] for row in v1_rows if split_values(row.get("biosample_accessions", ""))}
    new_strains = {row["ncppb_number"] for row in v2_rows if split_values(row.get("confirmed_biosample_accessions", ""))}
    accepted = [row for row in match_rows if row.get("decision") == "accept"]
    both = sum("ncppb_number" in row.get("discovery_tracks", "") and "other_references" in row.get("discovery_tracks", "") for row in accepted)
    ncppb_only = sum(row.get("discovery_tracks") == "ncppb_number" for row in accepted)
    other_only = sum(row.get("discovery_tracks") == "other_references" for row in accepted)
    historical_only = sum(row.get("discovery_tracks") == "historical_v1_recheck" for row in accepted)
    added = sum(row["change_type"] == "added_in_v2" for row in accession_changes)
    removed = sum(row["change_type"] == "removed_from_v2" for row in accession_changes)
    historical_pairs = len(v1_regression_rows)
    rediscovered_pairs = sum(row["rediscovered_by_v2_1_search"] == "yes" for row in v1_regression_rows)
    direct_recheck_pairs = sum(row["historical_direct_recheck_needed"] == "yes" for row in v1_regression_rows)
    unevaluated_pairs = sum(row["v2_1_decision"] == "not_evaluated" for row in v1_regression_rows)
    lines = [
        "# V1 versus V2.1 BioSample change analysis",
        "",
        f"- V1 strains with confirmed BioSamples: {len(old_strains)}",
        f"- V2.1 strains with confirmed BioSamples: {len(new_strains)}",
        f"- Confirmed in both versions: {len(old_strains & new_strains)}",
        f"- Newly confirmed at strain level in V2.1: {len(new_strains - old_strains)}",
        f"- No longer confirmed at strain level in V2.1: {len(old_strains - new_strains)}",
        f"- Added BioSample accessions in V2.1: {added}",
        f"- Removed BioSample accessions in V2.1: {removed}",
        "",
        "## Historical-pair retrieval control",
        "",
        f"- V1 strain-accession pairs audited: {historical_pairs}",
        f"- Rediscovered by the V2.1 NCPPB/Other-reference searches: {rediscovered_pairs}",
        f"- Required direct historical-accession recheck: {direct_recheck_pairs}",
        f"- Not evaluated after the safety recheck: {unevaluated_pairs}",
        "",
        "## V2.1 accepted BioSamples by discovery route",
        "",
        f"- NCPPB-number track only: {ncppb_only}",
        f"- Other-references track only: {other_only}",
        f"- Found by both tracks: {both}",
        f"- Restored only by direct V1 accession regression recheck: {historical_only}",
        "",
        "Removed accessions are not assumed to be false. `v1_v2_accession_changes.tsv` records whether each was rejected, routed to review, or not retrieved under V2.1.",
    ]
    (outdir / "v1_v2_change_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
