from __future__ import annotations

import json
import http.client
import os
import re
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .common import clean_text, sha256_text, stable_json, unique_join, write_table


CANDIDATE_COLUMNS = [
    "query_id",
    "ncppb_number",
    "query_track",
    "query_tier",
    "searched_identifier",
    "ncbi_uid",
    "biosample_accession",
    "organism",
    "taxid",
    "title",
    "strain",
    "isolate",
    "culture_collection",
    "bio_material",
    "sample_name",
    "identity_aliases",
    "identifiers",
    "attributes_json",
    "raw_xml_cache_path",
    "source_url",
    "status",
    "error",
]

LINK_COLUMNS = [
    "ncppb_number",
    "biosample_uid",
    "biosample_accession",
    "linked_database",
    "linked_uid",
    "linked_accession",
    "title",
    "assembly_level",
    "extra_json",
    "source_url",
    "status",
    "error",
]

QUERY_EXECUTION_COLUMNS = [
    "query_id",
    "ncppb_number",
    "query_track",
    "query_tier",
    "searched_identifier",
    "reported_count",
    "retrieved_uid_count",
    "truncated",
    "quoted_phrase_not_found_count",
    "status",
    "error",
]


IDENTITY_ATTRIBUTE_NAMES = {
    "strain": "strain",
    "isolate": "isolate",
    "culture_collection": "culture_collection",
    "culture_collection_id": "culture_collection",
    "culture_collection_number": "culture_collection",
    "bio_material": "bio_material",
    "biomaterial_provider": "bio_material",
    "sample_name": "sample_name",
    "isolate_name_alias": "identity_aliases",
    "strain_name_alias": "identity_aliases",
    "other_cc": "identity_aliases",
    "ncppb_number": "identity_aliases",
}


