#!/usr/bin/env python3
"""Expand accepted BioSample matches to linked SRA/SRR, BioProject, and BioCollections records."""

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
    "biosample_uid",
    "biosample_accession",
    "biosample_title",
    "organism",
    "taxid",
    "matched_identifier",
    "matched_identifier_type",
    "sra_sample_accessions",
    "sra_uids",
    "sra_experiment_accessions",
    "run_accessions",
    "srr_accessions",
    "sra_library_strategies",
    "bioproject_uids",
    "bioproject_accessions",
    "bioproject_titles",
    "biocollection_terms",
    "biocollection_prefixes",
    "biocollection_uids",
    "biocollection_summaries",
    "link_evidence",
    "status",
    "error",
]

BIOPROJECT_RE = re.compile(r"\bPRJ[A-Z]{2}\d+\b", re.IGNORECASE)
RUN_RE = re.compile(r"\b[SED]RR\d+\b", re.IGNORECASE)
SRA_SAMPLE_RE = re.compile(r"\b[SED]RS\d+\b", re.IGNORECASE)
EXPERIMENT_RE = re.compile(r"\b[SED]RX\d+\b", re.IGNORECASE)
BIOCOLLECTION_PREFIX_RE = re.compile(r"\b([A-Z][A-Z0-9-]{1,12})\s*[:#]?\s*[A-Z]*\d", re.IGNORECASE)


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


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def join_values(values: list[str]) -> str:
    return "; ".join(unique(values))


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
        query = {"tool": self.tool, "email": self.email, "retmode": "json", **params}
        if self.api_key:
            query["api_key"] = self.api_key
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{endpoint}.fcgi?{urlencode(query)}"
        self.request_count += 1
        with urlopen(url, timeout=self.timeout) as handle:
            return json.loads(handle.read().decode("utf-8"), strict=False)

    def esearch(self, db: str, term: str, retmax: int) -> list[str]:
        record = self.get_json("esearch", {"db": db, "term": term, "retmax": retmax})
        return list(record.get("esearchresult", {}).get("idlist", []))

    def esummary(self, db: str, ids: list[str], batch_size: int) -> dict[str, dict[str, Any]]:
        summaries: dict[str, dict[str, Any]] = {}
        for start in range(0, len(ids), batch_size):
            batch = ids[start : start + batch_size]
            if not batch:
                continue
            record = self.get_json("esummary", {"db": db, "id": ",".join(batch)})
            result = record.get("result", {})
            for uid in result.get("uids", []):
                summaries[uid] = result.get(uid, {})
        return summaries

    def elink(self, dbfrom: str, db: str, uid: str) -> list[str]:
        record = self.get_json("elink", {"dbfrom": dbfrom, "db": db, "id": uid})
        ids: list[str] = []
        for linkset in record.get("linksets", []):
            for linksetdb in linkset.get("linksetdbs", []):
                for linked in linksetdb.get("links", []):
                    ids.append(str(linked))
        return unique(ids)


def parse_xml_fragment(fragment: str) -> ET.Element | None:
    if not fragment:
        return None
    try:
        return ET.fromstring(f"<root>{fragment}</root>")
    except ET.ParseError:
        return None


def first_xml_text(root: ET.Element | None, path: str) -> str:
    if root is None:
        return ""
    element = root.find(path)
    if element is None:
        return ""
    return clean_text(" ".join(element.itertext()))


def first_xml_attr(root: ET.Element | None, path: str, attr: str) -> str:
    if root is None:
        return ""
    element = root.find(path)
    return clean_text(element.get(attr, "")) if element is not None else ""


def all_xml_attrs(root: ET.Element | None, path: str, attr: str) -> list[str]:
    if root is None:
        return []
    return unique([element.get(attr, "") or "" for element in root.findall(path)])


def all_xml_text(root: ET.Element | None, path: str) -> list[str]:
    if root is None:
        return []
    return unique([clean_text(" ".join(element.itertext())) for element in root.findall(path)])


