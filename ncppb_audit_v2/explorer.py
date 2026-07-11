from __future__ import annotations

import re
from pathlib import Path

from .common import clean_text, write_table


EXPLORER_COLUMNS = [
    "ncppb_number",
    "snapshot_status",
    "ncppb_current_name",
    "expected_genus",
    "scope_status",
    "catalogue_host",
    "catalogue_country",
    "ncbi_biosample_match_count",
    "ncbi_assembly_count",
    "ncbi_sra_run_count",
    "ncbi_bioproject_count",
    "ncbi_sequence_resource_count",
    "ncbi_record_match_count",
    "ncbi_eligible_assembly_count",
    "ncbi_eligible_sra_run_count",
    "ncbi_eligible_sequence_resource_count",
    "ncbi_taxonomy_blocked_resource_count",
    "has_confirmed_ncbi_data",
    "ncbi_data_status",
    "sequence_availability_category",
    "phylogeny_readiness",
    "manual_review_required",
    "confirmed_biosample_accessions",
    "linked_assembly_accessions",
    "linked_sra_run_accessions",
    "assembly_accessions",
    "sra_run_accessions",
    "bioproject_accessions",
    "taxonomy_blocked_biosample_accessions",
]


def split_accessions(value: str) -> set[str]:
    return {clean_text(item) for item in re.split(r"\s*;\s*", value or "") if clean_text(item)}


def build_explorer_table(
    supervisor_rows: list[dict[str, str]],
    snapshot_diff: list[dict[str, str]],
    phylogeny_rows: list[dict[str, str]],
    resource_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build a display-ready union table with explicit numeric NCBI counts."""
    supervisors = {row.get("ncppb_number", ""): row for row in supervisor_rows}
    phylogeny = {row.get("ncppb_number", ""): row for row in phylogeny_rows}
    snapshot = {row.get("ncppb_number", ""): row for row in snapshot_diff}
    resources_by_strain: dict[str, list[dict[str, str]]] = {}
    for row in resource_rows or []:
        resources_by_strain.setdefault(row.get("ncppb_number", ""), []).append(row)
    numbers = sorted(
        set(supervisors) | set(snapshot),
        key=lambda value: int(re.search(r"\d+", value).group(0)),
    )
    output: list[dict[str, str]] = []
    for number in numbers:
        supervisor = supervisors.get(number, {})
        diff = snapshot.get(number, {})
        phylo = phylogeny.get(number, {})
        biosamples = split_accessions(supervisor.get("confirmed_biosample_accessions", ""))
        strain_resources = [
            row for row in resources_by_strain.get(number, [])
            if row.get("evidence_status") == "confirmed"
        ]
        if strain_resources:
            assemblies = {
                row.get("resource_accession", "") for row in strain_resources
                if row.get("resource_type") == "assembly" and row.get("resource_accession")
            }
            sra = {
                row.get("resource_accession", "") for row in strain_resources
                if row.get("resource_type") == "sra_run" and row.get("resource_accession")
            }
            projects = {
                row.get("resource_accession", "") for row in strain_resources
                if row.get("resource_type") == "bioproject" and row.get("resource_accession")
            }
        else:
            assemblies = split_accessions(supervisor.get("assembly_accessions", ""))
            sra = split_accessions(supervisor.get("sra_run_accessions", ""))
            projects = split_accessions(supervisor.get("bioproject_accessions", ""))
        eligible_assemblies = split_accessions(supervisor.get("assembly_accessions", ""))
        eligible_sra = split_accessions(supervisor.get("sra_run_accessions", ""))
        all_records = biosamples | assemblies | sra | projects
        sequence_records = assemblies | sra
        eligible_sequence_records = eligible_assemblies | eligible_sra
        blocked_resources = {
            row.get("resource_accession", "") for row in strain_resources
            if row.get("downstream_block_reason") == "taxonomy_review_required"
            and row.get("resource_accession")
        }
        blocked = split_accessions(supervisor.get("taxonomy_blocked_biosample_accessions", ""))
        provisional = split_accessions(supervisor.get("provisional_biosample_accessions", ""))
        if eligible_sequence_records:
            data_status = "confirmed_sequence_available"
        elif blocked_resources or blocked:
            data_status = "linked_sequence_blocked_pending_taxonomy_review"
        elif biosamples:
            data_status = "confirmed_biosample_metadata_only"
        elif provisional:
            data_status = "provisional_match_requires_review"
        else:
            data_status = "no_confirmed_ncbi_match"
        output.append(
            {
                "ncppb_number": number,
                "snapshot_status": diff.get("snapshot_status", supervisor.get("snapshot_status", "")),
                "ncppb_current_name": supervisor.get("ncppb_current_name", diff.get("v1_current_name", "")),
                "expected_genus": supervisor.get("expected_genus", ""),
                "scope_status": supervisor.get("scope_status", "historical_missing_from_current_snapshot"),
                "catalogue_host": supervisor.get("catalogue_host", ""),
                "catalogue_country": supervisor.get("catalogue_country", ""),
                "ncbi_biosample_match_count": str(len(biosamples)),
                "ncbi_assembly_count": str(len(assemblies)),
                "ncbi_sra_run_count": str(len(sra)),
                "ncbi_bioproject_count": str(len(projects)),
                "ncbi_sequence_resource_count": str(len(sequence_records)),
                "ncbi_record_match_count": str(len(all_records)),
                "ncbi_eligible_assembly_count": str(len(eligible_assemblies)),
                "ncbi_eligible_sra_run_count": str(len(eligible_sra)),
                "ncbi_eligible_sequence_resource_count": str(len(eligible_sequence_records)),
                "ncbi_taxonomy_blocked_resource_count": str(len(blocked_resources)),
                "has_confirmed_ncbi_data": "yes" if all_records else "no",
                "ncbi_data_status": data_status,
                "sequence_availability_category": supervisor.get("sequence_availability_category", "not_in_current_snapshot"),
                "phylogeny_readiness": phylo.get("phylogeny_readiness", "not_in_current_snapshot"),
                "manual_review_required": supervisor.get("manual_review_required", "no"),
                "confirmed_biosample_accessions": supervisor.get("confirmed_biosample_accessions", ""),
                "linked_assembly_accessions": "; ".join(sorted(assemblies)),
                "linked_sra_run_accessions": "; ".join(sorted(sra)),
                "assembly_accessions": supervisor.get("assembly_accessions", ""),
                "sra_run_accessions": supervisor.get("sra_run_accessions", ""),
                "bioproject_accessions": supervisor.get("bioproject_accessions", ""),
                "taxonomy_blocked_biosample_accessions": supervisor.get("taxonomy_blocked_biosample_accessions", ""),
            }
        )
    return output


def write_explorer_output(outdir: Path, rows: list[dict[str, str]]) -> None:
    write_table(outdir / "explorer_strain_catalogue.tsv", rows, EXPLORER_COLUMNS)
