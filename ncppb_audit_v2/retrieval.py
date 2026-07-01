from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .common import clean_text, unique_join, write_table


RESOURCE_COLUMNS = [
    "ncppb_number",
    "ncppb_current_name",
    "biosample_accession",
    "evidence_status",
    "match_decision",
    "identity_match_status",
    "matched_identifier",
    "identifier_strength",
    "taxonomy_status",
    "resource_type",
    "resource_accession",
    "resource_role",
    "assembly_level",
    "assembly_source",
    "assembly_total_length",
    "assembly_contig_count",
    "assembly_contig_n50",
    "sra_library_strategy",
    "sra_library_source",
    "sra_library_layout",
    "sra_instrument",
    "sra_total_bases",
    "sequence_bioproject_accessions",
    "selected_for_phylogeny",
    "download_tool",
    "download_command",
    "source_url",
]

PHYLOGENY_COLUMNS = [
    "ncppb_number",
    "ncppb_current_name",
    "confirmed_biosample_accessions",
    "provisional_biosample_accessions",
    "preferred_resource_type",
    "preferred_biosample_accession",
    "preferred_sequence_accessions",
    "preferred_assembly_level",
    "sequence_bioproject_accessions",
    "phylogeny_readiness",
    "download_tool",
    "download_command",
    "qc_required",
    "identity_review_required",
    "taxonomy_review_required",
    "selection_reason",
]

BIOPROJECT_COLUMNS = [
    "ncppb_number",
    "ncppb_current_name",
    "biosample_accession",
    "evidence_status",
    "bioproject_accession",
    "project_role",
    "project_sources",
    "project_title",
    "use_for_sequence_provenance",
    "review_required",
    "source_url",
]


def split_values(value: str) -> list[str]:
    return [clean_text(item) for item in re.split(r"\s*;\s*", value or "") if clean_text(item)]


def safe_json(value: str) -> dict:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def xml_value(value: str, tag: str) -> str:
    match = re.search(rf"<{re.escape(tag)}(?:\s[^>]*)?>(.*?)</{re.escape(tag)}>", value or "", re.I | re.S)
    return clean_text(match.group(1)) if match else ""


def sra_metadata(extra_json: str) -> dict[str, object]:
    record = safe_json(extra_json)
    expxml = str(record.get("expxml", ""))
    runs_xml = str(record.get("runs", ""))
    instrument_match = re.search(r"instrument_model=[\"']([^\"']+)[\"']", expxml, re.I)
    runs: dict[str, str] = {}
    for match in re.finditer(r"<Run\b([^>]*)>", runs_xml, re.I):
        attrs = match.group(1)
        accession = re.search(r"\bacc=[\"']([^\"']+)[\"']", attrs, re.I)
        bases = re.search(r"\btotal_bases=[\"'](\d+)[\"']", attrs, re.I)
        if accession:
            runs[accession.group(1).upper()] = bases.group(1) if bases else ""
    layout = "paired" if re.search(r"<PAIRED\b", expxml, re.I) else "single" if re.search(r"<SINGLE\b", expxml, re.I) else ""
    return {
        "bioproject": xml_value(expxml, "Bioproject"),
        "study_accession": re.search(r"<Study\b[^>]*\bacc=[\"']([^\"']+)[\"']", expxml, re.I).group(1)
        if re.search(r"<Study\b[^>]*\bacc=[\"']([^\"']+)[\"']", expxml, re.I)
        else "",
        "library_strategy": xml_value(expxml, "LIBRARY_STRATEGY").upper(),
        "library_source": xml_value(expxml, "LIBRARY_SOURCE").upper(),
        "library_selection": xml_value(expxml, "LIBRARY_SELECTION"),
        "library_layout": layout,
        "instrument": clean_text(instrument_match.group(1)) if instrument_match else "",
        "runs": runs,
    }


def project_accessions(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        clean_text(item.get("bioprojectaccn", ""))
        for item in values
        if isinstance(item, dict) and clean_text(item.get("bioprojectaccn", ""))
    ]


def assembly_metadata(extra_json: str) -> dict[str, str]:
    record = safe_json(extra_json)
    meta = str(record.get("meta", ""))

    def stat(name: str) -> str:
        match = re.search(rf'<Stat\b[^>]*category=["\']{re.escape(name)}["\'][^>]*>([^<]+)</Stat>', meta, re.I)
        return clean_text(match.group(1)) if match else ""

    accession = clean_text(record.get("assemblyaccession", ""))
    return {
        "accession": accession,
        "assembly_source": "RefSeq" if accession.upper().startswith("GCF_") else "GenBank" if accession.upper().startswith("GCA_") else "",
        "total_length": clean_text(record.get("totallength", "")) or stat("total_length"),
        "contig_count": clean_text(record.get("contigcount", "")) or stat("contig_count"),
        "contig_n50": clean_text(record.get("contign50", "")) or stat("contig_n50"),
        "gb_bioprojects": unique_join(project_accessions(record.get("gb_bioprojects", []))),
        "rs_bioprojects": unique_join(project_accessions(record.get("rs_bioprojects", []))),
    }


