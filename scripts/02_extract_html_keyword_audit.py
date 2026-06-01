#!/usr/bin/env python3
"""Extract all visible NCPPB HTML record keywords into a long TSV.

This script is a Week 1 quality-control helper. It reads the saved NCPPB result
HTML directly and records every visible labelled value for each strain, without
mapping labels into the cleaned master-table schema.
"""

from __future__ import annotations

import argparse
import csv
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


BASE_URL = "https://ncppb.fera.co.uk/"
COLLECTION_ID_RE = re.compile(
    r"\b(ATCC|BCCM|CCUG|CFBP|CIP|DSMZ?|ICMP|JCM|LMG|NCTC|NIB|NRRL|PDDCC|PD|RIV|UQM|VKM|WDCM)\s*[-:]?\s*[A-Z]*\d+[A-Z0-9.-]*\b",
    flags=re.I,
)


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def normalise_label(value: object) -> str:
    label = clean_text(value).rstrip(":").lower()
    label = re.sub(r"[^a-z0-9]+", "_", label)
    return label.strip("_") or "unlabelled"


def normalise_ncppb(value: str) -> str:
    match = re.search(r"(\d+)", value or "")
    return f"NCPPB {match.group(1)}" if match else clean_text(value)


def strip_tags(fragment: str) -> str:
    return clean_text(unescape(re.sub(r"<[^>]+>", " ", fragment)))


def reconstruct_if_view_source(html: str) -> str:
    line_cells = re.findall(r'<td[^>]*class="line-content"[^>]*>(.*?)</td>', html, flags=re.I | re.S)
    if not line_cells:
        return html
    return "\n".join(strip_tags(cell) for cell in line_cells)


class Cell:
    def __init__(self) -> None:
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.active_href = ""
        self.active_link_text: list[str] = []

    def add_text(self, text: str) -> None:
        self.text_parts.append(text)
        if self.active_href:
            self.active_link_text.append(text)

    def start_link(self, href: str) -> None:
        self.active_href = href
        self.active_link_text = []

    def end_link(self) -> None:
        if self.active_href:
            self.links.append((clean_text(" ".join(self.active_link_text)), self.active_href))
        self.active_href = ""
        self.active_link_text = []

    def value(self) -> str:
        links = []
        for text, href in self.links:
            url = urljoin(BASE_URL, href)
            links.append(f"{text} <{url}>" if text else url)
        return "; ".join(links) if links else clean_text(" ".join(self.text_parts))


class NcppbKeywordParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.row_stack: list[list[Cell]] = []
        self.cell_stack: list[Cell] = []
        self.rows: list[list[Cell]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "tr":
            self.row_stack.append([])
        elif tag.lower() == "td":
            self.cell_stack.append(Cell())
        elif tag.lower() == "a" and self.cell_stack:
            self.cell_stack[-1].start_link(attrs_dict.get("href", ""))
        elif tag.lower() == "br" and self.cell_stack:
            self.cell_stack[-1].add_text(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self.cell_stack:
            self.cell_stack[-1].end_link()
        elif tag == "td" and self.cell_stack:
            cell = self.cell_stack.pop()
            if self.row_stack:
                self.row_stack[-1].append(cell)
        elif tag == "tr" and self.row_stack:
            row = self.row_stack.pop()
            if row:
                self.rows.append(row)

    def handle_data(self, data: str) -> None:
        if self.cell_stack:
            self.cell_stack[-1].add_text(data)


def add_row(
    rows: list[dict[str, str]],
    ncppb_number: str,
    catalogue_url: str,
    source_type: str,
    source_label: str,
    keyword: str,
) -> None:
    keyword = clean_text(keyword)
    if not keyword:
        return
    rows.append(
        {
            "ncppb_number": ncppb_number,
            "source_type": source_type,
            "source_label": source_label,
            "keyword": keyword,
            "ncppb_catalogue_url": catalogue_url,
        }
    )


def collection_identifiers(text: str) -> list[str]:
    found: list[str] = []
    for match in COLLECTION_ID_RE.finditer(text or ""):
        value = clean_text(match.group(0)).upper()
        value = re.sub(r"\s+", " ", value)
        if value not in found:
            found.append(value)
    return found


def parse_html_keyword_rows(html: str) -> list[dict[str, str]]:
    parser = NcppbKeywordParser()
    parser.feed(reconstruct_if_view_source(html))
    rows: list[dict[str, str]] = []
    seen_rows: set[tuple[str, str, str, str]] = set()
    current_ncppb = ""
    current_url = ""
    current_text_parts: list[str] = []

    def flush_current_record() -> None:
        if not current_ncppb:
            return
        raw_record_text = clean_text(" ".join(current_text_parts))
        candidate_rows: list[dict[str, str]] = []
        for identifier in collection_identifiers(raw_record_text):
            add_row(
                candidate_rows,
                current_ncppb,
                current_url,
                "derived_from_html_text",
                "collection_identifier",
                identifier,
            )
        add_row(candidate_rows, current_ncppb, current_url, "raw_record_text", "raw_record_text", raw_record_text)
        for row in candidate_rows:
            key = (row["ncppb_number"], row["source_type"], row["source_label"], row["keyword"].lower())
            if key in seen_rows:
                continue
            seen_rows.add(key)
            rows.append(row)

    for table_row in parser.rows:
        values = [cell.value() for cell in table_row]
        joined = clean_text(" ".join(values))
        ncppb_link = next(
            (
                (text, href)
                for cell in table_row
                for text, href in cell.links
                if re.search(r"furtherinfo\.cfm\?ncppb_no=", href, re.I)
            ),
            None,
        )
        if ncppb_link:
            flush_current_record()
            current_ncppb = normalise_ncppb(ncppb_link[0] or ncppb_link[1])
            current_url = urljoin(BASE_URL, ncppb_link[1])
            current_text_parts = [joined]
            add_row(rows, current_ncppb, current_url, "identifier", "ncppb_number", current_ncppb)
            if len(values) >= 3 and normalise_label(values[1]) == "catalogue_name":
                add_row(rows, current_ncppb, current_url, "header", "catalogue_name", values[2])
            continue

        if not current_ncppb:
            continue
        current_text_parts.append(joined)
        if len(values) >= 2 and values[0].strip().endswith(":"):
            add_row(rows, current_ncppb, current_url, "html_label", normalise_label(values[0]), values[1])

    flush_current_record()
    return rows


def write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["ncppb_number", "source_type", "source_label", "keyword", "ncppb_catalogue_url"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Saved NCPPB HTML file")
    parser.add_argument("--output", required=True, help="Long TSV keyword audit output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    html = Path(args.input).read_text(encoding="utf-8", errors="replace")
    rows = parse_html_keyword_rows(html)
    if not rows:
        raise SystemExit("No keyword rows found. Check that the input is a saved NCPPB result HTML page.")
    write_table(Path(args.output), rows)
    strains = {row["ncppb_number"] for row in rows}
    print(f"Wrote {len(rows)} keyword rows for {len(strains)} strains to {args.output}")


if __name__ == "__main__":
    main()
