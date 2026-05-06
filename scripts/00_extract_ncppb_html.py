#!/usr/bin/env python3
"""Extract NCPPB catalogue result records from a saved HTML page.

The NCPPB result page is not a normal rectangular table. Each strain is shown as
one header row followed by a nested detail row. This script converts that layout
into a CSV suitable for the Week 1 master table.

It also supports Chrome `view-source:` saves by reconstructing the underlying
HTML from `td.line-content` cells before parsing records.
"""

from __future__ import annotations

import argparse
import re
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

try:
    import pandas as pd
    from bs4 import BeautifulSoup
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pandas/beautifulsoup4. Activate the environment and run `pip install -r requirements.txt`."
    ) from exc

BASE_URL = "https://ncppb.fera.co.uk/"

OUTPUT_COLUMNS = [
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

LABEL_MAP = {
    "name as received": "name_as_received",
    "other name": "alternative_names",
    "country": "country",
    "host": "host",
    "year added": "year_added",
    "type strain of the species": "type_strain_of_species",
    "pathotype strain": "pathotype_strain",
    "other references": "other_references",
    "notes": "notes",
    "sequencing link": "catalogue_sequence_links",
    "sequencing type": "sequencing_type",
}

COLLECTION_ID_RE = re.compile(
    r"\b(ATCC|BCCM|CCUG|CFBP|CIP|DSMZ?|ICMP|JCM|LMG|NCTC|NIB|NRRL|PDDCC|PD|RIV|UQM|VKM|WDCM)\s*[-:]?\s*[A-Z]*\d+[A-Z0-9.-]*\b",
    flags=re.I,
)


def clean_text(value: object) -> str:
    text = " ".join(str(value or "").replace("\xa0", " ").split())
    return text.strip()


def normalise_ncppb(value: str) -> str:
    match = re.search(r"(\d+)", value or "")
    return f"NCPPB {match.group(1)}" if match else clean_text(value)


def compact_ncppb(value: str) -> str:
    return re.sub(r"\s+", "", value.upper()) if value else ""


def extract_pathovar(name: str) -> str:
    match = re.search(r"\bpv\.?\s+([A-Za-z0-9_.-]+)", name or "")
    return f"pv. {match.group(1)}" if match else ""


def extract_other_collection_numbers(*texts: str) -> str:
    found: list[str] = []
    for text in texts:
        for match in COLLECTION_ID_RE.finditer(text or ""):
            value = clean_text(match.group(0)).upper()
            value = re.sub(r"\s+", " ", value)
            if value not in found:
                found.append(value)
    return "; ".join(found)


def reconstruct_if_view_source(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    line_cells = soup.select("td.line-content")
    if not line_cells:
        return html
    lines = [td.get_text("", strip=False) for td in line_cells]
    return unescape("\n".join(lines))


def value_for_label(strong_tag) -> tuple[str, str]:
    label = clean_text(strong_tag.get_text(" ", strip=True)).rstrip(":").lower()
    label_td = strong_tag.find_parent("td")
    value_td = label_td.find_next_sibling("td") if label_td else None
    if value_td is None:
        return label, ""
    text = clean_text(value_td.get_text(" ", strip=True))
    links = []
    for a in value_td.find_all("a", href=True):
        link_text = clean_text(a.get_text(" ", strip=True))
        href = urljoin(BASE_URL, a.get("href", ""))
        if link_text and href:
            links.append(f"{link_text} <{href}>")
        elif href:
            links.append(href)
    if links:
        text = "; ".join(links)
    return label, text


def parse_records(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(reconstruct_if_view_source(html), "html.parser")
    links = soup.find_all("a", href=re.compile(r"furtherinfo\.cfm\?ncppb_no=", re.I))
    records: list[dict[str, str]] = []

    for a in links:
        header_tr = a.find_parent("tr")
        if header_tr is None:
            continue
        cells = header_tr.find_all("td", recursive=False)
        if len(cells) < 3:
            continue

        ncppb_number = normalise_ncppb(a.get_text(" ", strip=True) or a.get("href", ""))
        current_name = clean_text(cells[2].get_text(" ", strip=True))
        detail_tr = header_tr.find_next_sibling("tr")

        record = {col: "" for col in OUTPUT_COLUMNS}
        record["ncppb_number"] = ncppb_number
        record["ncppb_number_compact"] = compact_ncppb(ncppb_number)
        record["current_name"] = current_name
        record["pathovar"] = extract_pathovar(current_name)
        record["ncppb_catalogue_url"] = urljoin(BASE_URL, a.get("href", ""))

        if detail_tr is not None:
            record["raw_record_text"] = clean_text(header_tr.get_text(" ", strip=True) + " " + detail_tr.get_text(" ", strip=True))
            for strong in detail_tr.find_all("strong"):
                label, value = value_for_label(strong)
                col = LABEL_MAP.get(label)
                if not col or not value:
                    continue
                if record[col] and value not in record[col]:
                    record[col] = f"{record[col]}; {value}"
                else:
                    record[col] = value

        record["other_collection_numbers"] = extract_other_collection_numbers(
            record["other_references"], record["notes"], record["alternative_names"]
        )
        records.append(record)

    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Saved NCPPB HTML file")
    parser.add_argument("--output", required=True, help="CSV output path")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Input HTML not found: {input_path}")

    html = input_path.read_text(encoding="utf-8", errors="replace")
    records = parse_records(html)
    if not records:
        raise SystemExit("No NCPPB records found. Check that the saved HTML contains the result page, not a login/challenge page.")

    df = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    df = df.drop_duplicates(subset=["ncppb_number"], keep="first")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df)} NCPPB records to {output_path}")
    print("Columns:", ", ".join(df.columns))


if __name__ == "__main__":
    main()
