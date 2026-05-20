#!/usr/bin/env python3
"""Search NCBI BioSample with prepared identifier queries and write raw rows."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


OUTPUT_COLUMNS = [
    "ncppb_number",
    "query_source",
    "normalized_identifier",
    "prefix",
    "suffix",
    "search_term",
    "ncbi_db",
    "ncbi_uid",
    "ncbi_accession",
    "source_url",
    "title",
    "organism",
    "taxid",
    "identifiers",
    "infraspecies",
    "attributes",
    "metadata_text",
    "id_count_returned",
    "status",
    "error",
]


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def table_delimiter(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=table_delimiter(path))
        return [{key: value or "" for key, value in row.items()} for row in reader]


def write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, delimiter=table_delimiter(path))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def ncppb_digits(value: str) -> str:
    match = re.search(r"\d+", value or "")
    return match.group(0) if match else ""


def ncppb_query(ncppb_number: str) -> tuple[str, str, str, str]:
    digits = ncppb_digits(ncppb_number)
    return f"NCPPB {digits}", "NCPPB", digits, f"NCPPB[All Fields] AND {digits}[All Fields]"


def query_specs(rows: list[dict[str, str]], include_ncppb_number: bool) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    strain_order: list[str] = []

    for row in rows:
        ncppb_number = clean_text(row.get("ncppb_number", ""))
        if ncppb_number and ncppb_number not in strain_order:
            strain_order.append(ncppb_number)

    if include_ncppb_number:
        for ncppb_number in strain_order:
            normalized, prefix, suffix, term = ncppb_query(ncppb_number)
            key = (ncppb_number, term)
            if key in seen:
                continue
            seen.add(key)
            specs.append(
                {
                    "ncppb_number": ncppb_number,
                    "query_source": "ncppb_number",
                    "normalized_identifier": normalized,
                    "prefix": prefix,
                    "suffix": suffix,
                    "search_term": term,
                }
            )

    for row in rows:
        if clean_text(row.get("include_for_search", "")).lower() != "yes":
            continue
        ncppb_number = clean_text(row.get("ncppb_number", ""))
        term = clean_text(row.get("biosample_query", ""))
        if not ncppb_number or not term:
            continue
        key = (ncppb_number, term)
        if key in seen:
            continue
        seen.add(key)
        specs.append(
            {
                "ncppb_number": ncppb_number,
                "query_source": "other_reference",
                "normalized_identifier": clean_text(row.get("normalized_identifier", "")),
                "prefix": clean_text(row.get("prefix", "")),
                "suffix": clean_text(row.get("suffix", "")),
                "search_term": term,
            }
        )

    return specs


class EntrezClient:
    def __init__(self, email: str, api_key: str, delay: float, timeout: float, tool: str) -> None:
        self.email = email
        self.api_key = api_key
        self.delay = delay
        self.timeout = timeout
        self.tool = tool
        self.request_count = 0

    def get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        time.sleep(self.delay)
        query = {"tool": self.tool, "retmode": "json", **params}
        if self.email:
            query["email"] = self.email
        if self.api_key:
            query["api_key"] = self.api_key
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{endpoint}.fcgi?{urlencode(query)}"
        self.request_count += 1
        with urlopen(url, timeout=self.timeout) as handle:
            return json.loads(handle.read().decode("utf-8"), strict=False)

    def esearch_all(self, term: str, retmax: int, max_ids_per_query: int) -> tuple[int, list[str]]:
        ids: list[str] = []
        retstart = 0
        total_count = 0
        while retstart < max_ids_per_query:
            page_size = min(retmax, max_ids_per_query - retstart)
            record = self.get_json(
                "esearch",
                {"db": "biosample", "term": term, "retmax": page_size, "retstart": retstart},
            )
            result = record.get("esearchresult", {})
            total_count = int(result.get("count", "0") or 0)
            page_ids = list(result.get("idlist", []))
            ids.extend(page_ids)
            if not page_ids or len(ids) >= total_count:
                break
            retstart += len(page_ids)
        return total_count, ids

    def esummary(self, ids: list[str], batch_size: int) -> dict[str, dict[str, Any]]:
        summaries: dict[str, dict[str, Any]] = {}
        for start in range(0, len(ids), batch_size):
            batch = ids[start : start + batch_size]
            record = self.get_json("esummary", {"db": "biosample", "id": ",".join(batch)})
            result = record.get("result", {})
            for uid in result.get("uids", []):
                summaries[uid] = result.get(uid, {})
        return summaries


def parse_xml_fragment(fragment: str) -> ET.Element | None:
    if not fragment:
        return None
    try:
        return ET.fromstring(f"<root>{fragment}</root>")
    except ET.ParseError:
        return None


def xml_attribute_values(root: ET.Element | None) -> list[str]:
    if root is None:
        return []
    values: list[str] = []
    for element in root.iter("Attribute"):
        name = (
            element.get("attribute_name")
            or element.get("harmonized_name")
            or element.get("display_name")
            or "attribute"
        )
        value = clean_text(" ".join(element.itertext()))
        if value:
            values.append(f"{name}: {value}")
    return values


def flatten_biosample(uid: str, summary: dict[str, Any]) -> dict[str, str]:
    sampledata = str(summary.get("sampledata", ""))
    root = parse_xml_fragment(sampledata)
    attributes = xml_attribute_values(root)
    accession = clean_text(summary.get("accession", ""))
    title = clean_text(summary.get("title", ""))
    organism = clean_text(summary.get("organism", ""))
    taxid = clean_text(summary.get("taxonomy", ""))
    identifiers = clean_text(summary.get("identifiers", ""))
    infraspecies = clean_text(summary.get("infraspecies", ""))
    metadata_text = clean_text(" ".join([title, organism, identifiers, infraspecies, sampledata]))
    return {
        "ncbi_db": "biosample",
        "ncbi_uid": uid,
        "ncbi_accession": accession,
        "source_url": f"https://www.ncbi.nlm.nih.gov/biosample/{accession or uid}",
        "title": title,
        "organism": organism,
        "taxid": taxid,
        "identifiers": identifiers,
        "infraspecies": infraspecies,
        "attributes": "; ".join(attributes),
        "metadata_text": metadata_text,
    }


def no_hit_row(spec: dict[str, str], total_count: int) -> dict[str, str]:
    return {
        **spec,
        "ncbi_db": "biosample",
        "id_count_returned": str(total_count),
        "status": "no_hit",
        "error": "",
    }


def error_row(spec: dict[str, str], error: Exception) -> dict[str, str]:
    return {
        **spec,
        "ncbi_db": "biosample",
        "id_count_returned": "",
        "status": "error",
        "error": str(error),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Identifier candidate CSV/TSV from script 09")
    parser.add_argument("--output", required=True, help="Raw BioSample candidate CSV/TSV output path")
    parser.add_argument("--email", default="", help="Optional email for NCBI E-utilities")
    parser.add_argument("--api-key", default="", help="Optional NCBI API key; can also use NCBI_API_KEY")
    parser.add_argument("--delay", type=float, default=0.34, help="Delay between NCBI requests")
    parser.add_argument("--timeout", type=float, default=30.0, help="Network timeout per NCBI request")
    parser.add_argument("--retmax", type=int, default=50, help="IDs per ESearch page")
    parser.add_argument("--max-ids-per-query", type=int, default=100, help="Maximum IDs fetched per query")
    parser.add_argument("--summary-batch-size", type=int, default=200, help="IDs per ESummary request")
    parser.add_argument("--limit-strains", type=int, default=0, help="Optional first-N strain limit")
    parser.add_argument(
        "--no-ncppb-number",
        action="store_true",
        help="Do not add one NCPPB + number query per strain",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Input table not found: {input_path}")

    identifier_rows = read_table(input_path)
    if args.limit_strains > 0:
        allowed: list[str] = []
        for row in identifier_rows:
            ncppb_number = clean_text(row.get("ncppb_number", ""))
            if ncppb_number and ncppb_number not in allowed:
                allowed.append(ncppb_number)
            if len(allowed) >= args.limit_strains:
                break
        allowed_set = set(allowed)
        identifier_rows = [row for row in identifier_rows if row.get("ncppb_number", "") in allowed_set]

    specs = query_specs(identifier_rows, include_ncppb_number=not args.no_ncppb_number)
    client = EntrezClient(
        email=args.email,
        api_key=args.api_key or os.environ.get("NCBI_API_KEY", ""),
        delay=args.delay,
        timeout=args.timeout,
        tool="ncppb_biosample_identifier_harvest",
    )

    rows: list[dict[str, Any]] = []
    for spec in specs:
        try:
            total_count, ids = client.esearch_all(
                spec["search_term"],
                retmax=args.retmax,
                max_ids_per_query=args.max_ids_per_query,
            )
            if not ids:
                rows.append(no_hit_row(spec, total_count))
                continue
            summaries = client.esummary(ids, args.summary_batch_size)
            for uid in ids:
                rows.append(
                    {
                        **spec,
                        **flatten_biosample(uid, summaries.get(uid, {})),
                        "id_count_returned": str(total_count),
                        "status": "ok",
                        "error": "",
                    }
                )
        except Exception as exc:
            rows.append(error_row(spec, exc))

    write_table(output_path, rows)
    print(f"Wrote {len(rows)} raw BioSample rows to {output_path}; {client.request_count} NCBI requests")


if __name__ == "__main__":
    main()
