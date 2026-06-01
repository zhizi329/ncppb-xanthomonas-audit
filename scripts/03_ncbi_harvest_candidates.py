#!/usr/bin/env python3
"""Harvest raw BioSample metadata candidates for NCPPB strains.

This script is the network step. It searches BioSample with identifier-derived
queries and writes raw candidate metadata to a TSV. It does not classify records
as accepted or rejected.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


def load_core() -> Any:
    script_path = Path(__file__).resolve().with_name("03_ncbi_smoke_test.py")
    spec = importlib.util.spec_from_file_location("ncbi_smoke_test_core", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load core script from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


core = load_core()


def raw_output_columns() -> list[str]:
    return [
        "ncppb_number",
        "query_tier",
        "query_label",
        "search_term",
        "ncbi_db",
        "ncbi_uid",
        "ncbi_accession",
        "source_url",
        "data_type",
        "evidence_text",
        "metadata_text",
        "organism",
        "taxid",
        "title",
        "biosample_accession",
        "assembly_level",
        "sra_library_strategy",
        "id_count_returned",
        "status",
        "error",
    ]


def build_raw_candidate_row(
    context: Any,
    query: Any,
    uid: str,
    summary: dict[str, Any],
    id_count: int,
) -> dict[str, Any]:
    metadata = core.flatten_summary(query.db, uid, summary)
    return {
        "ncppb_number": context.ncppb_number,
        "query_tier": query.tier,
        "query_label": query.label,
        "search_term": query.term,
        "ncbi_db": query.db,
        "ncbi_uid": uid,
        "id_count_returned": id_count,
        "status": "ok",
        "error": "",
        "ncbi_accession": metadata.get("ncbi_accession", ""),
        "source_url": metadata.get("source_url", ""),
        "data_type": metadata.get("data_type", ""),
        "evidence_text": metadata.get("evidence_text", ""),
        "metadata_text": metadata.get("metadata_text", ""),
        "organism": metadata.get("organism", ""),
        "taxid": metadata.get("taxid", ""),
        "title": metadata.get("title", ""),
        "biosample_accession": metadata.get("biosample_accession", ""),
        "assembly_level": metadata.get("assembly_level", ""),
        "sra_library_strategy": metadata.get("sra_library_strategy", ""),
    }


def build_raw_error_row(context: Any, query: Any, error: Exception) -> dict[str, Any]:
    return {
        "ncppb_number": context.ncppb_number,
        "query_tier": query.tier,
        "query_label": query.label,
        "search_term": query.term,
        "ncbi_db": query.db,
        "status": "error",
        "error": str(error),
    }


def harvest_context(
    client: Any,
    context: Any,
    retmax: int,
    max_ids_per_query: int,
    summary_batch_size: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, str]] = set()
    for query in core.build_harvest_queries(context, core.HARVEST_DBS):
        try:
            ids = client.esearch_all(query.db, query.term, retmax, max_ids_per_query)
            summaries = client.esummary(query.db, ids, summary_batch_size)
        except Exception as exc:
            rows.append(build_raw_error_row(context, query, exc))
            continue
        for uid in ids:
            key = (query.db, uid)
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            rows.append(build_raw_candidate_row(context, query, uid, summaries.get(uid, {}), len(ids)))
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Search terms CSV or TSV, used for strain order")
    parser.add_argument("--master", required=True, help="NCPPB master CSV")
    parser.add_argument("--output", required=True, help="Raw candidate metadata TSV/CSV")
    parser.add_argument("--limit-strains", type=int, default=10, help="Number of strains to test")
    parser.add_argument("--retmax", type=int, default=100, help="IDs per NCBI ESearch page")
    parser.add_argument("--max-ids-per-query", type=int, default=100, help="Maximum IDs per keyword/database query")
    parser.add_argument("--summary-batch-size", type=int, default=200, help="Maximum IDs per ESummary request")
    parser.add_argument("--email", required=True, help="Email required by NCBI E-utilities")
    parser.add_argument("--api-key", default="", help="Optional NCBI API key")
    parser.add_argument("--delay", type=float, default=0.34, help="Delay between NCBI requests")
    parser.add_argument("--timeout", type=float, default=30.0, help="Network timeout per NCBI request")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = core.EntrezConfig(
        email=args.email,
        tool="ncppb_xanthomonas_audit",
        api_key=args.api_key or os.environ.get("NCBI_API_KEY", ""),
        delay=args.delay,
        timeout=args.timeout,
    )
    client = core.EntrezClient(config)

    all_terms = core.read_table(Path(args.input))
    selected = core.first_unique([row.get("ncppb_number", "") for row in all_terms], args.limit_strains)
    master = core.read_table(Path(args.master))
    master_rows = {row["ncppb_number"]: row for row in master if row.get("ncppb_number", "") in selected}
    contexts = [core.make_strain_context(master_rows.get(ncppb, {"ncppb_number": ncppb})) for ncppb in selected]

    rows: list[dict[str, Any]] = []
    for context in contexts:
        rows.extend(
            harvest_context(
                client,
                context,
                retmax=args.retmax,
                max_ids_per_query=args.max_ids_per_query,
                summary_batch_size=args.summary_batch_size,
            )
        )

    core.write_table(Path(args.output), rows, raw_output_columns())
    print(f"Wrote {len(rows)} raw candidate rows to {args.output}; {client.request_count} NCBI requests")


if __name__ == "__main__":
    main()
