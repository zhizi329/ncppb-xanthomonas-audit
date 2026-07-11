#!/usr/bin/env python3
"""Run the V2 NCPPB catalogue-to-NCBI sequence-availability audit."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ncppb_audit_v2.catalogue import write_catalogue_outputs
from ncppb_audit_v2.analysis import (
    build_accession_changes,
    build_manual_review_candidates,
    build_manual_review_queue,
    build_v1_regression_recall_audit,
    write_analysis_outputs,
)
from ncppb_audit_v2.common import read_table, sha256_file
from ncppb_audit_v2.explorer import build_explorer_table, write_explorer_output
from ncppb_audit_v2.identifiers import extract_identifiers, write_identifier_outputs
from ncppb_audit_v2.matching import (
    apply_review_decisions,
    build_supervisor_table,
    compare_v1_v2,
    match_candidates,
    write_matching_outputs,
)
from ncppb_audit_v2.ncbi import (
    NcbiClient,
    expand_linked_records,
    harvest_biosample_candidates,
    map_shared_ncppb_candidates,
    map_shared_other_prefix_candidates,
    recheck_v1_biosample_accessions,
    merge_verified_resource_seeds,
    write_ncbi_outputs,
)
from ncppb_audit_v2.queries import build_query_plan, write_query_plan
from ncppb_audit_v2.reporting import build_manifest, write_summary
from ncppb_audit_v2.retrieval import write_retrieval_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalogue-html",
        type=Path,
        required=True,
        help="User-supplied NCPPB catalogue HTML file",
    )
    parser.add_argument(
        "--v1-master",
        type=Path,
        default=None,
        help="Optional historical catalogue table used only for comparison",
    )
    parser.add_argument(
        "--v1-sequence-table",
        type=Path,
        default=None,
        help="Optional historical sequence table used only for regression comparison",
    )
    parser.add_argument("--outdir", type=Path, default=ROOT / "runs/audit/work")
    parser.add_argument("--run-ncbi", action="store_true", help="Execute NCBI BioSample retrieval and linked-record expansion")
    parser.add_argument("--email", default=os.environ.get("NCBI_EMAIL", ""))
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NCBI_API_KEY", ""),
        help="NCBI API key; prefer NCBI_API_KEY or --prompt-api-key to avoid shell history",
    )
    parser.add_argument(
        "--prompt-api-key",
        action="store_true",
        help="Securely request an optional NCBI API key without echoing or saving it",
    )
    parser.add_argument(
        "--record-input-hash",
        action="store_true",
        help="Optionally record the uploaded HTML SHA-256 for provenance; never used as an acceptance check",
    )
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache/ncbi/v2_1")
    parser.add_argument("--delay", type=float, default=0.34)
    parser.add_argument("--timeout", type=float, default=40.0)
    parser.add_argument("--retmax", type=int, default=100)
    parser.add_argument("--offline-cache-only", action="store_true")
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Bypass existing NCBI cache entries and fetch fresh responses",
    )
    parser.add_argument(
        "--cache-max-age-hours",
        type=float,
        default=0.0,
        help="Treat older cache entries as stale; zero keeps them indefinitely",
    )
    parser.add_argument("--reuse-candidates", action="store_true")
    parser.add_argument(
        "--review-decisions",
        type=Path,
        default=None,
        help="Pair-level TSV/CSV decisions using approve_for_downstream, reject_match, or keep_pending",
    )
    parser.add_argument(
        "--resource-seed-table",
        type=Path,
        default=None,
        help="Optional verified Assembly/SRA/BioProject accessions missed by BioSample ELink",
    )
    parser.add_argument(
        "--require-reviewed",
        action="store_true",
        help="Fail if any BioSample identity/taxonomy review remains unresolved",
    )
    parser.add_argument("--limit-strains", type=int, default=0)
    return parser.parse_args()


def resolve_api_key(current_key: str, prompt_requested: bool, run_ncbi: bool) -> str:
    if not prompt_requested:
        return current_key
    if not run_ncbi:
        raise ValueError("--prompt-api-key is only meaningful with --run-ncbi")
    try:
        prompted_key = getpass.getpass(
            "NCBI API key (input hidden; press Enter to continue without one): "
        ).strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise ValueError("Unable to read NCBI API key interactively") from exc
    return prompted_key or current_key


def main() -> None:
    args = parse_args()
    if not args.catalogue_html.exists():
        raise SystemExit(f"Catalogue HTML not found: {args.catalogue_html}")
    if args.run_ncbi and not args.email:
        raise SystemExit("--email or NCBI_EMAIL is required with --run-ncbi")
    if args.refresh_cache and args.offline_cache_only:
        raise SystemExit("--refresh-cache cannot be combined with --offline-cache-only")
    if args.cache_max_age_hours < 0:
        raise SystemExit("--cache-max-age-hours must be zero or positive")
    for label, path in [
        ("review decision table", args.review_decisions),
        ("resource seed table", args.resource_seed_table),
    ]:
        if path is not None and not path.exists():
            raise SystemExit(f"{label} not found: {path}")
    try:
        args.api_key = resolve_api_key(args.api_key, args.prompt_api_key, args.run_ncbi)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    args.outdir.mkdir(parents=True, exist_ok=True)

    strains, clauses, snapshot_diff = write_catalogue_outputs(
        args.catalogue_html,
        args.v1_master,
        args.outdir,
        read_table,
        record_source_hash=args.record_input_hash,
    )
    if args.limit_strains > 0:
        selected = {row["ncppb_number"] for row in strains[: args.limit_strains]}
        strains = strains[: args.limit_strains]
        clauses = [row for row in clauses if row["ncppb_number"] in selected]

    identifiers, parser_reviews = extract_identifiers(strains, clauses)
    identifier_reviews = write_identifier_outputs(args.outdir, identifiers, parser_reviews)
    query_plan = build_query_plan(strains, identifiers)
    write_query_plan(args.outdir, query_plan)

    match_rows = None
    supervisor_rows = None
    comparison_rows = None
    linked_rows: list[dict[str, str]] = []
    resource_rows: list[dict[str, str]] = []
    phylogeny_rows: list[dict[str, str]] = []
    bioproject_rows: list[dict[str, str]] = []
    manual_candidate_rows: list[dict[str, str]] = []
    explorer_rows: list[dict[str, str]] = []
    client = None
    if args.run_ncbi:
        v1_sequence = (
            read_table(args.v1_sequence_table)
            if args.v1_sequence_table and args.v1_sequence_table.exists()
            else []
        )
        client = NcbiClient(
            email=args.email,
            api_key=args.api_key,
            cache_dir=args.cache_dir,
            delay=args.delay,
            timeout=args.timeout,
            offline_cache_only=args.offline_cache_only,
            refresh_cache=args.refresh_cache,
            cache_max_age_hours=args.cache_max_age_hours,
        )
        candidate_path = args.outdir / "biosample_candidates.tsv"
        reuse_candidates = args.reuse_candidates and candidate_path.exists() and not args.refresh_cache
        if reuse_candidates and args.cache_max_age_hours:
            candidate_age_hours = max(0.0, (time.time() - candidate_path.stat().st_mtime) / 3600.0)
            reuse_candidates = candidate_age_hours <= args.cache_max_age_hours
        if reuse_candidates:
            candidates = read_table(candidate_path)
            query_execution_path = args.outdir / "ncbi_query_execution.tsv"
            query_execution = read_table(query_execution_path) if query_execution_path.exists() else []
        else:
            candidates, query_execution = harvest_biosample_candidates(query_plan, client, retmax=args.retmax)
        candidates, unmapped_ncppb = map_shared_ncppb_candidates(candidates, strains)
        candidates, unmapped_other = map_shared_other_prefix_candidates(candidates, identifiers)
        candidates.extend(recheck_v1_biosample_accessions(v1_sequence, candidates, client))
        if unmapped_ncppb:
            from ncppb_audit_v2.common import write_table
            from ncppb_audit_v2.ncbi import CANDIDATE_COLUMNS
            write_table(args.outdir / "unmapped_ncppb_prefix_candidates.tsv", unmapped_ncppb, CANDIDATE_COLUMNS)
        if unmapped_other:
            from ncppb_audit_v2.common import write_table
            from ncppb_audit_v2.ncbi import CANDIDATE_COLUMNS
            write_table(args.outdir / "unmapped_other_prefix_candidates.tsv", unmapped_other, CANDIDATE_COLUMNS)
        match_rows = match_candidates(strains, identifiers, candidates)
        if args.review_decisions:
            try:
                match_rows = apply_review_decisions(match_rows, read_table(args.review_decisions))
            except ValueError as exc:
                raise SystemExit(f"Invalid review decision table: {exc}") from exc
        if args.require_reviewed and any(row.get("manual_review_required") == "yes" for row in match_rows):
            unresolved = sum(row.get("manual_review_required") == "yes" for row in match_rows)
            raise SystemExit(f"--require-reviewed failed: {unresolved} BioSample candidate decisions remain unresolved")
        candidate_by_key = {
            (row.get("ncppb_number", ""), row.get("biosample_accession", "")): row
            for row in candidates
            if row.get("biosample_accession", "")
        }
        # Expand links for confirmed and provisional identity matches.  The
        # supervisor table keeps their sequence links in separate columns, so
        # reviewers can see what would change without promoting review rows.
        linkable_candidates = [
            candidate_by_key[(row["ncppb_number"], row["biosample_accession"])]
            for row in match_rows
            if row.get("decision") in {"accept", "review"}
            and (row["ncppb_number"], row["biosample_accession"]) in candidate_by_key
        ]
        linked_rows = expand_linked_records(linkable_candidates, client)
        if args.resource_seed_table:
            try:
                linked_rows = merge_verified_resource_seeds(
                    linked_rows, read_table(args.resource_seed_table), match_rows
                )
            except ValueError as exc:
                raise SystemExit(f"Invalid resource seed table: {exc}") from exc
        write_ncbi_outputs(args.outdir, candidates, linked_rows, query_execution)
        supervisor_rows = build_supervisor_table(strains, identifiers, match_rows, linked_rows)
        comparison_rows = compare_v1_v2(v1_sequence, supervisor_rows, snapshot_diff)
        write_matching_outputs(args.outdir, match_rows, supervisor_rows, comparison_rows)
        resource_rows, phylogeny_rows, bioproject_rows = write_retrieval_outputs(
            args.outdir, supervisor_rows, match_rows, linked_rows
        )
        explorer_rows = build_explorer_table(
            supervisor_rows, snapshot_diff, phylogeny_rows, resource_rows
        )
        write_explorer_output(args.outdir, explorer_rows)
        manual_rows = build_manual_review_queue(supervisor_rows, match_rows)
        manual_candidate_rows = build_manual_review_candidates(supervisor_rows, match_rows)
        accession_changes = build_accession_changes(v1_sequence, supervisor_rows, match_rows)
        v1_regression_rows = build_v1_regression_recall_audit(v1_sequence, match_rows)
        write_analysis_outputs(
            args.outdir,
            manual_rows,
            accession_changes,
            v1_sequence,
            supervisor_rows,
            match_rows,
            v1_regression_rows,
            manual_candidate_rows,
        )

    write_summary(
        args.outdir,
        strains,
        clauses,
        identifiers,
        parser_reviews,
        query_plan,
        snapshot_diff,
        match_rows,
        supervisor_rows,
        comparison_rows,
    )
    counts = {
        "catalogue_strains": len(strains),
        "other_reference_clauses": len(clauses),
        "identifiers": len(identifiers),
        "parser_review_rows": len(parser_reviews),
        "identifier_review_rows": len(identifier_reviews),
        "query_plan_rows": len(query_plan),
        "biosample_match_decisions": len(match_rows or []),
        "linked_ncbi_records": len(linked_rows),
        "supervisor_rows": len(supervisor_rows or []),
        "sequence_resource_rows": len(resource_rows),
        "phylogeny_input_rows": len(phylogeny_rows),
        "bioproject_mapping_rows": len(bioproject_rows),
        "manual_review_candidate_rows": len(manual_candidate_rows),
        "explorer_rows": len(explorer_rows),
    }
    manifest_args = {
        "run_ncbi": args.run_ncbi,
        "offline_cache_only": args.offline_cache_only,
        "refresh_cache": args.refresh_cache,
        "cache_max_age_hours": args.cache_max_age_hours,
        "reuse_candidates_requested": args.reuse_candidates,
        "retmax": args.retmax,
        "limit_strains": args.limit_strains,
        "cache_dir": args.cache_dir.name,
        "email_recorded": bool(args.email),
        "api_key_recorded": bool(args.api_key),
        "query_plan_sha256": sha256_file(args.outdir / "ncbi_query_plan.tsv"),
        "input_hash_recorded": args.record_input_hash,
        "review_decisions": args.review_decisions.name if args.review_decisions else "",
        "resource_seed_table": args.resource_seed_table.name if args.resource_seed_table else "",
        "require_reviewed": args.require_reviewed,
        "v1_master": args.v1_master.name if args.v1_master else "",
        "v1_sequence_table": args.v1_sequence_table.name if args.v1_sequence_table else "",
    }
    build_manifest(
        args.outdir,
        args.catalogue_html,
        manifest_args,
        counts,
        "ncbi_complete" if args.run_ncbi else "local_plan_complete_ncbi_not_run",
        record_input_hash=args.record_input_hash,
    )
    print(f"V2.1 outputs written to {args.outdir}")
    print(f"Current HTML strains: {len(strains)}")
    print(f"Query plan rows: {len(query_plan)}")
    if client is not None:
        print(
            f"NCBI requests: {client.request_count}; cache hits: {client.cache_hits}; "
            f"stale cache misses: {client.stale_cache_misses}"
        )


if __name__ == "__main__":
    main()
