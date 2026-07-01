from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from .common import clean_text, normalized_ncppb, sha256_file, write_table


BASE_URL = "https://ncppb.fera.co.uk/"

STRAIN_COLUMNS = [
    "ncppb_number",
    "current_name_raw",
    "canonical_name",
    "name_as_received",
    "alternative_names",
    "expected_genus",
    "expected_taxid",
    "host",
    "country",
    "other_references_raw",
    "catalogue_url",
    "source_snapshot_sha256",
    "record_html_start",
    "record_html_end",
]

CLAUSE_COLUMNS = [
    "ncppb_number",
    "clause_order",
    "clause_type",
    "raw_clause",
    "raw_value",
    "text_start",
    "text_end",
    "html_start",
    "html_end",
    "parse_status",
    "risk_level",
    "review_reason",
    "source_snapshot_sha256",
]

DIFF_COLUMNS = [
    "ncppb_number",
    "snapshot_status",
    "v1_current_name",
    "v2_current_name",
    "v1_other_references",
    "v2_other_references",
    "name_changed",
    "other_references_changed",
]


@dataclass(frozen=True)
class HtmlValue:
    raw_html: str
    text: str
    html_start: int
    html_end: int


RECORD_LINK_RE = re.compile(
    r"<a\b[^>]*href\s*=\s*[\"']?([^\"'>]*furtherinfo\.cfm\?ncppb_no=(\d+)[^\"'>]*)[\"']?[^>]*>.*?</a>",
    flags=re.IGNORECASE | re.DOTALL,
)


def html_to_text(fragment: str, preserve_breaks: bool = False) -> str:
    text = fragment
    replacement = "\n" if preserve_breaks else " "
    text = re.sub(r"<\s*br\s*/?\s*>", replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text).replace("\r", "")
    if preserve_breaks:
        return "\n".join(clean_text(line) for line in text.split("\n") if clean_text(line))
    return clean_text(text)


