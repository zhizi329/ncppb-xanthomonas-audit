#!/usr/bin/env python3
"""Run a small NCBI Entrez smoke test for Week 2.

This script searches metadata only. It does not download sequence files.
It writes TSV when the output path ends in `.tsv`; otherwise it writes CSV.
"""

from __future__ import annotations

import argparse
import socket
import time
from pathlib import Path

try:
    import pandas as pd
    from Bio import Entrez
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Activate the project environment and run `pip install -r requirements.txt`."
    ) from exc

DBS = ["biosample", "assembly", "sra", "taxonomy"]


def esearch(db: str, term: str, retmax: int, delay: float) -> list[str]:
    time.sleep(delay)
    with Entrez.esearch(db=db, term=term, retmax=retmax) as handle:
        record = Entrez.read(handle)
    return list(record.get("IdList", []))


def table_separator(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Search terms CSV or TSV")
    parser.add_argument("--output", required=True, help="Output CSV or TSV")
    parser.add_argument("--limit-strains", type=int, default=10, help="Number of strains to test")
    parser.add_argument("--retmax", type=int, default=5, help="Max IDs per database per term")
    parser.add_argument("--email", required=True, help="Email required by NCBI Entrez")
    parser.add_argument("--api-key", default="", help="Optional NCBI API key")
    parser.add_argument("--delay", type=float, default=0.34, help="Delay between NCBI calls")
    parser.add_argument("--timeout", type=float, default=30.0, help="Network timeout per NCBI request")
    args = parser.parse_args()

    Entrez.email = args.email
    Entrez.tool = "ncppb_xanthomonas_audit"
    if args.api_key:
        Entrez.api_key = args.api_key
    socket.setdefaulttimeout(args.timeout)

    input_path = Path(args.input)
    terms = pd.read_csv(input_path, dtype=str, sep=table_separator(input_path)).fillna("")
    selected = terms["ncppb_number"].drop_duplicates().head(args.limit_strains).tolist()
    terms = terms[terms["ncppb_number"].isin(selected)]

    rows = []
    for _, row in terms.iterrows():
        ncppb = row["ncppb_number"]
        term_type = row["term_type"]
        term = row["search_term"]
        for db in DBS:
            try:
                ids = esearch(db, term, args.retmax, args.delay)
                rows.append({
                    "ncppb_number": ncppb,
                    "term_type": term_type,
                    "search_term": term,
                    "ncbi_db": db,
                    "id_count_returned": len(ids),
                    "ids": ";".join(ids),
                    "status": "ok",
                    "error": "",
                })
            except Exception as exc:  # Keep smoke test running and record the problem.
                rows.append({
                    "ncppb_number": ncppb,
                    "term_type": term_type,
                    "search_term": term,
                    "ncbi_db": db,
                    "id_count_returned": 0,
                    "ids": "",
                    "status": "error",
                    "error": str(exc),
                })

    out = pd.DataFrame(rows)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False, sep=table_separator(output_path))
    print(f"Wrote {len(out)} rows to {output_path}")


if __name__ == "__main__":
    main()
