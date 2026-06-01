#!/usr/bin/env python3
"""Write the planned BioSample identifier queries for selected strains."""

from __future__ import annotations

import argparse
import csv
import importlib.util
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


def write_table(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["ncppb_number", "query_label", "identifier", "ncbi_db", "search_term"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=core.table_separator(path))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Search terms CSV or TSV, used for strain order")
    parser.add_argument("--master", required=True, help="NCPPB master CSV")
    parser.add_argument("--limit-strains", type=int, default=30, help="Number of ordered strains to include")
    parser.add_argument("--output", required=True, help="Query plan TSV/CSV output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ordered_rows = core.read_table(Path(args.input))
    selected = core.first_unique([row.get("ncppb_number", "") for row in ordered_rows], args.limit_strains)
    master = core.read_table(Path(args.master))
    master_rows = {row["ncppb_number"]: row for row in master if row.get("ncppb_number", "") in selected}

    rows: list[dict[str, str]] = []
    for ncppb_number in selected:
        context = core.make_strain_context(master_rows.get(ncppb_number, {"ncppb_number": ncppb_number}))
        keywords = {keyword.value: keyword.source for keyword in core.build_harvest_keywords(context)}
        for query in core.build_harvest_queries(context, core.HARVEST_DBS):
            rows.append(
                {
                    "ncppb_number": context.ncppb_number,
                    "query_label": query.label,
                    "identifier": next((value for value, source in keywords.items() if source == query.label and core.identifier_query_term(value) == query.term), ""),
                    "ncbi_db": query.db,
                    "search_term": query.term,
                }
            )

    write_table(Path(args.output), rows)
    print(f"Wrote {len(rows)} planned BioSample queries to {args.output}")


if __name__ == "__main__":
    main()
