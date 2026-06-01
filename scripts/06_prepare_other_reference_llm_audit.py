#!/usr/bin/env python3
"""Prepare files for LLM review of Other references identifier extraction."""

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


def write_table(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def identifiers_from_context(context: Any) -> list[Any]:
    return [
        identifier
        for identifier in context.identifiers
        if identifier.identifier_type in {"other_collection_number", "other_reference_identifier"}
    ]


def split_identifier(value: str) -> tuple[str, str]:
    prefix, suffix = core.identifier_parts(value)
    return prefix, suffix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", required=True, help="NCPPB master CSV")
    parser.add_argument("--output-dir", required=True, help="Directory for LLM audit files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    rows = core.read_table(Path(args.master))

    source_rows: list[dict[str, str]] = []
    extraction_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []

    for row in rows:
        ncppb_number = row.get("ncppb_number", "")
        other_references = row.get("other_references", "")
        context = core.make_strain_context(row)
        identifiers = identifiers_from_context(context)
        normalized_values: list[str] = []
        query_terms: list[str] = []

        source_rows.append(
            {
                "ncppb_number": ncppb_number,
                "other_references": other_references,
            }
        )

        for identifier in identifiers:
            prefix, number = split_identifier(identifier.value)
            query_term = core.identifier_query_term(identifier.value)
            normalized_values.append(identifier.value)
            query_terms.append(query_term)
            extraction_rows.append(
                {
                    "ncppb_number": ncppb_number,
                    "other_references": other_references,
                    "identifier_type": identifier.identifier_type,
                    "normalized_identifier": identifier.value,
                    "prefix": prefix,
                    "number": number,
                    "biosample_search_term": query_term,
                }
            )

        comparison_rows.append(
            {
                "ncppb_number": ncppb_number,
                "other_references": other_references,
                "script_identifiers": "; ".join(normalized_values),
                "script_biosample_search_terms": "; ".join(query_terms),
                "llm_expected_identifiers": "",
                "llm_missing_from_script": "",
                "llm_false_positive_from_script": "",
                "llm_verdict": "",
                "llm_notes": "",
            }
        )

    write_table(
        output_dir / "other_references_source_all.tsv",
        source_rows,
        ["ncppb_number", "other_references"],
    )
    write_table(
        output_dir / "other_reference_identifier_extraction_all.tsv",
        extraction_rows,
        [
            "ncppb_number",
            "other_references",
            "identifier_type",
            "normalized_identifier",
            "prefix",
            "number",
            "biosample_search_term",
        ],
    )
    write_table(
        output_dir / "other_reference_llm_review_template.tsv",
        comparison_rows,
        [
            "ncppb_number",
            "other_references",
            "script_identifiers",
            "script_biosample_search_terms",
            "llm_expected_identifiers",
            "llm_missing_from_script",
            "llm_false_positive_from_script",
            "llm_verdict",
            "llm_notes",
        ],
    )
    print(f"Wrote {len(source_rows)} source rows to {output_dir / 'other_references_source_all.tsv'}")
    print(
        f"Wrote {len(extraction_rows)} extracted identifiers to "
        f"{output_dir / 'other_reference_identifier_extraction_all.tsv'}"
    )
    print(f"Wrote LLM review template to {output_dir / 'other_reference_llm_review_template.tsv'}")


if __name__ == "__main__":
    main()
