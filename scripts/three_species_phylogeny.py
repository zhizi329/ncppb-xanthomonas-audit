#!/usr/bin/env python3
"""Build a reproducible three-species NCPPB read-based phylogeny workflow.

The workflow keeps one paired-end Illumina run per canonical NCPPB strain,
then creates reference-based consensus sequences with low-coverage masking.
The consensus sequences share reference coordinates, so the resulting core
alignment can be used by IQ-TREE with branch lengths in substitutions/site.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import shlex
from collections import defaultdict
from pathlib import Path


TARGET_SPECIES = [
    "Xanthomonas campestris",
    "Xanthomonas citri",
    "Xanthomonas euvesicatoria",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean(value)).strip("_")
    return token or "NA"


def strain_key(value: str) -> str:
    match = re.search(r"NCPPB\s*_?\s*(\d+)", value.upper())
    if match:
        return f"NCPPB_{match.group(1)}"
    return safe_token(value.upper())


def tree_label(row: dict[str, str]) -> str:
    return f"{strain_key(row['ncppb'])}__{safe_token(row['species'])}"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def split_semicolon(value: str) -> list[str]:
    return [item for item in clean(value).split(";") if item]


def https_url(value: str) -> str:
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("ftp://"):
        value = value.removeprefix("ftp://")
    return "https://" + value


def total_bytes(value: str) -> int:
    try:
        return sum(int(item) for item in split_semicolon(value))
    except ValueError:
        return 0


def command_candidates(args: argparse.Namespace) -> None:
    rows = read_tsv(args.manifest)
    seen_runs: set[str] = set()
    seen_strains: set[tuple[str, str]] = set()
    out: list[dict[str, object]] = []

    for row in rows:
        species = clean(row.get("species"))
        run = clean(row.get("accession"))
        if species not in TARGET_SPECIES or not run.startswith("SRR"):
            continue
        if clean(row.get("seq_platform")).upper() != "ILLUMINA":
            continue
        if clean(row.get("seq_library")).upper() != "PAIRED":
            continue
        key = (species, strain_key(row.get("ncppb", "")))
        if run in seen_runs or key in seen_strains:
            # A second run for the same strain is retained in the audit file,
            # but the candidate table is one-run-per-strain by design.
            continue
        seen_runs.add(run)
        seen_strains.add(key)
        out.append(
            {
                **row,
                "strain_key": key[1],
                "run_accession": run,
                "tree_label": tree_label(row),
            }
        )

    fields = [
        "species", "strain_key", "ncppb", "pathovar", "country", "source_details",
        "sample_accession", "study_accession", "experiment_accession", "run_accession",
        "tree_label", "accession_type", "seq_platform", "seq_library",
    ]
    write_tsv(args.out, out, fields)


def command_all_candidates(args: argparse.Namespace) -> None:
    rows = read_tsv(args.manifest)
    seen_runs: set[str] = set()
    out: list[dict[str, object]] = []
    for row in rows:
        species = clean(row.get("species"))
        run = clean(row.get("accession"))
        if species not in TARGET_SPECIES or not run.startswith("SRR"):
            continue
        if clean(row.get("seq_platform")).upper() != "ILLUMINA":
            continue
        if clean(row.get("seq_library")).upper() != "PAIRED":
            continue
        if run in seen_runs:
            continue
        seen_runs.add(run)
        out.append(
            {
                **row,
                "strain_key": strain_key(row.get("ncppb", "")),
                "run_accession": run,
                "tree_label": tree_label(row),
            }
        )
    fields = [
        "species", "strain_key", "ncppb", "pathovar", "country", "source_details",
        "sample_accession", "study_accession", "experiment_accession", "run_accession",
        "tree_label", "accession_type", "seq_platform", "seq_library",
    ]
    write_tsv(args.out, out, fields)


def command_write_ena(args: argparse.Namespace) -> None:
    rows = read_tsv(args.candidates)
    parts = args.metadata.with_suffix(args.metadata.suffix + ".parts")
    lines = [
        "#!/usr/bin/env bash", "set -euo pipefail",
        f"OUT={shlex.quote(str(args.metadata))}",
        f"PARTS={shlex.quote(str(parts))}",
        "JOBS=${JOBS:-12}",
        "jobs=0",
        "mkdir -p \"$(dirname \"$OUT\")\" \"$PARTS\"",
        "printf 'run_accession\\tfastq_ftp\\tfastq_bytes\\tfastq_md5\\tlibrary_layout\\tinstrument_platform\\n' > \"$OUT\"",
    ]
    fields = "run_accession,fastq_ftp,fastq_bytes,fastq_md5,library_layout,instrument_platform"
    run_order: list[str] = []
    jobs = 0
    for row in rows:
        run = row["run_accession"]
        url = f"https://www.ebi.ac.uk/ena/portal/api/filereport?accession={run}&result=read_run&fields={fields}&format=tsv&download=false"
        run_order.append(run)
        lines.extend([
            f"(curl -fsSL --max-time 90 --retry 3 --retry-delay 2 {shlex.quote(url)} | tail -n +2 > \"$PARTS/{run}.tsv\") &",
            "jobs=$((jobs + 1))",
            "if (( jobs >= JOBS )); then wait; jobs=0; fi",
        ])
    lines.extend(["wait"])
    for run in run_order:
        lines.append(f"if [[ -s \"$PARTS/{run}.tsv\" ]]; then cat \"$PARTS/{run}.tsv\" >> \"$OUT\"; fi")
    args.script.parent.mkdir(parents=True, exist_ok=True)
    args.script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.script.chmod(0o755)


def command_select(args: argparse.Namespace) -> None:
    candidates = read_tsv(args.candidates)
    metadata = {row["run_accession"]: row for row in read_tsv(args.metadata)}
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    rejected: list[dict[str, object]] = []

    for row in candidates:
        meta = metadata.get(row["run_accession"])
        if not meta:
            rejected.append({**row, "reject_reason": "missing_ena_metadata"})
            continue
        urls = split_semicolon(meta.get("fastq_ftp", ""))
        md5s = split_semicolon(meta.get("fastq_md5", ""))
        sizes = split_semicolon(meta.get("fastq_bytes", ""))
        if clean(meta.get("library_layout")).upper() != "PAIRED" or len(urls) < 2:
            rejected.append({**row, **meta, "reject_reason": "not_paired_fastq"})
            continue
        # ENA may report an additional unpaired FASTQ before the paired R1/R2
        # files. The tree uses the paired component consistently across runs.
        if len(urls) > 2:
            urls, md5s, sizes = urls[-2:], md5s[-2:], sizes[-2:]
        enriched = {
            **row,
            **meta,
            "total_bytes": total_bytes(meta.get("fastq_bytes", "")),
            "fastq_url_1": https_url(urls[0]),
            "fastq_url_2": https_url(urls[1]),
            "fastq_bytes_1": sizes[0] if len(sizes) > 0 else "",
            "fastq_bytes_2": sizes[1] if len(sizes) > 1 else "",
            "fastq_md5_1": md5s[0] if len(md5s) > 0 else "",
            "fastq_md5_2": md5s[1] if len(md5s) > 1 else "",
        }
        grouped[(row["species"], row["strain_key"])].append(enriched)

    selected: list[dict[str, object]] = []
    for key in sorted(grouped):
        choices = sorted(
            grouped[key],
            key=lambda row: (int(row.get("total_bytes", 0) or 0), row["run_accession"]),
            reverse=True,
        )
        chosen = choices[0]
        selected.append(chosen)
        for duplicate in choices[1:]:
            rejected.append({**duplicate, "reject_reason": "duplicate_strain_lower_bytes"})

    fields = [
        "species", "strain_key", "ncppb", "pathovar", "country", "source_details",
        "sample_accession", "study_accession", "experiment_accession", "run_accession",
        "tree_label", "library_layout", "instrument_platform", "total_bytes",
        "fastq_bytes_1", "fastq_bytes_2", "fastq_md5_1", "fastq_md5_2", "fastq_url_1", "fastq_url_2",
    ]
    write_tsv(args.out, selected, fields)
    write_tsv(args.rejected, rejected, fields + ["reject_reason"])


def command_write_download(args: argparse.Namespace) -> None:
    rows = read_tsv(args.selected)
    project_root = Path(__file__).resolve().parents[1]
    core_bin = project_root / ".cache/conda-envs/srr_phylo_core/bin"
    snp_bin = project_root / ".cache/conda-envs/srr_phylo_snp/bin"
    raw = args.outdir / "fastq_raw"
    trimmed = args.outdir / "fastq_fastp"
    reports = args.outdir / "fastp_reports"
    lines = [
        "#!/usr/bin/env bash", "set -euo pipefail",
        f"OUTDIR={shlex.quote(str(args.outdir))}",
        f"RAW={shlex.quote(str(raw))}", f"TRIMMED={shlex.quote(str(trimmed))}", f"REPORTS={shlex.quote(str(reports))}",
        f"export PATH={shlex.quote(str(core_bin))}:{shlex.quote(str(snp_bin))}:\"$PATH\"",
        "mkdir -p \"$RAW\" \"$TRIMMED\" \"$REPORTS\"",
        "THREADS=${THREADS:-4}",
        f"JOBS=${{JOBS:-{args.jobs}}}",
        "jobs=0",
        "LOGS=\"$OUTDIR/download_fastp_logs\"",
        "mkdir -p \"$LOGS\"",
        "download_checked() {",
        "  local file=$1 url=$2 expected=$3 actual",
        "  if [[ -s \"$file\" && -n \"$expected\" ]]; then",
        "    actual=$(md5 -q \"$file\")",
        "    if [[ \"$actual\" != \"$expected\" ]]; then",
        "      printf 'Removing incomplete or corrupt FASTQ: %s\\n' \"$file\" >&2",
        "      rm -f \"$file\"",
        "    fi",
        "  fi",
        "  if [[ ! -s \"$file\" ]]; then",
        "    curl -fL --retry 8 --retry-all-errors --retry-delay 5 --connect-timeout 30 --speed-time 120 --speed-limit 1048576 -C - -o \"$file\" \"$url\"",
        "  fi",
        "  if [[ -n \"$expected\" ]]; then",
        "    actual=$(md5 -q \"$file\")",
        "    [[ \"$actual\" == \"$expected\" ]] || { rm -f \"$file\"; return 1; }",
        "  fi",
        "}",
    ]
    for row in rows:
        label = row["tree_label"]
        r1 = raw / f"{label}_1.fastq.gz"
        r2 = raw / f"{label}_2.fastq.gz"
        t1 = trimmed / f"{label}_R1.fastq.gz"
        t2 = trimmed / f"{label}_R2.fastq.gz"
        json = reports / f"{label}.fastp.json"
        html = reports / f"{label}.fastp.html"
        lines.append("(")
        lines.extend([
            f"download_checked {shlex.quote(str(r1))} {shlex.quote(row['fastq_url_1'])} {shlex.quote(row.get('fastq_md5_1', ''))}",
            f"download_checked {shlex.quote(str(r2))} {shlex.quote(row['fastq_url_2'])} {shlex.quote(row.get('fastq_md5_2', ''))}",
            f"if [[ ! -s {shlex.quote(str(t1))} || ! -s {shlex.quote(str(t2))} ]]; then fastp --thread \"$THREADS\" --detect_adapter_for_pe --length_required 50 -i {shlex.quote(str(r1))} -I {shlex.quote(str(r2))} -o {shlex.quote(str(t1))} -O {shlex.quote(str(t2))} -j {shlex.quote(str(json))} -h {shlex.quote(str(html))} > {shlex.quote(str(reports / (label + '.fastp.log')))} 2>&1; fi",
        ])
        lines.extend([
            ") &",
            "jobs=$((jobs + 1))",
            "if (( jobs >= JOBS )); then wait; jobs=0; fi",
        ])
    lines.extend(["wait", "multiqc --force --outdir \"$OUTDIR/multiqc\" \"$REPORTS\""])
    args.script.parent.mkdir(parents=True, exist_ok=True)
    args.script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.script.chmod(0o755)


def command_write_snp(args: argparse.Namespace) -> None:
    rows = read_tsv(args.selected)
    project_root = Path(__file__).resolve().parents[1]
    core_bin = project_root / ".cache/conda-envs/srr_phylo_core/bin"
    snp_bin = project_root / ".cache/conda-envs/srr_phylo_snp/bin"
    out = args.outdir
    raw = out / "fastq_raw"
    trimmed = out / "fastq_fastp"
    refs = out / "references"
    mappings = out / "mapping"
    consensus = out / "consensus"
    alignments = out / "alignments"
    trees = out / "trees"
    lines = [
        "#!/usr/bin/env bash", "set -euo pipefail",
        f"OUTDIR={shlex.quote(str(out))}", f"REFS={shlex.quote(str(refs))}", f"MAP={shlex.quote(str(mappings))}", f"CONS={shlex.quote(str(consensus))}", f"ALN={shlex.quote(str(alignments))}", f"TREES={shlex.quote(str(trees))}",
        f"export PATH={shlex.quote(str(core_bin))}:{shlex.quote(str(snp_bin))}:\"$PATH\"",
        "THREADS=${THREADS:-4}", "JOBS=${JOBS:-3}", "jobs=0", "mkdir -p \"$MAP\" \"$CONS\" \"$ALN\" \"$TREES\"",
    ]
    for row in rows:
        species = row["species"]
        safe_species = safe_token(species)
        label = row["tree_label"]
        ref = refs / f"{safe_species}.fna"
        r1 = trimmed / f"{label}_R1.fastq.gz"
        r2 = trimmed / f"{label}_R2.fastq.gz"
        bam = mappings / f"{label}.bam"
        vcf = mappings / f"{label}.vcf.gz"
        bed = mappings / f"{label}.lowcov.bed"
        coverage = mappings / f"{label}.coverage.tsv"
        flagstat = mappings / f"{label}.flagstat.tsv"
        fasta = consensus / f"{label}.fna"
        lines.append("(")
        lines.extend([
            f"if [[ ! -s {shlex.quote(str(bam))} ]]; then bwa mem -t \"$THREADS\" {shlex.quote(str(ref))} {shlex.quote(str(r1))} {shlex.quote(str(r2))} | samtools sort -@ \"$THREADS\" -o {shlex.quote(str(bam))} -; samtools index {shlex.quote(str(bam))}; fi",
            f"if [[ ! -s {shlex.quote(str(vcf))} ]]; then bcftools mpileup -q 20 -Q 20 -a FORMAT/DP -f {shlex.quote(str(ref))} {shlex.quote(str(bam))} -Ou | bcftools call --ploidy 1 -mv -Ou | bcftools view -v snps -Oz -o {shlex.quote(str(vcf))}; tabix -f -p vcf {shlex.quote(str(vcf))}; fi",
            f"if [[ ! -s {shlex.quote(str(bed))} ]]; then samtools depth -aa -q 20 -Q 20 {shlex.quote(str(bam))} | awk -v OFS='\\t' '$3 < 5 {{print $1, $2-1, $2}}' > {shlex.quote(str(bed))}; fi",
            f"if [[ ! -s {shlex.quote(str(coverage))} ]]; then samtools coverage {shlex.quote(str(bam))} > {shlex.quote(str(coverage))}; fi",
            f"if [[ ! -s {shlex.quote(str(flagstat))} ]]; then samtools flagstat -O tsv {shlex.quote(str(bam))} > {shlex.quote(str(flagstat))}; fi",
            f"if [[ ! -s {shlex.quote(str(fasta))} ]]; then bcftools consensus -f {shlex.quote(str(ref))} --mask {shlex.quote(str(bed))} {shlex.quote(str(vcf))} > {shlex.quote(str(fasta) + '.tmp')}; {{ printf '>{label}\\n'; awk '!/^>/ {{printf \"%s\", $0}} END {{printf \"\\n\"}}' {shlex.quote(str(fasta) + '.tmp')}; }} > {shlex.quote(str(fasta))}; rm -f {shlex.quote(str(fasta) + '.tmp')}; fi",
            f"rm -f {shlex.quote(str(bam))} {shlex.quote(str(bam) + '.bai')}",
        ])
        lines.extend([
            ") &",
            "jobs=$((jobs + 1))",
            "if (( jobs >= JOBS )); then wait; jobs=0; fi",
        ])
    lines.append("wait")
    for species in TARGET_SPECIES:
        safe_species = safe_token(species)
        prefix = alignments / safe_species
        species_rows = [row for row in rows if row["species"] == species]
        if not species_rows:
            continue
        fasta_list = alignments / f"{safe_species}.consensus_files.txt"
        fasta_list.parent.mkdir(parents=True, exist_ok=True)
        fasta_list.write_text("\n".join(str(consensus / f"{row['tree_label']}.fna") for row in species_rows) + "\n", encoding="utf-8")
        lines.extend([
            f"if [[ ! -s {shlex.quote(str(prefix) + '.consensus.fna')} ]]; then cat $(tr '\\n' ' ' < {shlex.quote(str(fasta_list))}) > {shlex.quote(str(prefix) + '.consensus.fna')}; fi",
            f"if [[ ! -s {shlex.quote(str(prefix) + '.core.fna')} ]]; then python3 {shlex.quote(str(args.core_script))} filter-core --input {shlex.quote(str(prefix) + '.consensus.fna')} --output {shlex.quote(str(prefix) + '.core.fna')} --min-complete 1.0; fi",
            f"if [[ ! -s {shlex.quote(str(prefix) + '.snp.fna')} ]]; then snp-sites {shlex.quote(str(prefix) + '.core.fna')} > {shlex.quote(str(prefix) + '.snp.fna')}; fi",
            f"python3 {shlex.quote(str(args.core_script))} distances --input {shlex.quote(str(prefix) + '.snp.fna')} --out-prefix {shlex.quote(str(out / 'distances' / safe_species))}",
            f"if [[ ! -s {shlex.quote(str(trees / (safe_species + '.iqtree')))} ]]; then iqtree3 -s {shlex.quote(str(prefix) + '.core.fna')} -m GTR+F+G4 -B 1000 --alrt 1000 -T AUTO --prefix {shlex.quote(str(trees / safe_species))}; fi",
        ])
    if not args.no_finalize:
        lines.append(f"python3 {shlex.quote(str(args.core_script))} itol --selected {shlex.quote(str(args.selected))} --trees {shlex.quote(str(trees))} --outdir {shlex.quote(str(out / 'itol'))}")
        lines.append(f"python3 {shlex.quote(str(args.core_script))} fastp-summary --selected {shlex.quote(str(args.selected))} --reports {shlex.quote(str(out / 'fastp_reports'))} --out {shlex.quote(str(out / 'fastp_qc_summary.tsv'))}")
        lines.append(f"python3 {shlex.quote(str(args.core_script))} mapping-summary --selected {shlex.quote(str(args.selected))} --mapping-dir {shlex.quote(str(mappings))} --out {shlex.quote(str(out / 'mapping_qc_summary.tsv'))}")
    args.script.parent.mkdir(parents=True, exist_ok=True)
    args.script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.script.chmod(0o755)


def command_filter_species(args: argparse.Namespace) -> None:
    rows = [row for row in read_tsv(args.selected) if row.get("species") == args.species]
    if not rows:
        raise SystemExit(f"No rows found for {args.species}")
    write_tsv(args.out, rows, list(rows[0]))


def fasta_records(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    name: str | None = None
    seq: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if name is not None:
                    records.append((name, "".join(seq)))
                name, seq = line[1:].split()[0], []
            else:
                seq.append(line.strip())
    if name is not None:
        records.append((name, "".join(seq)))
    return records


def write_fasta(path: Path, records: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for name, sequence in records:
            handle.write(f">{name}\n")
            for start in range(0, len(sequence), 80):
                handle.write(sequence[start:start + 80] + "\n")


def command_filter_core(args: argparse.Namespace) -> None:
    records = fasta_records(args.input)
    if not records:
        raise SystemExit(f"No FASTA records in {args.input}")
    length = len(records[0][1])
    if any(len(sequence) != length for _, sequence in records):
        raise SystemExit("Consensus sequences are not the same length")
    keep: list[int] = []
    for index in range(length):
        complete = sum(sequence[index].upper() in "ACGT" for _, sequence in records)
        if complete / len(records) >= args.min_complete:
            keep.append(index)
    filtered = [(name, "".join(sequence[index] for index in keep)) for name, sequence in records]
    write_fasta(args.output, filtered)
    stats = args.output.with_suffix(args.output.suffix + ".stats.tsv")
    stats.write_text(f"samples\t{len(records)}\nreference_length\t{length}\ncore_sites\t{len(keep)}\nmin_complete\t{args.min_complete}\n", encoding="utf-8")


def command_distances(args: argparse.Namespace) -> None:
    records = fasta_records(args.input)
    if len(records) < 2:
        raise SystemExit("At least two aligned FASTA records are required")
    length = len(records[0][1])
    if any(len(sequence) != length for _, sequence in records):
        raise SystemExit("Aligned FASTA records have unequal lengths")
    args.out_prefix.parent.mkdir(parents=True, exist_ok=True)
    names = [name for name, _ in records]
    snp_matrix: list[list[int]] = [[0] * len(records) for _ in records]
    p_matrix: list[list[float]] = [[0.0] * len(records) for _ in records]
    long_rows: list[dict[str, object]] = []
    for i, (name_a, seq_a) in enumerate(records):
        for j in range(i + 1, len(records)):
            name_b, seq_b = records[j]
            comparable = [
                (base_a, base_b)
                for base_a, base_b in zip(seq_a.upper(), seq_b.upper())
                if base_a in "ACGT" and base_b in "ACGT"
            ]
            compared_sites = len(comparable)
            differences = sum(base_a != base_b for base_a, base_b in comparable)
            p_distance = differences / compared_sites if compared_sites else 0.0
            snp_matrix[i][j] = snp_matrix[j][i] = differences
            p_matrix[i][j] = p_matrix[j][i] = p_distance
            long_rows.append(
                {
                    "sample_a": name_a,
                    "sample_b": name_b,
                    "compared_variable_sites": compared_sites,
                    "snp_differences": differences,
                    "p_distance": f"{p_distance:.10f}",
                }
            )
    write_tsv(
        args.out_prefix.with_suffix(".pairwise_long.tsv"),
        long_rows,
        ["sample_a", "sample_b", "compared_variable_sites", "snp_differences", "p_distance"],
    )
    for suffix, matrix, formatter in [
        (".snp_distance_matrix.tsv", snp_matrix, str),
        (".p_distance_matrix.tsv", p_matrix, lambda value: f"{value:.10f}"),
    ]:
        path = args.out_prefix.with_suffix(suffix)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["sample", *names])
            for name, values in zip(names, matrix):
                writer.writerow([name, *(formatter(value) for value in values)])


def command_fastp_summary(args: argparse.Namespace) -> None:
    rows = read_tsv(args.selected)
    out: list[dict[str, object]] = []
    for row in rows:
        report = args.reports / f"{row['tree_label']}.fastp.json"
        if not report.exists():
            continue
        data = json.loads(report.read_text(encoding="utf-8"))
        before = data["summary"]["before_filtering"]
        after = data["summary"]["after_filtering"]
        filtering = data.get("filtering_result", {})
        before_reads = int(before.get("total_reads", 0))
        passed_reads = int(filtering.get("passed_filter_reads", after.get("total_reads", 0)))
        out.append(
            {
                "species": row["species"], "strain_key": row["strain_key"],
                "ncppb": row["ncppb"], "run_accession": row["run_accession"],
                "pathovar": row.get("pathovar", ""),
                "before_read_pairs": before_reads // 2,
                "passed_read_pairs": passed_reads // 2,
                "passed_read_percent": f"{(passed_reads / before_reads * 100) if before_reads else 0:.2f}",
                "after_total_bases": after.get("total_bases", ""),
                "after_gc_percent": f"{float(after.get('gc_content', 0)) * 100:.2f}",
                "after_q30_percent": f"{float(after.get('q30_rate', 0)) * 100:.2f}",
                "duplication_percent": f"{float(data.get('duplication', {}).get('rate', 0)) * 100:.2f}",
                "insert_size_peak": data.get("insert_size", {}).get("peak", ""),
                "fastp_json": str(report),
            }
        )
    fields = [
        "species", "strain_key", "ncppb", "run_accession", "pathovar",
        "before_read_pairs", "passed_read_pairs", "passed_read_percent",
        "after_total_bases", "after_gc_percent", "after_q30_percent",
        "duplication_percent", "insert_size_peak", "fastp_json",
    ]
    write_tsv(args.out, out, fields)


def command_mapping_summary(args: argparse.Namespace) -> None:
    rows = read_tsv(args.selected)
    out: list[dict[str, object]] = []
    for row in rows:
        coverage_path = args.mapping_dir / f"{row['tree_label']}.coverage.tsv"
        if not coverage_path.exists():
            continue
        reference_bases = 0
        covered_bases = 0
        depth_weighted_sum = 0.0
        for line in coverage_path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 7:
                continue
            try:
                start, end = int(fields[1]), int(fields[2])
                covbases, depth = int(fields[4]), float(fields[6])
            except ValueError:
                continue
            length = end - start + 1
            reference_bases += length
            covered_bases += covbases
            depth_weighted_sum += length * depth
        out.append(
            {
                "species": row["species"], "strain_key": row["strain_key"],
                "ncppb": row["ncppb"], "run_accession": row["run_accession"],
                "reference_bases": reference_bases,
                "covered_bases": covered_bases,
                "coverage_percent": f"{(covered_bases / reference_bases * 100) if reference_bases else 0:.2f}",
                "mean_depth": f"{(depth_weighted_sum / reference_bases) if reference_bases else 0:.2f}",
                "coverage_file": str(coverage_path),
            }
        )
    write_tsv(
        args.out,
        out,
        [
            "species", "strain_key", "ncppb", "run_accession", "reference_bases",
            "covered_bases", "coverage_percent", "mean_depth", "coverage_file",
        ],
    )


def itol_header(dataset_type: str, label: str, color: str = "#2f6f73") -> list[str]:
    return [
        f"DATASET_{dataset_type}", "SEPARATOR TAB", f"DATASET_LABEL\t{label}", f"COLOR\t{color}", "DATASET_SCALE\t0", "LEGEND_TITLE\tPhytoBacExplorer NCPPB", "DATA\n",
    ]


def command_itol(args: argparse.Namespace) -> None:
    rows = read_tsv(args.selected)
    args.outdir.mkdir(parents=True, exist_ok=True)
    colors = ["#2f6f73", "#7b6fbd", "#c46a3a", "#4d7c3f", "#a13e5a", "#64748b", "#d99a2b", "#2563eb", "#9333ea", "#0f766e"]
    for safe_species in sorted({safe_token(row["species"]) for row in rows}):
        species_rows = [row for row in rows if safe_token(row["species"]) == safe_species]
        pathovar_colors: dict[str, str] = {}
        country_colors: dict[str, str] = {}
        for row in species_rows:
            pathovar = clean(row.get("pathovar")) or "unassigned"
            country = clean(row.get("country")) or "unassigned"
            if pathovar not in pathovar_colors:
                pathovar_colors[pathovar] = colors[len(pathovar_colors) % len(colors)]
            if country not in country_colors:
                country_colors[country] = colors[len(country_colors) % len(colors)]
        path_file = args.outdir / f"{safe_species}.pathovar_colorstrip.txt"
        country_file = args.outdir / f"{safe_species}.country_colorstrip.txt"
        text_file = args.outdir / f"{safe_species}.labels.txt"
        source_tree = args.trees / f"{safe_species}.treefile"
        if source_tree.exists():
            shutil.copyfile(source_tree, args.outdir / source_tree.name)
        with path_file.open("w", encoding="utf-8") as handle:
            handle.write("DATASET_COLORSTRIP\nSEPARATOR TAB\nDATASET_LABEL\tPathovar\nCOLOR\t#2f6f73\nLEGEND_TITLE\tPathovar\nLEGEND_SHAPES\t" + "\t".join("1" for _ in pathovar_colors) + "\nLEGEND_COLORS\t" + "\t".join(pathovar_colors.values()) + "\nLEGEND_LABELS\t" + "\t".join(pathovar_colors) + "\nDATA\n")
            for row in species_rows:
                value = clean(row.get("pathovar")) or "unassigned"
                handle.write(f"{row['tree_label']}\t{pathovar_colors[value]}\t{value}\n")
        with country_file.open("w", encoding="utf-8") as handle:
            handle.write("DATASET_COLORSTRIP\nSEPARATOR TAB\nDATASET_LABEL\tCountry\nCOLOR\t#7b6fbd\nLEGEND_TITLE\tCountry\nLEGEND_SHAPES\t" + "\t".join("1" for _ in country_colors) + "\nLEGEND_COLORS\t" + "\t".join(country_colors.values()) + "\nLEGEND_LABELS\t" + "\t".join(country_colors) + "\nDATA\n")
            for row in species_rows:
                value = clean(row.get("country")) or "unassigned"
                handle.write(f"{row['tree_label']}\t{country_colors[value]}\t{value}\n")
        with text_file.open("w", encoding="utf-8") as handle:
            handle.write("LABELS\nSEPARATOR TAB\nDATA\n")
            for row in species_rows:
                value = f"{row['ncppb']} | {row.get('pathovar') or 'unassigned'} | {row.get('country') or 'unassigned'} | {row['run_accession']}"
                handle.write(f"{row['tree_label']}\t{value}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("candidates")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=command_candidates)
    p = sub.add_parser("all-candidates")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=command_all_candidates)
    p = sub.add_parser("write-ena")
    p.add_argument("--candidates", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--script", type=Path, required=True)
    p.set_defaults(func=command_write_ena)
    p = sub.add_parser("select")
    p.add_argument("--candidates", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--rejected", type=Path, required=True)
    p.set_defaults(func=command_select)
    p = sub.add_parser("write-download")
    p.add_argument("--selected", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--script", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=4)
    p.set_defaults(func=command_write_download)
    p = sub.add_parser("write-snp")
    p.add_argument("--selected", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--script", type=Path, required=True)
    p.add_argument("--core-script", type=Path, required=True)
    p.add_argument("--no-finalize", action="store_true")
    p.set_defaults(func=command_write_snp)
    p = sub.add_parser("filter-species")
    p.add_argument("--selected", type=Path, required=True)
    p.add_argument("--species", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=command_filter_species)
    p = sub.add_parser("filter-core")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--min-complete", type=float, default=1.0)
    p.set_defaults(func=command_filter_core)
    p = sub.add_parser("distances")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out-prefix", type=Path, required=True)
    p.set_defaults(func=command_distances)
    p = sub.add_parser("fastp-summary")
    p.add_argument("--selected", type=Path, required=True)
    p.add_argument("--reports", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=command_fastp_summary)
    p = sub.add_parser("mapping-summary")
    p.add_argument("--selected", type=Path, required=True)
    p.add_argument("--mapping-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=command_mapping_summary)
    p = sub.add_parser("itol")
    p.add_argument("--selected", type=Path, required=True)
    p.add_argument("--trees", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.set_defaults(func=command_itol)
    return parser


if __name__ == "__main__":
    parser = build_parser()
    namespace = parser.parse_args()
    namespace.func(namespace)