def find_labeled_value(block: str, label: str, absolute_start: int) -> HtmlValue:
    pattern = re.compile(
        rf"<strong>\s*{re.escape(label)}\s*:?\s*</strong>\s*</td>\s*<td\b[^>]*>(.*?)</td>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(block)
    if not match:
        return HtmlValue("", "", -1, -1)
    raw_html = match.group(1)
    preserve_breaks = label.lower().rstrip(":") == "other references"
    return HtmlValue(
        raw_html=raw_html,
        text=html_to_text(raw_html, preserve_breaks=preserve_breaks),
        html_start=absolute_start + match.start(1),
        html_end=absolute_start + match.end(1),
    )


def canonical_name(current_name: str) -> str:
    match = re.search(r"\b([A-Z][A-Za-z-]+)\s+([a-z][A-Za-z0-9_-]+)", current_name)
    return f"{match.group(1)} {match.group(2)}" if match else clean_text(current_name)


def expected_genus(current_name: str) -> str:
    match = re.search(r"\b([A-Z][A-Za-z-]+)\b", current_name)
    return match.group(1) if match else ""


CLAUSE_RULES = [
    (
        "donor_reference",
        re.compile(r"^The\s+donor\s+reference\s+(?:is|was)\s+(.+)$", re.IGNORECASE),
        "medium",
    ),
    (
        "collection_list",
        re.compile(r"^This\s+isolate\s+is\s+also\s+in\s+(?:the\s+)?collections?\s*[;:]\s*(.+)$", re.IGNORECASE),
        "low",
    ),
    (
        "isolated_by",
        re.compile(r"^This\s+isolate\s+was\s+isolated\s+by\s+(.+)$", re.IGNORECASE),
        "medium",
    ),
    (
        "source_of_isolate",
        re.compile(r"^The\s+source\s+of\s+this\s+isolate\s+was\s+(.+)$", re.IGNORECASE),
        "medium",
    ),
]


def classify_clause(raw_clause: str) -> tuple[str, str, str, str, str]:
    clause = clean_text(raw_clause)
    for clause_type, pattern, risk_level in CLAUSE_RULES:
        match = pattern.fullmatch(clause)
        if match:
            value = clean_text(match.group(1))
            review_reason = ""
            if clause_type in {"isolated_by", "source_of_isolate"}:
                review_reason = "person_or_source_text_not_automatically_an_identifier"
            elif clause_type == "donor_reference" and not re.search(r"\d", value):
                risk_level = "high"
                review_reason = "digit_free_donor_reference_requires_review_before_search"
            return clause_type, value, "parsed", risk_level, review_reason
    return "unknown", "", "review_required", "high", "unknown_other_reference_clause"


def parse_catalogue_html(
    path: Path, record_source_hash: bool = False
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    source_hash = sha256_file(path) if record_source_hash else ""
    html = path.read_text(encoding="utf-8", errors="replace")
    links = list(RECORD_LINK_RE.finditer(html))
    strains: list[dict[str, str]] = []
    clauses: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, link in enumerate(links):
        number = normalized_ncppb(link.group(2))
        if number in seen:
            continue
        seen.add(number)
        record_start = link.start()
        record_end = links[index + 1].start() if index + 1 < len(links) else len(html)
        block = html[record_start:record_end]

        current = find_labeled_value(block, "Catalogue name", record_start)
        received = find_labeled_value(block, "Name as received", record_start)
        alternative = find_labeled_value(block, "Other name", record_start)
        host = find_labeled_value(block, "Host", record_start)
        country = find_labeled_value(block, "Country", record_start)
        other = find_labeled_value(block, "Other references", record_start)

        strains.append(
            {
                "ncppb_number": number,
                "current_name_raw": current.text,
                "canonical_name": canonical_name(current.text),
                "name_as_received": received.text,
                "alternative_names": alternative.text,
                "expected_genus": expected_genus(current.text),
                "expected_taxid": "",
                "host": host.text,
                "country": country.text,
                "other_references_raw": other.text,
                "catalogue_url": urljoin(BASE_URL, link.group(1)),
                "source_snapshot_sha256": source_hash,
                "record_html_start": str(record_start),
                "record_html_end": str(record_end),
            }
        )

        if not other.text:
            continue
        search_from = 0
        raw_lines = other.text.split("\n")
        raw_html_parts = re.split(r"<\s*br\s*/?\s*>", other.raw_html, flags=re.IGNORECASE)
        html_cursor = other.html_start
        for order, raw_clause in enumerate(raw_lines, start=1):
            clause = clean_text(raw_clause)
            text_start = other.text.find(clause, search_from)
            text_end = text_start + len(clause)
            search_from = text_end
            clause_type, raw_value, status, risk, reason = classify_clause(clause)
            raw_html_part = raw_html_parts[order - 1] if order - 1 < len(raw_html_parts) else ""
            relative_match = re.search(re.escape(raw_html_part), other.raw_html)
            if relative_match:
                html_start = other.html_start + relative_match.start()
                html_end = other.html_start + relative_match.end()
            else:
                html_start = html_cursor
                html_end = html_cursor + len(raw_html_part)
            html_cursor = html_end
            clauses.append(
                {
                    "ncppb_number": number,
                    "clause_order": str(order),
                    "clause_type": clause_type,
                    "raw_clause": clause,
                    "raw_value": raw_value,
                    "text_start": str(text_start),
                    "text_end": str(text_end),
                    "html_start": str(html_start),
                    "html_end": str(html_end),
                    "parse_status": status,
                    "risk_level": risk,
                    "review_reason": reason,
                    "source_snapshot_sha256": source_hash,
                }
            )
    return strains, clauses


def compare_to_v1(
    v1_rows: list[dict[str, str]], v2_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    old = {row.get("ncppb_number", ""): row for row in v1_rows}
    new = {row.get("ncppb_number", ""): row for row in v2_rows}
    rows: list[dict[str, str]] = []
    for number in sorted(set(old) | set(new), key=lambda value: int(re.search(r"\d+", value).group(0))):
        v1 = old.get(number, {})
        v2 = new.get(number, {})
        status = "current_snapshot_no_v1_baseline" if not old else "present_in_both"
        if old and number not in new:
            status = "missing_from_v2_snapshot"
        elif old and number not in old:
            status = "added_in_v2_snapshot"
        v1_name = clean_text(v1.get("current_name", v1.get("current_name_raw", "")))
        v2_name = clean_text(v2.get("current_name_raw", v2.get("current_name", "")))
        v1_refs = clean_text(v1.get("other_references", v1.get("other_references_raw", "")))
        v2_refs = clean_text(v2.get("other_references_raw", v2.get("other_references", "")))
        rows.append(
            {
                "ncppb_number": number,
                "snapshot_status": status,
                "v1_current_name": v1_name,
                "v2_current_name": v2_name,
                "v1_other_references": v1_refs,
                "v2_other_references": v2_refs,
                "name_changed": "yes" if number in old and number in new and v1_name != v2_name else "no",
                "other_references_changed": "yes" if number in old and number in new and v1_refs != v2_refs else "no",
            }
        )
    return rows


def write_catalogue_outputs(
    html_path: Path,
    v1_master_path: Path | None,
    outdir: Path,
    read_table,
    record_source_hash: bool = False,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    strains, clauses = parse_catalogue_html(html_path, record_source_hash=record_source_hash)
    v1_rows = read_table(v1_master_path) if v1_master_path and v1_master_path.exists() else []
    differences = compare_to_v1(v1_rows, strains)
    write_table(outdir / "catalogue_strains.tsv", strains, STRAIN_COLUMNS)
    write_table(outdir / "other_reference_clauses.tsv", clauses, CLAUSE_COLUMNS)
    write_table(outdir / "catalogue_snapshot_diff.tsv", differences, DIFF_COLUMNS)
    return strains, clauses, differences