def ids_from_biosample_xml(root: ET.Element | None, db_name: str) -> list[str]:
    if root is None:
        return []
    values: list[str] = []
    for element in root.findall(".//Id"):
        if (element.get("db") or "").lower() == db_name.lower():
            values.append(clean_text(" ".join(element.itertext())))
    return unique(values)


def bioproject_links_from_biosample_xml(root: ET.Element | None) -> tuple[list[str], list[str]]:
    if root is None:
        return [], []
    uids: list[str] = []
    accessions: list[str] = []
    for link in root.findall(".//Link"):
        if (link.get("target") or "").lower() != "bioproject":
            continue
        uids.append(clean_text(" ".join(link.itertext())))
        accessions.extend(BIOPROJECT_RE.findall(link.get("label", "") or ""))
    return unique(uids), unique([value.upper() for value in accessions])


def biocollection_terms_from_biosample_xml(root: ET.Element | None) -> list[str]:
    if root is None:
        return []
    terms: list[str] = []
    for element in root.iter("Attribute"):
        names = " ".join(
            [
                element.get("attribute_name", ""),
                element.get("harmonized_name", ""),
                element.get("display_name", ""),
            ]
        ).lower()
        if not any(token in names for token in ["culture_collection", "culture collection", "specimen_voucher", "voucher", "bio_material"]):
            continue
        value = clean_text(" ".join(element.itertext()))
        if value:
            terms.append(value)
    return unique(terms)


def biocollection_prefixes(terms: list[str]) -> list[str]:
    prefixes: list[str] = []
    for term in terms:
        for match in BIOCOLLECTION_PREFIX_RE.finditer(term):
            prefixes.append(match.group(1).upper())
    return unique(prefixes)


def parse_biosample_summary(uid: str, summary: dict[str, Any]) -> dict[str, Any]:
    sampledata = str(summary.get("sampledata", ""))
    root = parse_xml_fragment(sampledata)
    bioproject_uids, bioproject_accessions = bioproject_links_from_biosample_xml(root)
    biocollection_terms = biocollection_terms_from_biosample_xml(root)
    identifiers_text = clean_text(summary.get("identifiers", ""))
    return {
        "biosample_uid": uid,
        "biosample_accession": clean_text(summary.get("accession", "")),
        "biosample_title": clean_text(summary.get("title", "")),
        "organism": clean_text(summary.get("organism", "")),
        "taxid": clean_text(summary.get("taxonomy", "")),
        "sra_sample_accessions": unique(
            ids_from_biosample_xml(root, "SRA") + [value.upper() for value in SRA_SAMPLE_RE.findall(identifiers_text)]
        ),
        "bioproject_uids": bioproject_uids,
        "bioproject_accessions": bioproject_accessions,
        "biocollection_terms": biocollection_terms,
        "biocollection_prefixes": biocollection_prefixes(biocollection_terms),
    }


