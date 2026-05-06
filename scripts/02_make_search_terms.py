#!/usr/bin/env python3
"""Generate traceable NCBI search terms from the NCPPB master table."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    import pandas as pd
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pandas. Activate the project environment and run `pip install -r requirements.txt`."
    ) from exc


def split_multi(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return []
    parts = []
    for chunk in text.replace("|", ";").split(";"):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def add_term(rows: list[dict], ncppb_number: str, term: str, term_type: str) -> None:
    term = " ".join(str(term or "").split())
    if not term:
        return
    rows.append({"ncppb_number": ncppb_number, "term_type": term_type, "search_term": term})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="NCPPB master CSV")
    parser.add_argument("--output", required=True, help="Search terms CSV")
    args = parser.parse_args()

    df = pd.read_csv(args.input, dtype=str).fillna("")
    rows: list[dict] = []

    for _, row in df.iterrows():
        ncppb = row.get("ncppb_number", "").strip()
        compact = row.get("ncppb_number_compact", "").strip()
        current = row.get("current_name", "").strip()
        received = row.get("name_as_received", "").strip()

        add_term(rows, ncppb, ncppb, "ncppb_number")
        add_term(rows, ncppb, compact, "ncppb_number_compact")
        if ncppb:
            digits = "".join(ch for ch in ncppb if ch.isdigit())
            add_term(rows, ncppb, f'"National Collection of Plant Pathogenic Bacteria" {digits}', "collection_name_plus_number")
        if current and ncppb:
            add_term(rows, ncppb, f'"{current}" "{ncppb}"', "current_name_plus_number")
        if received and ncppb and received != current:
            add_term(rows, ncppb, f'"{received}" "{ncppb}"', "received_name_plus_number")
        for alt in split_multi(row.get("alternative_names", "")):
            if ncppb:
                add_term(rows, ncppb, f'"{alt}" "{ncppb}"', "alternative_name_plus_number")
        for other in split_multi(row.get("other_collection_numbers", "")):
            add_term(rows, ncppb, other, "other_collection_number")

    out = pd.DataFrame(rows).drop_duplicates()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {len(out)} search terms to {args.output}")


if __name__ == "__main__":
    main()
