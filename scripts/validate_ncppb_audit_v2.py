#!/usr/bin/env python3
"""Validate V2 audit invariants before supervisor review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ncppb_audit_v2.common import read_table
from ncppb_audit_v2.matching import IDENTITY_FIELDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, default=ROOT / "results/v2_pipeline")
    parser.add_argument(
        "--expected-current-records",
        type=int,
        default=0,
        help="Optional project-specific expected row count; zero disables the check",
    )
    parser.add_argument(
        "--expected-missing-number",
        default="",
        help="Optional project-specific historical missing number",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    required = [
        "catalogue_strains.tsv",
        "catalogue_snapshot_diff.tsv",
        "strain_identifiers.tsv",
        "ncbi_query_plan.tsv",
        "ncbi_query_execution.tsv",
        "biosample_candidates.tsv",
        "biosample_match_decisions.tsv",
        "linked_ncbi_records.tsv",
        "supervisor_sequence_availability.tsv",
        "manual_review_queue.tsv",
        "v1_v2_comparison.tsv",
        "v1_regression_recall_audit.tsv",
        "sequence_resource_manifest.tsv",
        "phylogeny_input_manifest.tsv",
        "bioproject_mapping.tsv",
        "run_manifest.json",
    ]
    missing_files = [name for name in required if not (args.outdir / name).exists()]
    if missing_files:
        raise SystemExit(f"Missing V2 outputs: {', '.join(missing_files)}")

    strains = read_table(args.outdir / "catalogue_strains.tsv")
    snapshot_diff = read_table(args.outdir / "catalogue_snapshot_diff.tsv")
    queries = read_table(args.outdir / "ncbi_query_plan.tsv")
    query_execution = read_table(args.outdir / "ncbi_query_execution.tsv")
    candidates = read_table(args.outdir / "biosample_candidates.tsv")
    matches = read_table(args.outdir / "biosample_match_decisions.tsv")
    links = read_table(args.outdir / "linked_ncbi_records.tsv")
    supervisor = read_table(args.outdir / "supervisor_sequence_availability.tsv")
    manual = read_table(args.outdir / "manual_review_queue.tsv")
    comparison = read_table(args.outdir / "v1_v2_comparison.tsv")
    regression = read_table(args.outdir / "v1_regression_recall_audit.tsv")
    resources = read_table(args.outdir / "sequence_resource_manifest.tsv")
    phylogeny = read_table(args.outdir / "phylogeny_input_manifest.tsv")
    project_mapping = read_table(args.outdir / "bioproject_mapping.tsv")
    manifest = json.loads((args.outdir / "run_manifest.json").read_text(encoding="utf-8"))

    errors: list[str] = []
    if args.expected_current_records and len(strains) != args.expected_current_records:
        errors.append(f"catalogue_strains rows={len(strains)}, expected={args.expected_current_records}")
    if len(supervisor) != len(strains):
        errors.append(f"supervisor rows={len(supervisor)}, catalogue rows={len(strains)}")
    if len(comparison) != len(snapshot_diff):
        errors.append(f"comparison rows={len(comparison)}, snapshot diff rows={len(snapshot_diff)}")
    missing_rows = [row for row in snapshot_diff if row.get("snapshot_status") == "missing_from_v2_snapshot"]
    if args.expected_missing_number and [row.get("ncppb_number") for row in missing_rows] != [args.expected_missing_number]:
        errors.append(f"unexpected missing snapshot records: {[row.get('ncppb_number') for row in missing_rows]}")
    if args.expected_missing_number and any(row.get("ncppb_number") == args.expected_missing_number for row in supervisor):
        errors.append(f"{args.expected_missing_number} must not be inserted into the current supervisor table")

    ncppb_queries = [row for row in queries if row.get("query_track") == "ncppb_number"]
    prefix_queries = [row for row in ncppb_queries if row.get("ncppb_number") == "ALL_NCPPB"]
    exact_ncppb_queries = [row for row in ncppb_queries if row.get("identifier_type") == "ncppb_number"]
    if not prefix_queries or any(row.get("retrieval_strategy") != "trusted_prefix_harvest_then_structured_exact_local_mapping" for row in prefix_queries):
        errors.append("NCPPB prefix query track is not using local exact mapping")
    if len(exact_ncppb_queries) != len(strains) or any(
        row.get("retrieval_strategy") != "full_ncppb_identifier_variants_then_structured_exact_local_validation"
        for row in exact_ncppb_queries
    ):
        errors.append(
            f"full NCPPB identifier query coverage invalid: queries={len(exact_ncppb_queries)}, strains={len(strains)}"
        )
    if any("NCPPB[Text Word] AND" in row.get("query_term", "") for row in ncppb_queries):
        errors.append("NCPPB query plan contains forbidden split prefix/number terms")

    query_by_id = {row.get("query_id", ""): row for row in queries}
    execution_by_id = {row.get("query_id", ""): row for row in query_execution}
    if len(query_by_id) != len(queries):
        errors.append(f"duplicate query IDs in plan: rows={len(queries)}, unique={len(query_by_id)}")
    if set(query_by_id) != set(execution_by_id):
        errors.append(
            f"query execution coverage mismatch: plan={len(query_by_id)}, execution={len(execution_by_id)}"
        )
    trusted_execution_failures = []
    for query_id, query in query_by_id.items():
        execution = execution_by_id.get(query_id, {})
        if query.get("identifier_strength") in {"primary", "strong"} and (
            execution.get("status") == "error" or execution.get("truncated") == "yes"
        ):
            trusted_execution_failures.append(query_id)
    if trusted_execution_failures:
        errors.append(f"trusted prefix queries errored or truncated: {len(trusted_execution_failures)}")

    accepted = [row for row in matches if row.get("decision") == "accept"]
    invalid_accepted = [
        row for row in accepted
        if row.get("evidence_class") != "structured_exact_identifier"
        or row.get("matched_field") not in IDENTITY_FIELDS
        or row.get("identifier_strength") not in {"primary", "strong"}
        or bool(row.get("conflicting_ncppb_numbers"))
    ]
    if invalid_accepted:
        errors.append(f"accepted rows without strong structured exact identity evidence: {len(invalid_accepted)}")
    unflagged_taxonomy = [
        row for row in accepted
        if row.get("taxonomy_status") not in {"same_name", "compatible_synonym"}
        and row.get("taxonomy_review_required") != "yes"
    ]
    if unflagged_taxonomy:
        errors.append(f"accepted taxonomy anomalies not flagged for review: {len(unflagged_taxonomy)}")
    candidate_errors = [row for row in candidates if row.get("status") == "error"]
    link_errors = [row for row in links if row.get("status") == "error"]
    if candidate_errors:
        errors.append(f"candidate error rows: {len(candidate_errors)}")
    if link_errors:
        errors.append(f"linked-record error rows: {len(link_errors)}")
    unevaluated_regression = [row for row in regression if row.get("v2_1_decision") == "not_evaluated"]
    if unevaluated_regression:
        errors.append(f"V1 historical pairs not evaluated after safety recheck: {len(unevaluated_regression)}")

    if len(phylogeny) != len(strains):
        errors.append(f"phylogeny manifest rows={len(phylogeny)}, catalogue rows={len(strains)}")
    confirmed_pairs = {
        (row["ncppb_number"], accession)
        for row in supervisor
        for accession in row.get("confirmed_biosample_accessions", "").split("; ")
        if accession
    }
    manifested_confirmed_pairs = {
        (row.get("ncppb_number", ""), row.get("biosample_accession", ""))
        for row in resources
        if row.get("resource_type") == "biosample" and row.get("evidence_status") == "confirmed"
    }
    if confirmed_pairs != manifested_confirmed_pairs:
        errors.append(
            f"confirmed BioSample manifest coverage mismatch: expected={len(confirmed_pairs)}, manifested={len(manifested_confirmed_pairs)}"
        )
    invalid_selected_resources = [
        row for row in resources
        if row.get("selected_for_phylogeny") == "yes"
        and (
            row.get("evidence_status") != "confirmed"
            or row.get("resource_type") not in {"assembly", "sra_run"}
        )
    ]
    if invalid_selected_resources:
        errors.append(f"invalid selected phylogeny resources: {len(invalid_selected_resources)}")
    invalid_sequence_projects = [
        row for row in project_mapping
        if row.get("use_for_sequence_provenance") == "yes"
        and row.get("project_role") != "sequence_source_project"
    ]
    if invalid_sequence_projects:
        errors.append(f"non-sequence BioProjects promoted to provenance: {len(invalid_sequence_projects)}")
    confirmed_project_pairs = {
        (row.get("ncppb_number", ""), row.get("bioproject_accession", ""))
        for row in project_mapping
        if row.get("evidence_status") == "confirmed" and row.get("use_for_sequence_provenance") == "yes"
    }
    supervisor_project_pairs = {
        (row["ncppb_number"], accession)
        for row in supervisor
        for accession in row.get("bioproject_accessions", "").split("; ")
        if accession
    }
    if not supervisor_project_pairs <= confirmed_project_pairs:
        errors.append(
            f"supervisor contains unverified BioProject links: {len(supervisor_project_pairs - confirmed_project_pairs)}"
        )

    supervisor_manual = {row["ncppb_number"] for row in supervisor if row.get("manual_review_required") == "yes"}
    queue_numbers = {row["ncppb_number"] for row in manual}
    if supervisor_manual != queue_numbers:
        errors.append(
            f"manual queue mismatch: supervisor={len(supervisor_manual)}, queue={len(queue_numbers)}"
        )
    print(f"INFO: catalogue_rows={len(strains)}")
    print(f"INFO: supervisor_rows={len(supervisor)}")
    print(f"INFO: comparison_rows={len(comparison)}")
    print(f"INFO: accepted_biosamples={len(accepted)}")
    print(f"INFO: query_execution_rows={len(query_execution)}")
    print(f"INFO: confirmed_strains={sum(bool(row.get('confirmed_biosample_accessions')) for row in supervisor)}")
    print(f"INFO: manual_review_strains={len(manual)}")
    print(f"INFO: candidate_errors={len(candidate_errors)}")
    print(f"INFO: linked_record_errors={len(link_errors)}")
    print(f"INFO: v1_regression_pairs={len(regression)}")
    print(f"INFO: v1_pairs_rediscovered_by_new_search={sum(row.get('rediscovered_by_v2_1_search') == 'yes' for row in regression)}")
    print(f"INFO: v1_pairs_requiring_direct_recheck={sum(row.get('historical_direct_recheck_needed') == 'yes' for row in regression)}")
    print(f"INFO: sequence_resource_rows={len(resources)}")
    print(f"INFO: phylogeny_ready_assemblies={sum(row.get('preferred_resource_type') == 'assembly' for row in phylogeny)}")
    print(f"INFO: phylogeny_sra_fallbacks={sum(row.get('preferred_resource_type') == 'sra_wgs_reads' for row in phylogeny)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("V2.1 audit validation passed.")


if __name__ == "__main__":
    main()