def parse_sra_summaries(summaries: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    sra_uids: list[str] = []
    experiments: list[str] = []
    runs: list[str] = []
    strategies: list[str] = []
    bioprojects: list[str] = []
    biosamples: list[str] = []

    for uid, summary in summaries.items():
        sra_uids.append(uid)
        expxml = str(summary.get("expxml", ""))
        runs_xml = str(summary.get("runs", ""))
        root = parse_xml_fragment(expxml + runs_xml)
        experiments.extend(all_xml_attrs(root, ".//Experiment", "acc"))
        runs.extend(all_xml_attrs(root, ".//Run", "acc"))
        strategies.extend(all_xml_text(root, ".//LIBRARY_STRATEGY"))
        bioprojects.extend(BIOPROJECT_RE.findall(" ".join(all_xml_text(root, ".//Bioproject"))))
        biosamples.extend(SRA_SAMPLE_RE.findall(" ".join([expxml, runs_xml])))
    return {
        "sra_uids": unique(sra_uids),
        "sra_experiment_accessions": unique([value.upper() for value in experiments]),
        "run_accessions": unique([value.upper() for value in runs]),
        "srr_accessions": unique([value.upper() for value in runs if value.upper().startswith("SRR")]),
        "sra_library_strategies": unique(strategies),
        "bioproject_accessions": unique([value.upper() for value in bioprojects]),
        "sra_sample_accessions": unique([value.upper() for value in biosamples]),
    }


def nested_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        output: list[str] = []
        for child in value.values():
            output.extend(nested_strings(child))
        return output
    if isinstance(value, list):
        output = []
        for child in value:
            output.extend(nested_strings(child))
        return output
    return [str(value)] if value is not None else []


def parse_bioproject_summaries(summaries: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    accessions: list[str] = []
    titles: list[str] = []
    for summary in summaries.values():
        strings = nested_strings(summary)
        accessions.extend(BIOPROJECT_RE.findall(" ".join(strings)))
        for key in ["project_title", "project_name", "title", "name"]:
            value = clean_text(summary.get(key, ""))
            if value and not BIOPROJECT_RE.fullmatch(value):
                titles.append(value)
    return unique([value.upper() for value in accessions]), unique(titles)


def parse_biocollection_summaries(summaries: dict[str, dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for uid, summary in summaries.items():
        strings = [clean_text(value) for value in nested_strings(summary) if clean_text(value)]
        head = "; ".join(unique(strings)[:4])
        labels.append(f"{uid}: {head}" if head else uid)
    return unique(labels)


def selected_biosample_rows(rows: list[dict[str, str]], limit_strains: int, only_ncppb: set[str] | None = None) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_strains: set[str] = set()
    for row in rows:
        ncppb_number = row.get("ncppb_number", "")
        if only_ncppb and ncppb_number not in only_ncppb:
            continue
        if row.get("evidence_level", "") != "strong_strain_match":
            continue
        accession = clean_text(row.get("biosample_accession") or row.get("ncbi_accession", ""))
        uid = clean_text(row.get("ncbi_uid", ""))
        db = clean_text(row.get("ncbi_db", ""))
        if db and db != "biosample" and not accession:
            continue
        key = accession or uid
        pair = (ncppb_number, key)
        if not key or pair in seen_pairs:
            continue
        if limit_strains > 0 and ncppb_number not in seen_strains and len(seen_strains) >= limit_strains:
            continue
        seen_pairs.add(pair)
        seen_strains.add(ncppb_number)
        selected.append(row)
    return selected


def resolve_biosample_uid(client: EntrezClient, row: dict[str, str]) -> str:
    uid = clean_text(row.get("ncbi_uid", ""))
    db = clean_text(row.get("ncbi_db", ""))
    if uid and (not db or db == "biosample"):
        return uid
    accession = clean_text(row.get("biosample_accession") or row.get("ncbi_accession", ""))
    if not accession:
        return ""
    ids = client.esearch("biosample", f"{accession}[All Fields]", retmax=5)
    return ids[0] if ids else ""


def linked_ids(client: EntrezClient, db: str, biosample_uid: str, errors: list[str]) -> list[str]:
    try:
        return client.elink("biosample", db, biosample_uid)
    except Exception as exc:
        errors.append(f"elink biosample->{db}: {exc}")
        return []


def summarize_linked_records(
    client: EntrezClient,
    biosample_uid: str,
    biosample_summary: dict[str, Any],
    batch_size: int,
    biocollections_retmax: int,
    skip_biocollections_search: bool,
    include_elink_bioprojects: bool,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    parsed = parse_biosample_summary(biosample_uid, biosample_summary)

    sra_uids = linked_ids(client, "sra", biosample_uid, errors)
    sra_data = parse_sra_summaries(client.esummary("sra", sra_uids, batch_size)) if sra_uids else {}

    bioproject_uids = list(parsed["bioproject_uids"])
    if include_elink_bioprojects:
        bioproject_uids = unique(bioproject_uids + linked_ids(client, "bioproject", biosample_uid, errors))
    bioproject_accessions = list(parsed["bioproject_accessions"])
    bioproject_titles: list[str] = []
    if bioproject_uids:
        parsed_accessions, parsed_titles = parse_bioproject_summaries(client.esummary("bioproject", bioproject_uids, batch_size))
        bioproject_accessions = unique(bioproject_accessions + parsed_accessions)
        bioproject_titles = parsed_titles
    bioproject_accessions = unique(bioproject_accessions + sra_data.get("bioproject_accessions", []))

    biocollection_uids = linked_ids(client, "biocollections", biosample_uid, errors)
    if not skip_biocollections_search:
        for prefix in parsed["biocollection_prefixes"]:
            try:
                biocollection_uids.extend(client.esearch("biocollections", f"{prefix}[All Fields]", biocollections_retmax))
            except Exception as exc:
                errors.append(f"esearch biocollections {prefix}: {exc}")
    biocollection_uids = unique(biocollection_uids)
    biocollection_summaries = (
        parse_biocollection_summaries(client.esummary("biocollections", biocollection_uids, batch_size))
        if biocollection_uids
        else []
    )

    linked = {
        **parsed,
        "sra_sample_accessions": unique(parsed["sra_sample_accessions"] + sra_data.get("sra_sample_accessions", [])),
        "sra_uids": sra_data.get("sra_uids", []),
        "sra_experiment_accessions": sra_data.get("sra_experiment_accessions", []),
        "run_accessions": sra_data.get("run_accessions", []),
        "srr_accessions": sra_data.get("srr_accessions", []),
        "sra_library_strategies": sra_data.get("sra_library_strategies", []),
        "bioproject_uids": bioproject_uids,
        "bioproject_accessions": bioproject_accessions,
        "bioproject_titles": bioproject_titles,
        "biocollection_uids": biocollection_uids,
        "biocollection_summaries": biocollection_summaries,
    }
    return linked, errors


def output_row(match_row: dict[str, str], linked: dict[str, Any], errors: list[str]) -> dict[str, str]:
    evidence_parts = []
    for label in ["sra_sample_accessions", "run_accessions", "bioproject_accessions", "biocollection_terms"]:
        values = linked.get(label, [])
        if values:
            evidence_parts.append(f"{label}={join_values(values)}")
    return {
        "ncppb_number": clean_text(match_row.get("ncppb_number", "")),
        "biosample_uid": clean_text(linked.get("biosample_uid", "")),
        "biosample_accession": clean_text(linked.get("biosample_accession", "")),
        "biosample_title": clean_text(linked.get("biosample_title", "")),
        "organism": clean_text(linked.get("organism", "")),
        "taxid": clean_text(linked.get("taxid", "")),
        "matched_identifier": clean_text(match_row.get("matched_identifier", "")),
        "matched_identifier_type": clean_text(match_row.get("matched_identifier_type", "")),
        "sra_sample_accessions": join_values(linked.get("sra_sample_accessions", [])),
        "sra_uids": join_values(linked.get("sra_uids", [])),
        "sra_experiment_accessions": join_values(linked.get("sra_experiment_accessions", [])),
        "run_accessions": join_values(linked.get("run_accessions", [])),
        "srr_accessions": join_values(linked.get("srr_accessions", [])),
        "sra_library_strategies": join_values(linked.get("sra_library_strategies", [])),
        "bioproject_uids": join_values(linked.get("bioproject_uids", [])),
        "bioproject_accessions": join_values(linked.get("bioproject_accessions", [])),
        "bioproject_titles": join_values(linked.get("bioproject_titles", [])),
        "biocollection_terms": join_values(linked.get("biocollection_terms", [])),
        "biocollection_prefixes": join_values(linked.get("biocollection_prefixes", [])),
        "biocollection_uids": join_values(linked.get("biocollection_uids", [])),
        "biocollection_summaries": join_values(linked.get("biocollection_summaries", [])),
        "link_evidence": " | ".join(evidence_parts),
        "status": "ok" if not errors else "partial",
        "error": " | ".join(errors),
    }


def error_row(match_row: dict[str, str], error: Exception) -> dict[str, str]:
    return {
        "ncppb_number": clean_text(match_row.get("ncppb_number", "")),
        "biosample_uid": clean_text(match_row.get("ncbi_uid", "")),
        "biosample_accession": clean_text(match_row.get("biosample_accession") or match_row.get("ncbi_accession", "")),
        "matched_identifier": clean_text(match_row.get("matched_identifier", "")),
        "matched_identifier_type": clean_text(match_row.get("matched_identifier_type", "")),
        "status": "error",
        "error": str(error),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches-input", required=True, help="Accepted BioSample matches CSV/TSV from script 11")
    parser.add_argument("--output", required=True, help="BioSample-centred linked record CSV/TSV output path")
    parser.add_argument("--email", required=True, help="Email required by NCBI E-utilities")
    parser.add_argument("--api-key", default="", help="Optional NCBI API key; can also use NCBI_API_KEY")
    parser.add_argument("--delay", type=float, default=0.34, help="Delay between NCBI requests")
    parser.add_argument("--timeout", type=float, default=30.0, help="Network timeout per NCBI request")
    parser.add_argument("--summary-batch-size", type=int, default=200, help="IDs per ESummary request")
    parser.add_argument("--limit-strains", type=int, default=0, help="Optional first-N strain limit")
    parser.add_argument(
        "--only-ncppb",
        default="",
        help="Optional comma-separated NCPPB numbers to expand, for example 'NCPPB 556,NCPPB 101'",
    )
    parser.add_argument("--biocollections-retmax", type=int, default=5, help="BioCollections IDs per prefix search")
    parser.add_argument(
        "--skip-biocollections-search",
        action="store_true",
        help="Only parse BioCollection/culture collection terms from BioSample; do not search NCBI BioCollections",
    )
    parser.add_argument(
        "--include-elink-bioprojects",
        action="store_true",
        help="Also include BioProject IDs returned by BioSample->BioProject ELink; these can include indirect projects",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.matches_input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Matches input not found: {input_path}")

    only_ncppb = {clean_text(value) for value in args.only_ncppb.split(",") if clean_text(value)}
    match_rows = selected_biosample_rows(read_table(input_path), args.limit_strains, only_ncppb or None)
    client = EntrezClient(
        email=args.email,
        api_key=args.api_key or os.environ.get("NCBI_API_KEY", ""),
        delay=args.delay,
        timeout=args.timeout,
        tool="ncppb_biosample_link_expander",
    )

    output_rows: list[dict[str, str]] = []
    for match_row in match_rows:
        try:
            biosample_uid = resolve_biosample_uid(client, match_row)
            if not biosample_uid:
                raise RuntimeError("could not resolve BioSample UID")
            biosample_summary = client.esummary("biosample", [biosample_uid], args.summary_batch_size).get(biosample_uid, {})
            linked, errors = summarize_linked_records(
                client=client,
                biosample_uid=biosample_uid,
                biosample_summary=biosample_summary,
                batch_size=args.summary_batch_size,
                biocollections_retmax=args.biocollections_retmax,
                skip_biocollections_search=args.skip_biocollections_search,
                include_elink_bioprojects=args.include_elink_bioprojects,
            )
            output_rows.append(output_row(match_row, linked, errors))
        except Exception as exc:
            output_rows.append(error_row(match_row, exc))

    write_table(output_path, output_rows)
    print(f"Wrote {len(output_rows)} linked BioSample rows to {output_path}; {client.request_count} NCBI requests")


if __name__ == "__main__":
    main()