class NcbiClient:
    def __init__(
        self,
        email: str,
        cache_dir: Path,
        api_key: str = "",
        delay: float = 0.34,
        timeout: float = 40.0,
        offline_cache_only: bool = False,
    ) -> None:
        if not email:
            raise ValueError("NCBI contact email is required for live or cached NCBI stages")
        self.email = email
        self.api_key = api_key or os.environ.get("NCBI_API_KEY", "")
        self.cache_dir = cache_dir
        self.delay = min(delay, 0.11) if self.api_key else max(delay, 0.34)
        self.max_workers = 8 if self.api_key else 3
        self.timeout = timeout
        self.offline_cache_only = offline_cache_only
        self.request_count = 0
        self.cache_hits = 0
        self.next_request_at = 0.0
        self._rate_lock = threading.Lock()
        self._counter_lock = threading.Lock()

    def cache_path(self, endpoint: str, params: dict[str, str]) -> Path:
        semantic = {key: value for key, value in params.items() if key not in {"email", "api_key", "tool"}}
        digest = sha256_text(stable_json({"endpoint": endpoint, "params": semantic}))
        return self.cache_dir / f"{endpoint}_{digest}.xml"

    def request(self, endpoint: str, params: dict[str, str]) -> tuple[str, Path]:
        request_params = dict(params)
        request_params.update({"email": self.email, "tool": "ncppb_audit_v2"})
        if self.api_key:
            request_params["api_key"] = self.api_key
        cache_path = self.cache_path(endpoint, request_params)
        if cache_path.exists():
            cached = cache_path.read_text(encoding="utf-8")
            if request_params.get("retmode") == "json":
                try:
                    json.loads(cached)
                except json.JSONDecodeError:
                    cached = ""
            if cached:
                with self._counter_lock:
                    self.cache_hits += 1
                return cached, cache_path
        if self.offline_cache_only:
            raise RuntimeError(f"NCBI cache miss: {endpoint} {params}")
        url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{endpoint}.fcgi?"
            + urllib.parse.urlencode(request_params)
        )
        request = urllib.request.Request(url, headers={"User-Agent": "ncppb-audit-v2/2.0"})
        text = ""
        for attempt in range(5):
            with self._rate_lock:
                now = time.monotonic()
                wait = max(0.0, self.next_request_at - now)
                if wait:
                    time.sleep(wait)
                self.next_request_at = time.monotonic() + self.delay
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    text = response.read().decode("utf-8", errors="replace")
                if request_params.get("retmode") == "json":
                    json.loads(text)
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429 and exc.code < 500:
                    raise
                if attempt == 4:
                    raise
                time.sleep(min(8.0, 0.75 * (2**attempt)))
            except (urllib.error.URLError, http.client.IncompleteRead, json.JSONDecodeError):
                if attempt == 4:
                    raise
                time.sleep(min(8.0, 0.75 * (2**attempt)))
        with self._counter_lock:
            self.request_count += 1
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
        return text, cache_path


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def parse_esearch_ids(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [clean_text(node.text) for node in root.findall(".//IdList/Id") if clean_text(node.text)]


def parse_esearch_details(xml_text: str) -> tuple[int, list[str], int]:
    root = ET.fromstring(xml_text)
    count = int(root.findtext("Count", "0") or 0)
    ids = [clean_text(node.text) for node in root.findall(".//IdList/Id") if clean_text(node.text)]
    warnings = len(root.findall(".//QuotedPhraseNotFound"))
    return count, ids, warnings


def child_text(node: ET.Element, path: str) -> str:
    child = node.find(path)
    return clean_text(child.text if child is not None else "")


def parse_biosamples(xml_text: str, cache_path: Path) -> dict[str, dict[str, str]]:
    root = ET.fromstring(xml_text)
    records: dict[str, dict[str, str]] = {}
    for sample in root.findall(".//BioSample"):
        uid = clean_text(sample.attrib.get("id", ""))
        accession = clean_text(sample.attrib.get("accession", ""))
        organism_node = sample.find("./Description/Organism")
        organism = clean_text(organism_node.attrib.get("taxonomy_name", "") if organism_node is not None else "")
        taxid = clean_text(organism_node.attrib.get("taxonomy_id", "") if organism_node is not None else "")
        title = child_text(sample, "./Description/Title")
        attribute_values: dict[str, list[str]] = {}
        all_attributes: dict[str, list[str]] = {}
        for attribute in sample.findall("./Attributes/Attribute"):
            name = clean_text(attribute.attrib.get("attribute_name", attribute.attrib.get("harmonized_name", "")))
            value = clean_text(attribute.text)
            if not name or not value:
                continue
            all_attributes.setdefault(name, []).append(value)
            normalized_name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            mapped = IDENTITY_ATTRIBUTE_NAMES.get(normalized_name)
            if mapped:
                attribute_values.setdefault(mapped, []).append(value)
        ids: list[str] = []
        for identifier in sample.findall("./Ids/Id"):
            value = clean_text(identifier.text)
            db = clean_text(identifier.attrib.get("db", ""))
            label = f"{db}: {value}" if db and value else value
            if label:
                ids.append(label)
        records[uid or accession] = {
            "ncbi_uid": uid,
            "biosample_accession": accession,
            "organism": organism,
            "taxid": taxid,
            "title": title,
            "strain": unique_join(attribute_values.get("strain", [])),
            "isolate": unique_join(attribute_values.get("isolate", [])),
            "culture_collection": unique_join(attribute_values.get("culture_collection", [])),
            "bio_material": unique_join(attribute_values.get("bio_material", [])),
            "sample_name": unique_join(attribute_values.get("sample_name", [])),
            "identity_aliases": unique_join(attribute_values.get("identity_aliases", [])),
            "identifiers": unique_join(ids),
            "attributes_json": stable_json(all_attributes),
            "raw_xml_cache_path": str(cache_path),
            "source_url": f"https://www.ncbi.nlm.nih.gov/biosample/{accession or uid}",
            "status": "ok",
            "error": "",
        }
    return records


def harvest_biosample_candidates(
    query_plan: list[dict[str, str]], client: NcbiClient, retmax: int = 100
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    query_uids: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    execution_rows: list[dict[str, str]] = []

    def execute_search(query: dict[str, str]) -> tuple[str, list[str], dict[str, str]]:
        try:
            page_size = int(query.get("page_size", "") or retmax)
            max_records = int(query.get("max_records", "") or page_size)
            base_params = {
                    "db": "biosample",
                    "term": query["query_term"],
                    "retmode": "xml",
            }
            first_params = {**base_params, "retstart": "0", "retmax": str(min(page_size, max_records))}
            xml_text, _ = client.request("esearch", first_params)
            reported_count, ids, warning_count = parse_esearch_details(xml_text)
            target = min(reported_count, max_records)
            offset = len(ids)
            while offset < target:
                request_size = min(page_size, target - offset)
                page_text, _ = client.request(
                    "esearch", {**base_params, "retstart": str(offset), "retmax": str(request_size)}
                )
                _, page_ids, page_warnings = parse_esearch_details(page_text)
                warning_count += page_warnings
                if not page_ids:
                    break
                ids.extend(page_ids)
                offset += len(page_ids)
            ids = list(dict.fromkeys(ids))
            truncated = reported_count > len(ids)
            audit = {
                "query_id": query["query_id"],
                "ncppb_number": query["ncppb_number"],
                "query_track": query["query_track"],
                "query_tier": query["query_tier"],
                "searched_identifier": query["identifier_raw"],
                "reported_count": str(reported_count),
                "retrieved_uid_count": str(len(ids)),
                "truncated": "yes" if truncated else "no",
                "quoted_phrase_not_found_count": str(warning_count),
                "status": "truncated" if truncated else "ok",
                "error": "",
            }
            return query["query_id"], ids, audit
        except Exception as exc:  # network and malformed remote XML become explicit rows
            error = f"{type(exc).__name__}: {exc}"
            audit = {
                "query_id": query["query_id"],
                "ncppb_number": query["ncppb_number"],
                "query_track": query["query_track"],
                "query_tier": query["query_tier"],
                "searched_identifier": query["identifier_raw"],
                "status": "error",
                "error": error,
            }
            return query["query_id"], [], audit

    with ThreadPoolExecutor(max_workers=client.max_workers) as executor:
        futures = [executor.submit(execute_search, query) for query in query_plan]
        for completed, future in enumerate(as_completed(futures), start=1):
            query_id, uids, audit = future.result()
            query_uids[query_id] = uids
            execution_rows.append(audit)
            if audit.get("error"):
                errors[query_id] = audit["error"]
            if completed % 100 == 0 or completed == len(futures):
                print(f"[NCBI esearch] {completed}/{len(futures)} queries", flush=True)

    all_uids = sorted({uid for values in query_uids.values() for uid in values}, key=lambda value: int(value))
    records: dict[str, dict[str, str]] = {}
    def execute_fetch(uid_chunk: list[str]) -> tuple[list[str], dict[str, dict[str, str]], str]:
        try:
            xml_text, cache_path = client.request(
                "efetch",
                {"db": "biosample", "id": ",".join(uid_chunk), "retmode": "xml"},
            )
            return uid_chunk, parse_biosamples(xml_text, cache_path), ""
        except Exception as exc:
            return uid_chunk, {}, f"{type(exc).__name__}: {exc}"

    fetch_chunks = list(chunks(all_uids, 100))
    with ThreadPoolExecutor(max_workers=client.max_workers) as executor:
        futures = [executor.submit(execute_fetch, uid_chunk) for uid_chunk in fetch_chunks]
        for completed, future in enumerate(as_completed(futures), start=1):
            uid_chunk, fetched, error = future.result()
            records.update(fetched)
            if error:
                for uid in uid_chunk:
                    records[uid] = {"ncbi_uid": uid, "status": "error", "error": error}
            if completed % 25 == 0 or completed == len(futures):
                print(f"[NCBI efetch] {completed}/{len(futures)} BioSample batches", flush=True)

    rows: list[dict[str, str]] = []
    for query in query_plan:
        query_id = query["query_id"]
        uids = query_uids.get(query_id, [])
        if not uids:
            rows.append(
                {
                    "query_id": query_id,
                    "ncppb_number": query["ncppb_number"],
                    "query_track": query["query_track"],
                    "query_tier": query["query_tier"],
                    "searched_identifier": query["identifier_raw"],
                    "status": "error" if query_id in errors else "no_hit",
                    "error": errors.get(query_id, ""),
                }
            )
            continue
        for uid in uids:
            record = records.get(uid, {"ncbi_uid": uid, "status": "error", "error": "missing_efetch_record"})
            rows.append(
                {
                    "query_id": query_id,
                    "ncppb_number": query["ncppb_number"],
                    "query_track": query["query_track"],
                    "query_tier": query["query_tier"],
                    "searched_identifier": query["identifier_raw"],
                    **record,
                }
            )
    deduplicated: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("ncppb_number", ""), row.get("query_track", ""), row.get("ncbi_uid", "") or row["query_id"])
        existing = deduplicated.get(key)
        if existing is None or (existing.get("query_tier") == "unfiltered_fallback" and row.get("query_tier") == "expected_genus"):
            deduplicated[key] = row
    return list(deduplicated.values()), sorted(execution_rows, key=lambda row: row["query_id"])


def map_shared_ncppb_candidates(
    candidates: list[dict[str, str]], strains: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Map prefix-harvest candidates to strains using complete bounded NCPPB identifiers."""
    valid_numbers = {row.get("ncppb_number", "") for row in strains}
    mapped: list[dict[str, str]] = []
    unmapped: list[dict[str, str]] = []
    for candidate in candidates:
        if candidate.get("ncppb_number") != "ALL_NCPPB":
            mapped.append(candidate)
            continue
        if candidate.get("status") != "ok":
            if candidate.get("status") == "error":
                unmapped.append(candidate)
            continue
        combined = " ".join(candidate.get(field, "") for field in [
            "strain", "isolate", "culture_collection", "bio_material", "sample_name", "identity_aliases", "identifiers", "title"
        ])
        found = sorted(
            {f"NCPPB {digits}" for digits in re.findall(r"(?<![A-Za-z0-9])NCPPB\s*[-:_]?\s*(\d+)(?![A-Za-z0-9])", combined, flags=re.IGNORECASE)},
            key=lambda value: int(re.search(r"\d+", value).group(0)),
        )
        targets = [number for number in found if number in valid_numbers]
        if not targets:
            unmapped.append(candidate)
            continue
        for number in targets:
            mapped.append({**candidate, "ncppb_number": number})
    deduplicated: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in mapped:
        key = (row.get("ncppb_number", ""), row.get("query_track", ""), row.get("ncbi_uid", "") or row.get("query_id", ""))
        existing = deduplicated.get(key)
        if existing is None:
            deduplicated[key] = row
        else:
            existing["query_id"] = unique_join([existing.get("query_id", ""), row.get("query_id", "")])
            existing["query_tier"] = unique_join([existing.get("query_tier", ""), row.get("query_tier", "")])
            existing["searched_identifier"] = unique_join(
                [existing.get("searched_identifier", ""), row.get("searched_identifier", "")]
            )
    return list(deduplicated.values()), unmapped


def map_shared_other_prefix_candidates(
    candidates: list[dict[str, str]], identifiers: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Map collection-prefix harvests to strains by exact complete identifiers."""
    from .identifiers import collection_prefix

    by_prefix: dict[str, list[dict[str, str]]] = {}
    for identifier in identifiers:
        if identifier.get("identifier_type") != "collection_number" or identifier.get("search_eligible") != "yes":
            continue
        prefix = collection_prefix(identifier.get("identifier_raw", ""))
        if prefix:
            by_prefix.setdefault(prefix, []).append(identifier)

    def pattern(value: str) -> re.Pattern[str] | None:
        parts = re.findall(r"[A-Za-z]+|\d+", value or "")
        if not parts:
            return None
        body = r"[\s:._/\-]*".join(re.escape(part) for part in parts)
        return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)

    mapped: list[dict[str, str]] = []
    unmapped: list[dict[str, str]] = []
    fields = [
        "strain", "isolate", "culture_collection", "bio_material", "sample_name",
        "identity_aliases", "identifiers", "title",
    ]
    for candidate in candidates:
        marker = candidate.get("ncppb_number", "")
        if not marker.startswith("ALL_OTHER_PREFIX:"):
            mapped.append(candidate)
            continue
        if candidate.get("status") != "ok":
            if candidate.get("status") == "error":
                unmapped.append(candidate)
            continue
        prefix = marker.split(":", 1)[1]
        combined = " ".join(candidate.get(field, "") for field in fields)
        targets: list[str] = []
        for identifier in by_prefix.get(prefix, []):
            compiled = pattern(identifier.get("identifier_raw", ""))
            if compiled and compiled.search(combined):
                targets.append(identifier["ncppb_number"])
        if not targets:
            unmapped.append(candidate)
            continue
        for number in sorted(set(targets)):
            mapped.append({**candidate, "ncppb_number": number})

    deduplicated: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in mapped:
        key = (
            row.get("ncppb_number", ""),
            row.get("query_track", ""),
            row.get("ncbi_uid", "") or row.get("query_id", ""),
        )
        existing = deduplicated.get(key)
        if existing is None:
            deduplicated[key] = row
        else:
            existing["query_id"] = unique_join([existing.get("query_id", ""), row.get("query_id", "")])
            existing["query_tier"] = unique_join([existing.get("query_tier", ""), row.get("query_tier", "")])
            existing["searched_identifier"] = unique_join(
                [existing.get("searched_identifier", ""), row.get("searched_identifier", "")]
            )
    return list(deduplicated.values()), unmapped


def recheck_v1_biosample_accessions(
    v1_rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
    client: NcbiClient,
) -> list[dict[str, str]]:
    """Directly re-read V1 BioSamples not rediscovered by either V2 search track."""
    existing = {
        (row.get("ncppb_number", ""), row.get("biosample_accession", "").upper())
        for row in candidates
        if row.get("biosample_accession", "")
    }
    requested: dict[str, set[str]] = {}
    for row in v1_rows:
        number = row.get("ncppb_number", "")
        accessions = [clean_text(value).upper() for value in re.split(r"\s*;\s*", row.get("biosample_accessions", "")) if clean_text(value)]
        for accession in accessions:
            if (number, accession) not in existing:
                requested.setdefault(accession, set()).add(number)
    if not requested:
        return []

    resolved_uids: set[str] = set()
    errors: dict[str, str] = {}
    accessions = sorted(requested)
    for accession_chunk in chunks(accessions, 50):
        term = " OR ".join(f"{accession}[Accession]" for accession in accession_chunk)
        try:
            xml_text, _ = client.request(
                "esearch",
                {"db": "biosample", "term": term, "retmode": "xml", "retmax": str(len(accession_chunk) * 3)},
            )
            resolved_uids.update(parse_esearch_ids(xml_text))
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            for accession in accession_chunk:
                errors[accession] = message

    records: dict[str, dict[str, str]] = {}
    uid_values = sorted(resolved_uids, key=int)
    for uid_chunk in chunks(uid_values, 100):
        try:
            xml_text, cache_path = client.request(
                "efetch", {"db": "biosample", "id": ",".join(uid_chunk), "retmode": "xml"}
            )
            records.update(parse_biosamples(xml_text, cache_path))
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            for accession in requested:
                errors.setdefault(accession, message)
    by_accession = {
        row.get("biosample_accession", "").upper(): row
        for row in records.values()
        if row.get("biosample_accession", "")
    }
    output: list[dict[str, str]] = []
    for accession, numbers in requested.items():
        record = by_accession.get(accession)
        for number in sorted(numbers):
            base = {
                "query_id": sha256_text(stable_json({"track": "historical_v1_recheck", "number": number, "accession": accession}))[:20],
                "ncppb_number": number,
                "query_track": "historical_v1_recheck",
                "query_tier": "direct_accession_recheck",
                "searched_identifier": accession,
            }
            if record:
                output.append({**base, **record})
            else:
                output.append(
                    {
                        **base,
                        "biosample_accession": accession,
                        "status": "error" if accession in errors else "no_hit",
                        "error": errors.get(accession, "accession_not_resolved"),
                    }
                )
    print(f"[V1 regression recheck] {len(requested)} accessions not rediscovered; {len(by_accession)} resolved", flush=True)
    return output


def parse_elink_ids(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [clean_text(node.text) for node in root.findall(".//LinkSetDb/Link/Id") if clean_text(node.text)]


def parse_docsum_items(docsum: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in docsum.findall("./Item"):
        name = clean_text(item.attrib.get("Name", ""))
        if name:
            values[name] = clean_text("".join(item.itertext()))
    return values


def linked_summary(database: str, uid: str, values: dict[str, str]) -> tuple[str, str, str]:
    if database == "assembly":
        return (
            clean_text(values.get("assemblyaccession", values.get("AssemblyAccession", ""))),
            clean_text(values.get("assemblyname", values.get("AssemblyName", values.get("organism", "")))),
            clean_text(values.get("assemblystatus", values.get("AssemblyStatus", ""))),
        )
    if database == "bioproject":
        return (
            clean_text(values.get("project_acc", values.get("Project_Acc", ""))),
            clean_text(values.get("project_title", values.get("Project_Title", ""))),
            "",
        )
    if database == "sra":
        runs_text = str(values.get("runs", values.get("Runs", "")))
        runs = re.findall(r"<Run\b[^>]*\bacc=[\"']([SED]RR\d+)[\"']", runs_text, flags=re.IGNORECASE)
        accession = "; ".join(runs) if runs else clean_text(values.get("accession", values.get("Accession", "")))
        return accession, clean_text(values.get("title", values.get("expxml", ""))), ""
    return uid, values.get("Title", ""), ""


def expand_linked_records(
    accepted_candidates: list[dict[str, str]], client: NcbiClient
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_samples: set[tuple[str, str]] = set()
    tasks: list[tuple[dict[str, str], str]] = []
    for candidate in accepted_candidates:
        sample_key = (candidate.get("ncppb_number", ""), candidate.get("ncbi_uid", ""))
        if not sample_key[1] or sample_key in seen_samples:
            continue
        seen_samples.add(sample_key)
        for database in ["assembly", "sra", "bioproject"]:
            tasks.append((candidate, database))

    def expand_one(candidate: dict[str, str], database: str) -> list[dict[str, str]]:
        sample_key = (candidate.get("ncppb_number", ""), candidate.get("ncbi_uid", ""))
        task_rows: list[dict[str, str]] = []
        try:
            xml_text, _ = client.request(
                "elink",
                {"dbfrom": "biosample", "db": database, "id": sample_key[1], "retmode": "json"},
            )
            link_record = json.loads(xml_text)
            linked_ids = []
            for linkset in link_record.get("linksets", []):
                for linksetdb in linkset.get("linksetdbs", []):
                    linked_ids.extend(str(value) for value in linksetdb.get("links", []))
            linked_ids = sorted(set(linked_ids), key=lambda value: int(value))
            if not linked_ids:
                return []
            summary_text, _ = client.request(
                "esummary",
                {"db": database, "id": ",".join(linked_ids), "retmode": "json"},
            )
            summary_record = json.loads(summary_text)
            result = summary_record.get("result", {})
            values_by_uid = {str(uid): result.get(str(uid), {}) for uid in result.get("uids", [])}
            for linked_uid in linked_ids:
                values = values_by_uid.get(linked_uid, {})
                accession, title, level = linked_summary(database, linked_uid, values)
                source_token = accession.split(";", 1)[0].strip() or linked_uid
                task_rows.append(
                    {
                        "ncppb_number": sample_key[0],
                        "biosample_uid": sample_key[1],
                        "biosample_accession": candidate.get("biosample_accession", ""),
                        "linked_database": database,
                        "linked_uid": linked_uid,
                        "linked_accession": accession,
                        "title": title,
                        "assembly_level": level,
                        "extra_json": stable_json(values),
                        "source_url": f"https://www.ncbi.nlm.nih.gov/{database}/{source_token}",
                        "status": "ok",
                        "error": "",
                    }
                )
        except Exception as exc:
            task_rows.append(
                {
                    "ncppb_number": sample_key[0],
                    "biosample_uid": sample_key[1],
                    "biosample_accession": candidate.get("biosample_accession", ""),
                    "linked_database": database,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        return task_rows

    with ThreadPoolExecutor(max_workers=client.max_workers) as executor:
        futures = [executor.submit(expand_one, candidate, database) for candidate, database in tasks]
        for completed, future in enumerate(as_completed(futures), start=1):
            rows.extend(future.result())
            if completed % 100 == 0 or completed == len(futures):
                print(f"[NCBI elink/esummary] {completed}/{len(futures)} link tasks", flush=True)
    return rows


def write_ncbi_outputs(outdir: Path, candidates, links, query_execution=None) -> None:
    write_table(outdir / "biosample_candidates.tsv", candidates, CANDIDATE_COLUMNS)
    write_table(outdir / "linked_ncbi_records.tsv", links, LINK_COLUMNS)
    if query_execution is not None:
        write_table(outdir / "ncbi_query_execution.tsv", query_execution, QUERY_EXECUTION_COLUMNS)
