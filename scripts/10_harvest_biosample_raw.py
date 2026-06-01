#!/usr/bin/env python3
"""Search NCBI BioSample with prepared identifier queries and write raw rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


QUERY_PROFILES = {
    "current_all_fields",
    "strict_xanthomonas",
    "known_collection_strict",
    "broad_review",
}

OUTPUT_COLUMNS = [
    "ncppb_number",
    "query_source",
    "normalized_identifier",
    "prefix",
    "suffix",
    "query_profile",
    "rule_name",
    "confidence",
    "target_organism_filter",
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
    "count_returned",
    "ids_fetched",
    "retmax_saturated",
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


def split_identifier_terms(prefix: str, suffix: str) -> list[str]:
    prefix_terms = [part for part in re.split(r"[^A-Za-z0-9]+", prefix.upper()) if part]
    suffix_terms = [part for part in re.split(r"[^A-Za-z0-9]+", suffix.upper()) if part]
    return [*prefix_terms, *suffix_terms]


def fielded_and_terms(terms: list[str], field: str) -> str:
    return " AND ".join(f"{term}[{field}]" for term in terms)


def with_organism_filter(term: str, target_organism: str) -> str:
    organism = clean_text(target_organism)
    if not organism:
        return term
    return f"({term}) AND {organism}[Organism]"


def query_from_parts(prefix: str, suffix: str, query_profile: str, target_organism: str) -> str:
    terms = split_identifier_terms(prefix, suffix)
    if not terms:
        return ""
    if query_profile == "current_all_fields":
        return fielded_and_terms(terms, "All Fields")
    if query_profile == "broad_review":
        return fielded_and_terms(terms, "Text Word")
    if query_profile in {"strict_xanthomonas", "known_collection_strict"}:
        return with_organism_filter(fielded_and_terms(terms, "Text Word"), target_organism)
    raise ValueError(f"Unsupported query profile: {query_profile}")


def ncppb_query(ncppb_number: str, query_profile: str, target_organism: str) -> tuple[str, str, str, str]:
    digits = ncppb_digits(ncppb_number)
    prefix = "NCPPB"
    return f"NCPPB {digits}", prefix, digits, query_from_parts(prefix, digits, query_profile, target_organism)


def query_specs(
    rows: list[dict[str, str]],
    include_ncppb_number: bool,
    query_profile: str = "strict_xanthomonas",
    target_organism: str = "Xanthomonas",
) -> list[dict[str, str]]:
    if query_profile not in QUERY_PROFILES:
        raise ValueError(f"Unsupported query profile: {query_profile}")

    specs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    strain_order: list[str] = []

    for row in rows:
        ncppb_number = clean_text(row.get("ncppb_number", ""))
        if ncppb_number and ncppb_number not in strain_order:
            strain_order.append(ncppb_number)

    if include_ncppb_number:
        for ncppb_number in strain_order:
            normalized, prefix, suffix, term = ncppb_query(ncppb_number, query_profile, target_organism)
            if not term:
                continue
            key = (ncppb_number, query_profile, term)
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
                    "query_profile": query_profile,
                    "rule_name": "ncppb_number",
                    "confidence": "high",
                    "target_organism_filter": clean_text(target_organism),
                    "search_term": term,
                }
            )

    for row in rows:
        if clean_text(row.get("include_for_search", "")).lower() != "yes":
            continue
        rule_name = clean_text(row.get("rule_name", ""))
        confidence = clean_text(row.get("confidence", ""))
        if query_profile == "known_collection_strict" and not (
            rule_name == "known_collection_prefix" and confidence == "high"
        ):
            continue

        ncppb_number = clean_text(row.get("ncppb_number", ""))
        prefix = clean_text(row.get("prefix", ""))
        suffix = clean_text(row.get("suffix", ""))
        if query_profile == "current_all_fields":
            stored_term = clean_text(row.get("biosample_query", ""))
            term = stored_term if "[All Fields]" in stored_term else query_from_parts(prefix, suffix, query_profile, target_organism)
        else:
            term = query_from_parts(prefix, suffix, query_profile, target_organism)
        if not ncppb_number or not term:
            continue
        key = (ncppb_number, query_profile, term)
        if key in seen:
            continue
        seen.add(key)
        specs.append(
            {
                "ncppb_number": ncppb_number,
                "query_source": "other_reference",
                "normalized_identifier": clean_text(row.get("normalized_identifier", "")),
                "prefix": prefix,
                "suffix": suffix,
                "query_profile": query_profile,
                "rule_name": rule_name,
                "confidence": confidence,
                "target_organism_filter": clean_text(target_organism),
                "search_term": term,
            }
        )

    return specs


class EntrezClient:
    def __init__(self, email: str, api_key: str, delay: float, timeout: float, tool: str, cache_dir: Path | None = None) -> None:
        self.email = email
        self.api_key = api_key
        self.delay = delay
        self.timeout = timeout
        self.tool = tool
        self.cache_dir = cache_dir
        self.request_count = 0
        self.cache_hits = 0
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_path(self, endpoint: str, params: dict[str, Any]) -> Path | None:
        if self.cache_dir is None:
            return None
        cache_key = {
            "endpoint": endpoint,
            "params": {key: value for key, value in sorted(params.items())},
        }
        digest = hashlib.sha256(json.dumps(cache_key, sort_keys=True).encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        cache_path = self.cache_path(endpoint, params)
        if cache_path is not None and cache_path.exists():
            self.cache_hits += 1
            return json.loads(cache_path.read_text(encoding="utf-8"))

        time.sleep(self.delay)
        query = {"tool": self.tool, "retmode": "json", **params}
        if self.email:
            query["email"] = self.email
        if self.api_key:
            query["api_key"] = self.api_key
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{endpoint}.fcgi?{urlencode(query)}"
        self.request_count += 1
        with urlopen(url, timeout=self.timeout) as handle:
            data = json.loads(handle.read().decode("utf-8"), strict=False)
        if cache_path is not None:
            cache_path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        return data

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


def count_metadata(total_count: int, ids: list[str], max_ids_per_query: int) -> dict[str, str]:
    ids_fetched = len(ids)
    return {
        "count_returned": str(total_count),
        "ids_fetched": str(ids_fetched),
        "retmax_saturated": "yes" if total_count > ids_fetched and ids_fetched >= max_ids_per_query else "no",
        "id_count_returned": str(total_count),
    }


def no_hit_row(spec: dict[str, str], total_count: int, max_ids_per_query: int) -> dict[str, str]:
    return {
        **spec,
        "ncbi_db": "biosample",
        **count_metadata(total_count, [], max_ids_per_query),
        "status": "no_hit",
        "error": "",
    }


def error_row(spec: dict[str, str], error: Exception) -> dict[str, str]:
    return {
        **spec,
        "ncbi_db": "biosample",
        "count_returned": "",
        "ids_fetched": "",
        "retmax_saturated": "",
        "id_count_returned": "",
        "status": "error",
        "error": str(error),
    }


def output_columns() -> list[str]:
    return list(OUTPUT_COLUMNS)


def completed_query_keys(rows: list[dict[str, str]]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for row in rows:
        ncppb = clean_text(row.get("ncppb_number", ""))
        profile = clean_text(row.get("query_profile", ""))
        term = clean_text(row.get("search_term", ""))
        if ncppb and term:
            keys.add((ncppb, profile, term))
    return keys


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
    parser.add_argument("--query-profile", choices=sorted(QUERY_PROFILES), default="strict_xanthomonas")
    parser.add_argument(
        "--target-organism",
        default="Xanthomonas",
        help="Optional organism filter used by strict profiles; set empty for full-NCPPB batches",
    )
    parser.add_argument("--cache-dir", default="", help="Optional local JSON cache directory for NCBI E-utilities")
    parser.add_argument("--resume", action="store_true", help="Skip query/profile/term combinations already present in output")
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

    specs = query_specs(
        identifier_rows,
        include_ncppb_number=not args.no_ncppb_number,
        query_profile=args.query_profile,
        target_organism=args.target_organism,
    )

    rows: list[dict[str, Any]] = []
    if args.resume and output_path.exists():
        rows = read_table(output_path)
        done = completed_query_keys(rows)
        specs = [spec for spec in specs if (spec["ncppb_number"], spec["query_profile"], spec["search_term"]) not in done]

    client = EntrezClient(
        email=args.email,
        api_key=args.api_key or os.environ.get("NCBI_API_KEY", ""),
        delay=args.delay,
        timeout=args.timeout,
        tool="ncppb_biosample_identifier_harvest",
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )

    for spec in specs:
        try:
            total_count, ids = client.esearch_all(
                spec["search_term"],
                retmax=args.retmax,
                max_ids_per_query=args.max_ids_per_query,
            )
            if not ids:
                rows.append(no_hit_row(spec, total_count, args.max_ids_per_query))
                continue
            summaries = client.esummary(ids, args.summary_batch_size)
            metadata = count_metadata(total_count, ids, args.max_ids_per_query)
            for uid in ids:
                rows.append(
                    {
                        **spec,
                        **flatten_biosample(uid, summaries.get(uid, {})),
                        **metadata,
                        "status": "ok",
                        "error": "",
                    }
                )
        except Exception as exc:
            rows.append(error_row(spec, exc))

    write_table(output_path, rows)
    print(
        f"Wrote {len(rows)} raw BioSample rows to {output_path}; "
        f"{client.request_count} NCBI requests; {client.cache_hits} cache hits"
    )


if __name__ == "__main__":
    main()
