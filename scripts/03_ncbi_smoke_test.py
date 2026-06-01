#!/usr/bin/env python3
"""Run an identifier-first NCBI BioSample harvest.

The script searches BioSample metadata using strain identifiers only, then
validates returned metadata. It does not use organism names for harvest and does
not download sequence files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

HARVEST_DBS = ["biosample"]
NCPPB_NUMBER_RE = re.compile(
    r"\bNCPPB(?:\s*(?:No\.?|Number|#|:|-|_))?\s*0*(\d{1,5})(?!\d)",
    re.IGNORECASE,
)
XANTHOMONAS_RE = re.compile(r"\bXanthomonas\b", re.IGNORECASE)
COLLECTION_ID_RE = re.compile(
    r"\b(ATCC|BCCM|CCUG|CFBP|CIP|DSMZ?|ICMP|JCM|LMG|NCTC|NIB|NRRL|PDDCC|PD|RIV|UQM|VKM|WDCM)"
    r"\s*[-:]?\s*([A-Z]*\d+[A-Z0-9.-]*)\b",
    re.IGNORECASE,
)
REFERENCE_ID_RE = re.compile(r"\b([A-Z]{2,10})\s*[-:]?\s*(\d+[A-Z0-9.-]*)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Identifier:
    value: str
    identifier_type: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class SearchKeyword:
    source: str
    value: str


@dataclass(frozen=True)
class StrainContext:
    ncppb_number: str
    ncppb_digits: str
    current_name: str
    name_as_received: str
    alternative_names: str
    pathovar: str
    other_references: str
    raw_record_text: str
    identifiers: tuple[Identifier, ...]


@dataclass(frozen=True)
class Classification:
    evidence_level: str
    matched_identifier: str = ""
    matched_identifier_type: str = ""
    reject_reason: str = ""


@dataclass(frozen=True)
class QuerySpec:
    tier: str
    label: str
    db: str
    term: str
    allow_match: bool = True


@dataclass(frozen=True)
class EntrezConfig:
    email: str
    tool: str
    api_key: str
    delay: float
    timeout: float


class EntrezClient:
    """Small cached E-utilities client using only the Python standard library."""

    def __init__(self, config: EntrezConfig) -> None:
        self.config = config
        self.search_cache: dict[tuple[str, str, int, int], list[str]] = {}
        self.summary_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.request_count = 0

    def get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        time.sleep(self.config.delay)
        query = {
            "tool": self.config.tool,
            "email": self.config.email,
            "retmode": "json",
            **params,
        }
        if self.config.api_key:
            query["api_key"] = self.config.api_key
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{endpoint}.fcgi?{urlencode(query)}"
        self.request_count += 1
        with urlopen(url, timeout=self.config.timeout) as handle:
            return json.loads(handle.read().decode("utf-8"))

    def esearch(self, db: str, term: str, retmax: int) -> list[str]:
        return self.esearch_all(db, term, retmax, retmax)

    def esearch_all(self, db: str, term: str, page_size: int, max_ids: int) -> list[str]:
        cache_key = (db, term, page_size, max_ids)
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]
        ids: list[str] = []
        retstart = 0
        while retstart < max_ids:
            retmax = min(page_size, max_ids - retstart)
            record = self.get_json(
                "esearch",
                {"db": db, "term": term, "retmax": retmax, "retstart": retstart},
            )
            result = record.get("esearchresult", {})
            page_ids = list(result.get("idlist", []))
            ids.extend(page_ids)
            total_count = int(result.get("count", "0") or 0)
            if not page_ids or len(ids) >= total_count:
                break
            retstart += len(page_ids)
        self.search_cache[cache_key] = ids
        return ids

    def esummary(self, db: str, ids: list[str], batch_size: int) -> dict[str, dict[str, Any]]:
        missing = [uid for uid in ids if (db, uid) not in self.summary_cache]
        for start in range(0, len(missing), batch_size):
            batch = missing[start : start + batch_size]
            record = self.get_json("esummary", {"db": db, "id": ",".join(batch)})
            result = record.get("result", {})
            for uid in result.get("uids", []):
                self.summary_cache[(db, uid)] = result.get(uid, {})
        return {uid: self.summary_cache.get((db, uid), {}) for uid in ids}


def compact_spaces(value: object) -> str:
    return " ".join(str(value or "").split())


def table_separator(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=table_separator(path))
        return [{key: value or "" for key, value in row.items()} for row in reader]


def write_table(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=table_separator(path))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def first_unique(values: list[str], limit: int) -> list[str]:
    seen = set()
    selected = []
    for value in values:
        if value in seen or not value:
            continue
        seen.add(value)
        selected.append(value)
        if len(selected) >= limit:
            break
    return selected


def split_multi(value: object) -> list[str]:
    text = compact_spaces(value)
    if not text or text.lower() == "nan":
        return []
    return [part.strip() for part in text.replace("|", ";").split(";") if part.strip()]


def ncppb_digits(value: object) -> str:
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else ""


def ncppb_identifier_pattern(digits: str) -> re.Pattern[str]:
    return re.compile(
        rf"\bNCPPB(?:\s*(?:No\.?|Number|#|:|-|_))?\s*0*{re.escape(digits)}(?!\d)",
        re.IGNORECASE,
    )


def collection_identifier_pattern(identifier: str) -> re.Pattern[str]:
    text = compact_spaces(identifier)
    match = re.match(r"^([A-Za-z]+)\s+(.+)$", text)
    if not match:
        return re.compile(rf"(?<![A-Za-z0-9]){re.escape(text)}(?![A-Za-z0-9])", re.IGNORECASE)

    prefix, suffix = match.groups()
    suffix_parts = [part for part in re.split(r"[\s:_-]+", suffix) if part]
    suffix_pattern = r"\s*[:_-]?\s*".join(re.escape(part) for part in suffix_parts)
    return re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(prefix)}\s*[:_-]?\s*{suffix_pattern}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def collection_identifiers_from_text(text: object) -> list[str]:
    identifiers: list[str] = []
    seen: set[str] = set()
    for pattern in [COLLECTION_ID_RE, REFERENCE_ID_RE]:
        for match in pattern.finditer(str(text or "")):
            prefix, suffix = match.groups()
            identifier = f"{prefix.upper()} {suffix.upper()}"
            if identifier in seen:
                continue
            seen.add(identifier)
            identifiers.append(identifier)
    return identifiers


def ncppb_identifier_value(digits: str) -> str:
    return f"NCPPB {digits}" if digits else ""


def identifier_parts(identifier: str) -> tuple[str, str]:
    text = compact_spaces(identifier).upper()
    match = re.match(r"^([A-Z]{2,10})\s*[-:]?\s*(\d+[A-Z0-9.-]*)$", text)
    if not match:
        return ("", "")
    return match.group(1), match.group(2)


def identifier_query_term(identifier: str) -> str:
    prefix, suffix = identifier_parts(identifier)
    if not prefix or not suffix:
        return compact_spaces(identifier)
    return f"{prefix}[All Fields] AND {suffix}[All Fields]"


def is_ncppb_identifier(identifier: str) -> bool:
    prefix, _ = identifier_parts(identifier)
    return prefix == "NCPPB"


def searchable_reference_identifiers(context: StrainContext) -> list[Identifier]:
    output: list[Identifier] = []
    for identifier in context.identifiers:
        if identifier.identifier_type == "ncppb_number":
            output.append(identifier)
            continue
        if identifier.identifier_type == "other_collection_number":
            output.append(identifier)
            continue
        if identifier.identifier_type == "other_reference_identifier":
            output.append(identifier)
    return output


def add_reference_identifiers_from_text(identifiers: list[Identifier], text: object) -> None:
    for other in collection_identifiers_from_text(text):
        if is_ncppb_identifier(other):
            continue
        add_identifier(identifiers, other, "other_reference_identifier")


def collection_identifiers_from_known_fields(text: object) -> list[str]:
    identifiers: list[str] = []
    seen: set[str] = set()
    for match in COLLECTION_ID_RE.finditer(str(text or "")):
        prefix, suffix = match.groups()
        identifier = f"{prefix.upper()} {suffix.upper()}"
        if identifier in seen:
            continue
        seen.add(identifier)
        identifiers.append(identifier)
    return identifiers


def add_identifier(identifiers: list[Identifier], value: str, identifier_type: str) -> None:
    value = compact_spaces(value)
    if not value:
        return
    key = value.upper()
    if any(existing.value.upper() == key for existing in identifiers):
        return
    identifiers.append(Identifier(value, identifier_type, collection_identifier_pattern(value)))


def make_strain_context(master_row: dict[str, str]) -> StrainContext:
    ncppb_number = compact_spaces(master_row.get("ncppb_number", ""))
    digits = ncppb_digits(ncppb_number)
    identifiers: list[Identifier] = []

    if digits:
        identifiers.append(
            Identifier(f"NCPPB {digits}", "ncppb_number", ncppb_identifier_pattern(digits))
        )
    for other in split_multi(master_row.get("other_collection_numbers", "")):
        add_identifier(identifiers, other, "other_collection_number")
    add_reference_identifiers_from_text(identifiers, master_row.get("other_references", ""))
    for other in collection_identifiers_from_known_fields(master_row.get("raw_record_text", "")):
        if not is_ncppb_identifier(other):
            add_identifier(identifiers, other, "other_reference_identifier")

    return StrainContext(
        ncppb_number=ncppb_number,
        ncppb_digits=digits,
        current_name=compact_spaces(master_row.get("current_name", "")),
        name_as_received=compact_spaces(master_row.get("name_as_received", "")),
        alternative_names=compact_spaces(master_row.get("alternative_names", "")),
        pathovar=compact_spaces(master_row.get("pathovar", "")),
        other_references=compact_spaces(master_row.get("other_references", "")),
        raw_record_text=compact_spaces(master_row.get("raw_record_text", "")),
        identifiers=tuple(identifiers),
    )


def find_ncppb_numbers(text: str) -> set[str]:
    return {match.group(1).lstrip("0") or "0" for match in NCPPB_NUMBER_RE.finditer(text)}


def classify_candidate(context: StrainContext, metadata: dict[str, str]) -> Classification:
    organism = metadata.get("organism", "")
    metadata_text = compact_spaces(metadata.get("metadata_text", ""))

    if organism and not XANTHOMONAS_RE.search(organism):
        return Classification("ambiguous", reject_reason="non_xanthomonas_organism")

    for identifier in context.identifiers:
        if identifier.pattern.search(metadata_text):
            return Classification(
                "strong_strain_match",
                matched_identifier=identifier.value,
                matched_identifier_type=identifier.identifier_type,
            )

    conflicting_ncppb = sorted(find_ncppb_numbers(metadata_text) - {context.ncppb_digits})
    if conflicting_ncppb:
        return Classification(
            "ambiguous",
            reject_reason=f"conflicting_ncppb_number:{';'.join(conflicting_ncppb)}",
        )

    if organism and XANTHOMONAS_RE.search(organism):
        return Classification("taxon_level_only", reject_reason="no_exact_strain_identifier_match")

    return Classification("ambiguous", reject_reason="no_organism_or_strain_identifier")


def keyword_search_term(keyword: str) -> str:
    return compact_spaces(keyword)


def add_keyword(keywords: list[SearchKeyword], source: str, value: str) -> None:
    value = compact_spaces(value)
    if not value:
        return
    keywords.append(SearchKeyword(source, value))


def build_harvest_keywords(context: StrainContext) -> list[SearchKeyword]:
    keywords: list[SearchKeyword] = []

    if context.ncppb_digits:
        add_keyword(keywords, "ncppb_number", ncppb_identifier_value(context.ncppb_digits))

    for identifier in searchable_reference_identifiers(context):
        if identifier.identifier_type == "ncppb_number":
            continue
        add_keyword(keywords, identifier.identifier_type, identifier.value)

    seen: set[str] = set()
    unique_keywords: list[SearchKeyword] = []
    for keyword in keywords:
        key = keyword.value.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_keywords.append(keyword)
    return unique_keywords


def build_harvest_queries(context: StrainContext, dbs: list[str]) -> list[QuerySpec]:
    queries: list[QuerySpec] = []
    for keyword in build_harvest_keywords(context):
        for db in dbs:
            queries.append(
                QuerySpec(
                    tier="recall_harvest",
                    label=keyword.source,
                    db=db,
                    term=identifier_query_term(keyword.value),
                )
            )
    return queries


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
    return compact_spaces(" ".join(element.itertext()))


def first_xml_attr(root: ET.Element | None, path: str, attr: str) -> str:
    if root is None:
        return ""
    element = root.find(path)
    return compact_spaces(element.get(attr, "")) if element is not None else ""


def xml_attribute_values(root: ET.Element | None) -> list[str]:
    if root is None:
        return []
    values = []
    for element in root.iter("Attribute"):
        name = (
            element.get("attribute_name")
            or element.get("harmonized_name")
            or element.get("display_name")
            or "attribute"
        )
        value = compact_spaces(" ".join(element.itertext()))
        if value:
            values.append(f"{name}: {value}")
    return values


def limit_text(text: str, max_len: int = 700) -> str:
    text = compact_spaces(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def source_url(db: str, accession: str, uid: str) -> str:
    target = accession or uid
    if db == "biosample":
        return f"https://www.ncbi.nlm.nih.gov/biosample/{target}"
    if db == "assembly":
        return f"https://www.ncbi.nlm.nih.gov/assembly/{target}"
    if db == "sra":
        return f"https://www.ncbi.nlm.nih.gov/sra/{target}"
    return ""


def flatten_biosample(uid: str, summary: dict[str, Any]) -> dict[str, str]:
    sampledata = str(summary.get("sampledata", ""))
    root = parse_xml_fragment(sampledata)
    attributes = xml_attribute_values(root)
    accession = compact_spaces(summary.get("accession", ""))
    title = compact_spaces(summary.get("title", ""))
    organism = compact_spaces(summary.get("organism", ""))
    taxid = compact_spaces(summary.get("taxonomy", ""))
    identifiers = compact_spaces(summary.get("identifiers", ""))
    infraspecies = compact_spaces(summary.get("infraspecies", ""))
    evidence = " | ".join(
        part
        for part in [
            f"title={title}" if title else "",
            f"organism={organism}" if organism else "",
            f"identifiers={identifiers}" if identifiers else "",
            f"infraspecies={infraspecies}" if infraspecies else "",
            f"attributes={'; '.join(attributes)}" if attributes else "",
        ]
        if part
    )
    metadata_text = " ".join([title, organism, identifiers, infraspecies, sampledata])
    return {
        "ncbi_accession": accession,
        "title": title,
        "organism": organism,
        "taxid": taxid,
        "biosample_accession": accession,
        "assembly_level": "",
        "sra_library_strategy": "",
        "data_type": "BioSample",
        "source_url": source_url("biosample", accession, uid),
        "evidence_text": limit_text(evidence),
        "metadata_text": compact_spaces(metadata_text),
    }


def flatten_assembly(uid: str, summary: dict[str, Any]) -> dict[str, str]:
    biosource = summary.get("biosource", {}) or {}
    infraspecies = []
    for item in biosource.get("infraspecieslist", []) or []:
        label = compact_spaces(item.get("sub_type", ""))
        value = compact_spaces(item.get("sub_value", ""))
        if value:
            infraspecies.append(f"{label}: {value}" if label else value)

    accession = compact_spaces(summary.get("assemblyaccession", ""))
    assembly_name = compact_spaces(summary.get("assemblyname", ""))
    organism = compact_spaces(summary.get("organism", ""))
    taxid = compact_spaces(summary.get("taxid", ""))
    biosample = compact_spaces(summary.get("biosampleaccn", ""))
    assembly_level = compact_spaces(summary.get("assemblystatus", ""))
    submitter = compact_spaces(summary.get("submitterorganization", ""))
    meta = compact_spaces(summary.get("meta", ""))
    title = compact_spaces(" ".join(part for part in [accession, assembly_name] if part))
    evidence = " | ".join(
        part
        for part in [
            f"assembly={title}" if title else "",
            f"organism={organism}" if organism else "",
            f"biosample={biosample}" if biosample else "",
            f"assembly_level={assembly_level}" if assembly_level else "",
            f"infraspecies={'; '.join(infraspecies)}" if infraspecies else "",
            f"submitter={submitter}" if submitter else "",
        ]
        if part
    )
    metadata_text = " ".join([title, organism, biosample, " ".join(infraspecies), submitter, meta])
    return {
        "ncbi_accession": accession,
        "title": title,
        "organism": organism,
        "taxid": taxid,
        "biosample_accession": biosample,
        "assembly_level": assembly_level,
        "sra_library_strategy": "",
        "data_type": "Assembly",
        "source_url": source_url("assembly", accession, uid),
        "evidence_text": limit_text(evidence),
        "metadata_text": compact_spaces(metadata_text),
    }


def flatten_sra(uid: str, summary: dict[str, Any]) -> dict[str, str]:
    expxml = str(summary.get("expxml", ""))
    runs = str(summary.get("runs", ""))
    root = parse_xml_fragment(expxml + runs)
    experiment = first_xml_attr(root, ".//Experiment", "acc")
    run = first_xml_attr(root, ".//Run", "acc")
    accession = experiment or run
    title = first_xml_text(root, ".//Title") or first_xml_attr(root, ".//Experiment", "name")
    organism = first_xml_attr(root, ".//Organism", "ScientificName")
    taxid = first_xml_attr(root, ".//Organism", "taxid")
    biosample = first_xml_text(root, ".//Biosample")
    library_strategy = first_xml_text(root, ".//LIBRARY_STRATEGY")
    bioproject = first_xml_text(root, ".//Bioproject")
    evidence = " | ".join(
        part
        for part in [
            f"title={title}" if title else "",
            f"organism={organism}" if organism else "",
            f"biosample={biosample}" if biosample else "",
            f"bioproject={bioproject}" if bioproject else "",
            f"library_strategy={library_strategy}" if library_strategy else "",
            f"experiment={experiment}" if experiment else "",
            f"run={run}" if run else "",
        ]
        if part
    )
    metadata_text = " ".join([title, organism, biosample, bioproject, library_strategy, experiment, run, expxml, runs])
    return {
        "ncbi_accession": accession,
        "title": title,
        "organism": organism,
        "taxid": taxid,
        "biosample_accession": biosample,
        "assembly_level": "",
        "sra_library_strategy": library_strategy,
        "data_type": f"SRA:{library_strategy}" if library_strategy else "SRA",
        "source_url": source_url("sra", accession, uid),
        "evidence_text": limit_text(evidence),
        "metadata_text": compact_spaces(metadata_text),
    }


def flatten_summary(db: str, uid: str, summary: dict[str, Any]) -> dict[str, str]:
    if db == "biosample":
        return flatten_biosample(uid, summary)
    if db == "assembly":
        return flatten_assembly(uid, summary)
    if db == "sra":
        return flatten_sra(uid, summary)
    raise ValueError(f"Unsupported NCBI database: {db}")


def output_columns() -> list[str]:
    return [
        "ncppb_number",
        "ncbi_db",
        "ncbi_uid",
        "ncbi_accession",
        "source_url",
        "data_type",
        "evidence_level",
        "matched_identifier",
        "matched_identifier_type",
        "reject_reason",
        "evidence_text",
        "organism",
        "taxid",
        "title",
        "biosample_accession",
        "assembly_level",
        "sra_library_strategy",
        "linked_from_db",
        "linked_from_accession",
        "status",
        "error",
    ]


def metadata_output_columns() -> list[str]:
    return [
        "ncbi_accession",
        "source_url",
        "data_type",
        "evidence_text",
        "organism",
        "taxid",
        "title",
        "biosample_accession",
        "assembly_level",
        "sra_library_strategy",
    ]


def build_candidate_row(
    context: StrainContext,
    query: QuerySpec,
    uid: str,
    summary: dict[str, Any],
    id_count: int,
) -> dict[str, Any]:
    metadata = flatten_summary(query.db, uid, summary)
    classification = classify_candidate(context, metadata)
    if not query.allow_match and classification.evidence_level == "strong_strain_match":
        classification = Classification(
            "probable_strain_match",
            matched_identifier=classification.matched_identifier,
            matched_identifier_type=classification.matched_identifier_type,
            reject_reason="fallback_requires_manual_review",
        )
    return {
        "ncppb_number": context.ncppb_number,
        "query_tier": query.tier,
        "query_label": query.label,
        "search_term": query.term,
        "ncbi_db": query.db,
        "ncbi_uid": uid,
        "id_count_returned": id_count,
        "status": "ok",
        "error": "",
        **{col: metadata.get(col, "") for col in metadata_output_columns()},
        "evidence_level": classification.evidence_level,
        "matched_identifier": classification.matched_identifier,
        "matched_identifier_type": classification.matched_identifier_type,
        "reject_reason": classification.reject_reason,
    }


def build_error_row(context: StrainContext, query: QuerySpec, error: Exception) -> dict[str, Any]:
    return {
        "ncppb_number": context.ncppb_number,
        "query_tier": query.tier,
        "query_label": query.label,
        "search_term": query.term,
        "ncbi_db": query.db,
        "status": "error",
        "error": str(error),
        "evidence_level": "ambiguous",
        "reject_reason": "query_error",
    }


def is_match_row(row: dict[str, Any]) -> bool:
    return row.get("status") == "ok" and row.get("evidence_level") == "strong_strain_match"


def split_match_review_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matches = [row for row in rows if is_match_row(row)]
    review = [row for row in rows if not is_match_row(row)]
    return matches, review


def linked_sra_rows(
    client: EntrezClient,
    context: StrainContext,
    accepted_rows: list[dict[str, Any]],
    seen_sra: set[tuple[str, str]],
    retmax: int,
    max_ids_per_query: int,
    summary_batch_size: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for parent in accepted_rows:
        biosample_accession = parent.get("biosample_accession", "")
        if not biosample_accession:
            continue
        query = QuerySpec(
            tier="linked_sra_from_accepted_metadata",
            label="biosample_accession",
            db="sra",
            term=f"{biosample_accession}[All Fields]",
        )
        ids = client.esearch_all("sra", query.term, retmax, max_ids_per_query)
        summaries = client.esummary("sra", ids, summary_batch_size)
        for uid in ids:
            key = (context.ncppb_number, uid)
            if key in seen_sra:
                continue
            seen_sra.add(key)
            row = build_candidate_row(context, query, uid, summaries.get(uid, {}), len(ids))
            row["linked_from_db"] = parent.get("ncbi_db", "")
            row["linked_from_accession"] = parent.get("ncbi_accession", "")
            if row.get("evidence_level") != "strong_strain_match" and row.get("reject_reason") != "non_xanthomonas_organism":
                row["evidence_level"] = "strong_strain_match"
                row["matched_identifier"] = parent.get("matched_identifier", "")
                row["matched_identifier_type"] = "linked_accepted_biosample"
                row["reject_reason"] = ""
                row["evidence_text"] = limit_text(
                    f"Linked from accepted {parent.get('ncbi_db')} {parent.get('ncbi_accession')} via BioSample "
                    f"{biosample_accession}. {row.get('evidence_text', '')}"
                )
            rows.append(row)
    return rows


def run_query_batch(
    client: EntrezClient,
    context: StrainContext,
    queries: list[QuerySpec],
    rows: list[dict[str, Any]],
    seen_candidates: set[tuple[str, str]],
    retmax: int,
    max_ids_per_query: int,
    summary_batch_size: int,
) -> None:
    for query in queries:
        try:
            ids = client.esearch_all(query.db, query.term, retmax, max_ids_per_query)
            summaries = client.esummary(query.db, ids, summary_batch_size)
        except Exception as exc:
            rows.append(build_error_row(context, query, exc))
            continue
        for uid in ids:
            key = (query.db, uid)
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            rows.append(build_candidate_row(context, query, uid, summaries.get(uid, {}), len(ids)))


def run_queries_for_strain(
    client: EntrezClient,
    context: StrainContext,
    retmax: int,
    max_ids_per_query: int,
    summary_batch_size: int,
    linked_sra_retmax: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, str]] = set()

    run_query_batch(
        client,
        context,
        build_harvest_queries(context, HARVEST_DBS),
        rows,
        seen_candidates,
        retmax,
        max_ids_per_query,
        summary_batch_size,
    )

    matches, _ = split_match_review_rows(rows)
    seen_sra = {
        (context.ncppb_number, row.get("ncbi_uid", ""))
        for row in rows
        if row.get("ncbi_db") == "sra" and row.get("ncbi_uid")
    }
    rows.extend(
        linked_sra_rows(
            client,
            context,
            matches,
            seen_sra,
            linked_sra_retmax,
            max_ids_per_query,
            summary_batch_size,
        )
    )
    if not any(is_match_row(row) for row in rows):
        rows.append(
            {
                "ncppb_number": context.ncppb_number,
                "query_tier": "summary",
                "query_label": "no_strain_level_match",
                "evidence_level": "no_public_data_found",
                "reject_reason": "no_accepted_strain_level_match",
                "status": "ok",
                "error": "",
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Search terms CSV or TSV, used for strain order")
    parser.add_argument(
        "--master",
        default="data/processed/ncppb_xanthomonas_master.csv",
        help="NCPPB master CSV used to build exact strain identifiers",
    )
    parser.add_argument("--matches-output", required=True, help="Accepted strain-level matches TSV/CSV")
    parser.add_argument("--review-output", required=True, help="Rejected or review candidate TSV/CSV")
    parser.add_argument("--limit-strains", type=int, default=10, help="Number of strains to test")
    parser.add_argument("--retmax", type=int, default=100, help="IDs per NCBI ESearch page")
    parser.add_argument(
        "--max-ids-per-query",
        type=int,
        default=100,
        help="Maximum IDs to retrieve for each keyword/database query",
    )
    parser.add_argument(
        "--summary-batch-size",
        type=int,
        default=200,
        help="Maximum IDs per NCBI ESummary request",
    )
    parser.add_argument("--linked-sra-retmax", type=int, default=10, help="Max SRA IDs per accepted BioSample")
    parser.add_argument("--email", required=True, help="Email required by NCBI E-utilities")
    parser.add_argument("--api-key", default="", help="Optional NCBI API key")
    parser.add_argument("--delay", type=float, default=0.34, help="Delay between NCBI requests")
    parser.add_argument("--timeout", type=float, default=30.0, help="Network timeout per NCBI request")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = EntrezConfig(
        email=args.email,
        tool="ncppb_xanthomonas_audit",
        api_key=args.api_key or os.environ.get("NCBI_API_KEY", ""),
        delay=args.delay,
        timeout=args.timeout,
    )
    client = EntrezClient(config)

    all_terms = read_table(Path(args.input))
    selected = first_unique([row.get("ncppb_number", "") for row in all_terms], args.limit_strains)
    master = read_table(Path(args.master))
    master_rows = {row["ncppb_number"]: row for row in master if row.get("ncppb_number", "") in selected}
    contexts = [make_strain_context(master_rows.get(ncppb, {"ncppb_number": ncppb})) for ncppb in selected]

    rows: list[dict[str, Any]] = []
    for context in contexts:
        rows.extend(
            run_queries_for_strain(
                client,
                context,
                retmax=args.retmax,
                max_ids_per_query=args.max_ids_per_query,
                summary_batch_size=args.summary_batch_size,
                linked_sra_retmax=args.linked_sra_retmax,
            )
        )

    matches, review = split_match_review_rows(rows)
    columns = output_columns()
    write_table(Path(args.matches_output), matches, columns)
    write_table(Path(args.review_output), review, columns)
    print(
        f"Wrote {len(matches)} accepted matches to {args.matches_output}; "
        f"{len(review)} review rows to {args.review_output}; "
        f"{client.request_count} NCBI requests"
    )


if __name__ == "__main__":
    main()