def assembly_rank(row: dict[str, str]) -> tuple[int, int, int, int, str]:
    level = clean_text(row.get("assembly_level", "")).lower()
    level_rank = 4 if "complete" in level else 3 if "chromosome" in level else 2 if "scaffold" in level else 1 if "contig" in level else 0
    source_rank = 1 if row.get("assembly_source") == "RefSeq" else 0

    def integer(value: str) -> int:
        try:
            return int(float(value or 0))
        except ValueError:
            return 0

    return (
        level_rank,
        source_rank,
        integer(row.get("assembly_contig_n50", "")),
        integer(row.get("assembly_total_length", "")),
        row.get("resource_accession", ""),
    )


def evidence_for_accession(supervisor: dict[str, str], accession: str) -> str:
    if accession in set(split_values(supervisor.get("confirmed_biosample_accessions", ""))):
        return "confirmed"
    if accession in set(split_values(supervisor.get("provisional_biosample_accessions", ""))):
        return "provisional"
    return "unclassified"


def build_retrieval_manifests(
    supervisor_rows: list[dict[str, str]],
    match_rows: list[dict[str, str]],
    linked_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    supervisors = {row["ncppb_number"]: row for row in supervisor_rows}
    matches = {
        (row.get("ncppb_number", ""), row.get("biosample_accession", "")): row
        for row in match_rows
        if row.get("biosample_accession", "")
    }
    linked_by_sample: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in linked_rows:
        if row.get("status") == "ok" and row.get("biosample_accession"):
            linked_by_sample[(row.get("ncppb_number", ""), row.get("biosample_accession", ""))].append(row)

    resource_rows: list[dict[str, str]] = []
    project_details: dict[tuple[str, str, str], dict[str, object]] = {}

    def base_row(number: str, accession: str) -> dict[str, str]:
        supervisor = supervisors.get(number, {})
        match = matches.get((number, accession), {})
        return {
            "ncppb_number": number,
            "ncppb_current_name": supervisor.get("ncppb_current_name", ""),
            "biosample_accession": accession,
            "evidence_status": evidence_for_accession(supervisor, accession),
            "match_decision": match.get("decision", ""),
            "identity_match_status": match.get("identity_match_status", ""),
            "matched_identifier": match.get("matched_identifier", ""),
            "identifier_strength": match.get("identifier_strength", ""),
            "taxonomy_status": match.get("taxonomy_status", ""),
            "selected_for_phylogeny": "no",
        }

    def add_project(
        number: str,
        biosample: str,
        project: str,
        source: str,
        title: str = "",
        url: str = "",
    ) -> None:
        if not project:
            return
        key = (number, biosample, project)
        item = project_details.setdefault(key, {"sources": set(), "title": "", "url": ""})
        item["sources"].add(source)
        if title and not item["title"]:
            item["title"] = title
        if url and not item["url"]:
            item["url"] = url

    for supervisor in supervisor_rows:
        number = supervisor["ncppb_number"]
        accessions = split_values(supervisor.get("confirmed_biosample_accessions", "")) + split_values(
            supervisor.get("provisional_biosample_accessions", "")
        )
        for biosample in dict.fromkeys(accessions):
            base = base_row(number, biosample)
            resource_rows.append(
                {
                    **base,
                    "resource_type": "biosample",
                    "resource_accession": biosample,
                    "resource_role": "identity_anchor",
                    "download_tool": "NCBI BioSample metadata",
                    "source_url": f"https://www.ncbi.nlm.nih.gov/biosample/{biosample}",
                }
            )
            for linked in linked_by_sample.get((number, biosample), []):
                database = linked.get("linked_database", "")
                if database == "assembly":
                    metadata = assembly_metadata(linked.get("extra_json", ""))
                    accession = linked.get("linked_accession", "") or metadata.get("accession", "")
                    sequence_projects = metadata.get("gb_bioprojects", "")
                    for project in split_values(metadata.get("gb_bioprojects", "")):
                        add_project(number, biosample, project, "assembly_genbank_project")
                    for project in split_values(metadata.get("rs_bioprojects", "")):
                        add_project(number, biosample, project, "refseq_annotation_project")
                    if accession:
                        safe_number = number.replace(" ", "_")
                        resource_rows.append(
                            {
                                **base,
                                "resource_type": "assembly",
                                "resource_accession": accession,
                                "resource_role": "assembled_genome_sequence",
                                "assembly_level": linked.get("assembly_level", ""),
                                "assembly_source": metadata.get("assembly_source", ""),
                                "assembly_total_length": metadata.get("total_length", ""),
                                "assembly_contig_count": metadata.get("contig_count", ""),
                                "assembly_contig_n50": metadata.get("contig_n50", ""),
                                "sequence_bioproject_accessions": sequence_projects,
                                "download_tool": "NCBI Datasets CLI",
                                "download_command": f"datasets download genome accession {accession} --include genome --filename {safe_number}_{accession}.zip",
                                "source_url": linked.get("source_url", ""),
                            }
                        )
                elif database == "sra":
                    metadata = sra_metadata(linked.get("extra_json", ""))
                    bioproject = clean_text(metadata.get("bioproject", ""))
                    if bioproject:
                        add_project(number, biosample, bioproject, "sra_sequence_project")
                    accessions = split_values(linked.get("linked_accession", ""))
                    for accession in accessions:
                        safe_number = number.replace(" ", "_")
                        total_bases = str(metadata.get("runs", {}).get(accession.upper(), ""))
                        resource_rows.append(
                            {
                                **base,
                                "resource_type": "sra_run",
                                "resource_accession": accession,
                                "resource_role": "raw_sequence_reads",
                                "sra_library_strategy": str(metadata.get("library_strategy", "")),
                                "sra_library_source": str(metadata.get("library_source", "")),
                                "sra_library_layout": str(metadata.get("library_layout", "")),
                                "sra_instrument": str(metadata.get("instrument", "")),
                                "sra_total_bases": total_bases,
                                "sequence_bioproject_accessions": bioproject,
                                "download_tool": "NCBI SRA Toolkit",
                                "download_command": f"prefetch {accession} && fasterq-dump {accession} --split-files --outdir fastq/{safe_number}",
                                "source_url": f"https://www.ncbi.nlm.nih.gov/sra/{accession}",
                            }
                        )
                elif database == "bioproject":
                    add_project(
                        number,
                        biosample,
                        linked.get("linked_accession", ""),
                        "biosample_elink",
                        linked.get("title", ""),
                        linked.get("source_url", ""),
                    )

    bioproject_rows: list[dict[str, str]] = []
    for (number, biosample, project), details in sorted(project_details.items()):
        base = base_row(number, biosample)
        sources = set(details["sources"])
        title = clean_text(details.get("title", ""))
        if "sra_sequence_project" in sources or "assembly_genbank_project" in sources:
            role = "sequence_source_project"
            use = "yes"
            review = "no"
        elif "refseq_annotation_project" in sources or "refseq prokaryotic genome annotation" in title.lower():
            role = "annotation_project"
            use = "no"
            review = "no"
        else:
            role = "biosample_elink_only"
            use = "no"
            review = "yes"
        url = clean_text(details.get("url", "")) or f"https://www.ncbi.nlm.nih.gov/bioproject/{project}"
        bioproject_rows.append(
            {
                **base,
                "bioproject_accession": project,
                "project_role": role,
                "project_sources": unique_join(sorted(sources)),
                "project_title": title,
                "use_for_sequence_provenance": use,
                "review_required": review,
                "source_url": url,
            }
        )
        resource_rows.append(
            {
                **base,
                "resource_type": "bioproject",
                "resource_accession": project,
                "resource_role": role,
                "download_tool": "NCBI BioProject metadata",
                "source_url": url,
            }
        )

    resources_by_strain: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in resource_rows:
        resources_by_strain[row["ncppb_number"]].append(row)

    phylogeny_rows: list[dict[str, str]] = []
    for supervisor in supervisor_rows:
        number = supervisor["ncppb_number"]
        resources = resources_by_strain.get(number, [])
        assemblies = [
            row for row in resources if row.get("evidence_status") == "confirmed" and row.get("resource_type") == "assembly"
        ]
        wgs_runs = [
            row
            for row in resources
            if row.get("evidence_status") == "confirmed"
            and row.get("resource_type") == "sra_run"
            and row.get("sra_library_strategy") == "WGS"
            and row.get("sra_library_source") in {"", "GENOMIC"}
        ]
        selected: list[dict[str, str]] = []
        preferred_type = "none"
        readiness = "no_confirmed_public_sequence"
        reason = "No confirmed Assembly or WGS SRA run is linked to this strain."
        if assemblies:
            selected = [max(assemblies, key=assembly_rank)]
            preferred_type = "assembly"
            readiness = "assembly_available_qc_required"
            reason = "Selected the highest assembly level, then preferred RefSeq and higher contig N50."
        elif wgs_runs:
            bases_by_sample: dict[str, int] = defaultdict(int)
            for row in wgs_runs:
                try:
                    bases_by_sample[row["biosample_accession"]] += int(row.get("sra_total_bases", "") or 0)
                except ValueError:
                    pass
            chosen_sample = max(
                sorted({row["biosample_accession"] for row in wgs_runs}),
                key=lambda accession: bases_by_sample.get(accession, 0),
            )
            selected = [row for row in wgs_runs if row["biosample_accession"] == chosen_sample]
            preferred_type = "sra_wgs_reads"
            readiness = "raw_wgs_reads_require_assembly_and_qc"
            reason = "No confirmed assembly; selected WGS genomic run(s) from the BioSample with the most reported bases."
        elif supervisor.get("confirmed_biosample_accessions"):
            readiness = "confirmed_biosample_metadata_only"
            reason = "Confirmed strain identity is present, but no linked assembly or WGS genomic run is available."
        elif supervisor.get("provisional_biosample_accessions"):
            readiness = "identity_review_required_before_use"
            reason = "Only provisional BioSample identity evidence is available; do not include in a tree before review."

        for row in selected:
            row["selected_for_phylogeny"] = "yes"
        commands = [row.get("download_command", "") for row in selected if row.get("download_command")]
        phylogeny_rows.append(
            {
                "ncppb_number": number,
                "ncppb_current_name": supervisor.get("ncppb_current_name", ""),
                "confirmed_biosample_accessions": supervisor.get("confirmed_biosample_accessions", ""),
                "provisional_biosample_accessions": supervisor.get("provisional_biosample_accessions", ""),
                "preferred_resource_type": preferred_type,
                "preferred_biosample_accession": unique_join(row.get("biosample_accession", "") for row in selected),
                "preferred_sequence_accessions": unique_join(row.get("resource_accession", "") for row in selected),
                "preferred_assembly_level": unique_join(row.get("assembly_level", "") for row in selected),
                "sequence_bioproject_accessions": unique_join(
                    project
                    for row in selected
                    for project in split_values(row.get("sequence_bioproject_accessions", ""))
                ),
                "phylogeny_readiness": readiness,
                "download_tool": unique_join(row.get("download_tool", "") for row in selected),
                "download_command": " ; ".join(commands),
                "qc_required": "yes" if selected else "not_applicable",
                "identity_review_required": "yes" if readiness == "identity_review_required_before_use" else "no",
                "taxonomy_review_required": supervisor.get("taxonomy_review_required", "no"),
                "selection_reason": reason,
            }
        )

    resource_rows.sort(
        key=lambda row: (
            int(re.search(r"\d+", row["ncppb_number"]).group(0)),
            row.get("biosample_accession", ""),
            row.get("resource_type", ""),
            row.get("resource_accession", ""),
        )
    )
    return resource_rows, phylogeny_rows, bioproject_rows


def write_retrieval_outputs(
    outdir: Path,
    supervisor_rows: list[dict[str, str]],
    match_rows: list[dict[str, str]],
    linked_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    resources, phylogeny, projects = build_retrieval_manifests(supervisor_rows, match_rows, linked_rows)
    write_table(outdir / "sequence_resource_manifest.tsv", resources, RESOURCE_COLUMNS)
    write_table(outdir / "phylogeny_input_manifest.tsv", phylogeny, PHYLOGENY_COLUMNS)
    write_table(outdir / "bioproject_mapping.tsv", projects, BIOPROJECT_COLUMNS)

    readiness: dict[str, int] = defaultdict(int)
    for row in phylogeny:
        readiness[row["phylogeny_readiness"]] += 1
    lines = [
        "# Sequence retrieval and phylogeny-input summary",
        "",
        f"- Current NCPPB strains: {len(phylogeny)}",
        f"- Preferred assembled genomes: {sum(row['preferred_resource_type'] == 'assembly' for row in phylogeny)}",
        f"- WGS-read fallbacks: {sum(row['preferred_resource_type'] == 'sra_wgs_reads' for row in phylogeny)}",
        f"- Selected BioProject provenance links: {sum(bool(row['sequence_bioproject_accessions']) for row in phylogeny)}",
        f"- Long-form resource rows: {len(resources)}",
        "",
        "## Readiness categories",
        "",
        *[f"- {key}: {value}" for key, value in sorted(readiness.items())],
        "",
        "`BioSample` is the strain-identity anchor. `Assembly` and WGS `SRA` runs are sequence sources. BioProjects are used for provenance only when recovered from Assembly or SRA metadata; BioSample-only ELink projects are not automatically treated as sequence projects.",
    ]
    (outdir / "sequence_retrieval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return resources, phylogeny, projects
