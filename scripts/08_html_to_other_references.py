#!/usr/bin/env python3
"""Extract only NCPPB number and Other references from a saved NCPPB HTML page."""

from __future__ import annotations

import argparse
import csv
import re
from html import unescape
from pathlib import Path


OUTPUT_COLUMNS = ["ncppb_number", "other_references"]


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def normalise_ncppb(value: str) -> str:
    match = re.search(r"(\d+)", value or "")
    return f"NCPPB {match.group(1)}" if match else clean_text(value)


def table_delimiter(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def strip_html_tags(fragment: str) -> str:
    text = re.sub(r"<\s*br\s*/?\s*>", " ", fragment, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text)


def reconstruct_if_view_source(html: str) -> str:
    line_cells = re.findall(
        r'<td\s+class=["\']line-content["\'][^>]*>(.*?)</td>\s*</tr>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not line_cells:
        return html
    lines = [strip_html_tags(cell) for cell in line_cells]
    return "\n".join(lines)


def parse_other_reference_rows(html: str) -> list[dict[str, str]]:
    reconstructed = reconstruct_if_view_source(html)
    link_pattern = re.compile(
        r"<a\b[^>]*href\s*=\s*[\"']?[^\"'>]*furtherinfo\.cfm\?ncppb_no=(\d+)[^>]*>(.*?)</a>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    links = list(link_pattern.finditer(reconstructed))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, link in enumerate(links):
        ncppb_number = normalise_ncppb(link.group(1) or strip_html_tags(link.group(2)))
        if not ncppb_number or ncppb_number in seen:
            continue

        next_start = links[index + 1].start() if index + 1 < len(links) else len(reconstructed)
        record_block = reconstructed[link.end() : next_start]
        match = re.search(
            r"<strong>\s*Other references:\s*</strong>\s*</td>\s*<td[^>]*>(.*?)</td>",
            record_block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        other_references = ""
        if match:
            other_references = clean_text(strip_html_tags(match.group(1)))

        seen.add(ncppb_number)
        rows.append({"ncppb_number": ncppb_number, "other_references": other_references})

    return rows


def write_table(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, delimiter=table_delimiter(path))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Saved NCPPB HTML file")
    parser.add_argument("--output", required=True, help="Two-column CSV/TSV output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise SystemExit(f"Input HTML not found: {input_path}")

    html = input_path.read_text(encoding="utf-8", errors="replace")
    rows = parse_other_reference_rows(html)
    if not rows:
        raise SystemExit("No NCPPB records found in the HTML file.")

    write_table(output_path, rows)
    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
