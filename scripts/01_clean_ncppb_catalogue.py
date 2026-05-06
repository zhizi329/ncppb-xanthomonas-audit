#!/usr/bin/env python3
"""Clean a raw NCPPB catalogue export into the project master table.

Expected input: CSV exported by `00_extract_ncppb_html.py` or manually prepared
from the NCPPB result page. The script is deliberately conservative: it
preserves original fields and creates standard search-oriented fields without
deleting historical names.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    import pandas as pd
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pandas. Activate the project environment and run `pip install -r requirements.txt`."
    ) from exc

MASTER_COLUMNS = [
    "ncppb_number",
    "ncppb_number_compact",
    "current_name",
    "name_as_received",
    "alternative_names",
    "pathovar",
    "host",
    "country",
    "other_collection_numbers",
    "ncppb_catalogue_url",
    "catalogue_sequence_links",
    "sequencing_type",
    "year_added",
    "type_strain_of_species",
    "pathotype_strain",
    "other_references",
    "notes",
    "raw_record_text",
]

COLUMN_ALIASES = {
    "ncppb_number": ["ncppb_number", "ncppb", "ncppb no", "ncppb no.", "accession", "accession number", "catalogue number"],
    "current_name": ["current_name", "name", "organism", "taxon", "species", "scientific name", "catalogue name"],
    "name_as_received": ["name_as_received", "name as received", "received as", "original name"],
    "alternative_names": ["alternative_names", "alternative names", "synonyms", "other names", "other name"],
    "pathovar": ["pathovar", "pv", "pv."],
    "host": ["host", "host plant"],
    "country": ["country", "origin", "country of origin"],
    "other_collection_numbers": ["other_collection_numbers", "other collection numbers", "other numbers", "strain", "strain number"],
    "ncppb_catalogue_url": ["ncppb_catalogue_url", "url", "link"],
    "catalogue_sequence_links": ["catalogue_sequence_links", "sequence links", "sequencing link", "sequence", "genome", "ncbi"],
    "sequencing_type": ["sequencing_type", "sequencing type"],
    "year_added": ["year_added", "year added"],
    "type_strain_of_species": ["type_strain_of_species", "type strain of the species", "type strain"],
    "pathotype_strain": ["pathotype_strain", "pathotype strain"],
    "other_references": ["other_references", "other references"],
    "notes": ["notes", "comments", "remarks"],
    "raw_record_text": ["raw_record_text", "raw record text"],
}


def normalise_header(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def clean_text(value: object) -> str:
    text = " ".join(str(value or "").replace("\xa0", " ").split())
    return "" if text.lower() == "nan" else text


def standardise_ncppb(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    match = re.search(r"(?:NCPPB\s*)?(\d+)", text, flags=re.I)
    if match:
        return f"NCPPB {match.group(1)}"
    return text


def compact_ncppb(value: object) -> str:
    text = standardise_ncppb(value)
    return re.sub(r"\s+", "", text.upper()) if text else ""


def extract_pathovar(name: object) -> str:
    text = clean_text(name)
    match = re.search(r"\bpv\.?\s+([A-Za-z0-9_.-]+)", text)
    return f"pv. {match.group(1)}" if match else ""


def map_columns(df: "pd.DataFrame") -> "pd.DataFrame":
    lookup = {normalise_header(col): col for col in df.columns}
    output = pd.DataFrame()
    for target, aliases in COLUMN_ALIASES.items():
        source = next((lookup[a] for a in aliases if a in lookup), None)
        output[target] = df[source] if source else ""
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Raw NCPPB CSV file")
    parser.add_argument("--output", required=True, help="Cleaned master CSV output")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path, dtype=str).fillna("")
    master = map_columns(df)
    for col in MASTER_COLUMNS:
        if col not in master.columns:
            master[col] = ""
        master[col] = master[col].map(clean_text)

    master["ncppb_number"] = master["ncppb_number"].map(standardise_ncppb)
    master["ncppb_number_compact"] = master["ncppb_number"].map(compact_ncppb)
    missing_pathovar = master["pathovar"].eq("")
    master.loc[missing_pathovar, "pathovar"] = master.loc[missing_pathovar, "current_name"].map(extract_pathovar)

    master = master[MASTER_COLUMNS]
    master = master.drop_duplicates(subset=["ncppb_number"], keep="first")
    master = master.sort_values("ncppb_number", key=lambda s: s.str.extract(r"(\d+)", expand=False).astype(float), ignore_index=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(output_path, index=False)
    print(f"Wrote {len(master)} rows to {output_path}")


if __name__ == "__main__":
    main()
