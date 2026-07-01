#!/usr/bin/env python3
"""Build reusable BioSample/Assembly/SRA/BioProject and phylogeny-input manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ncppb_audit_v2.common import read_table
from ncppb_audit_v2.retrieval import write_retrieval_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, default=ROOT / "results/v2_1_pipeline")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resources, phylogeny, projects = write_retrieval_outputs(
        args.outdir,
        read_table(args.outdir / "supervisor_sequence_availability.tsv"),
        read_table(args.outdir / "biosample_match_decisions.tsv"),
        read_table(args.outdir / "linked_ncbi_records.tsv"),
    )
    print(f"Sequence resource rows: {len(resources)}")
    print(f"Phylogeny input rows: {len(phylogeny)}")
    print(f"BioProject mapping rows: {len(projects)}")


if __name__ == "__main__":
    main()
