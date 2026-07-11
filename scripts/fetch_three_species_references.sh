#!/usr/bin/env bash
set -euo pipefail

OUTDIR=${1:?usage: fetch_three_species_references.sh OUTDIR}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export PATH="$ROOT/.cache/conda-envs/srr_phylo_snp/bin:$PATH"
mkdir -p "$OUTDIR"

download_reference() {
  local accession=$1
  local label=$2
  local zip="$OUTDIR/${accession}.zip"
  local unpack="$OUTDIR/${accession}"
  local fasta="$OUTDIR/${label}.fna"

  if [[ ! -s "$fasta" ]]; then
    if [[ -s "$zip" ]] && ! unzip -tq "$zip" >/dev/null 2>&1; then
      rm -f "$zip"
    fi
    if [[ ! -s "$zip" ]]; then
      curl --http1.1 -fL --retry 5 --retry-delay 5 -o "$zip" \
        "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/${accession}/download?include_annotation_type=GENOME_FASTA"
    fi
    mkdir -p "$unpack"
    unzip -oq "$zip" -d "$unpack"
    find "$unpack/ncbi_dataset/data" -name '*_genomic.fna' -type f -print -quit | xargs -I{} cp {} "$fasta"
  fi
  samtools faidx "$fasta"
  bwa index "$fasta"
}

download_reference GCF_000007145.1 Xanthomonas_campestris
download_reference GCF_000007165.1 Xanthomonas_citri
download_reference GCF_000009165.1 Xanthomonas_euvesicatoria

printf 'Reference FASTA files:\n'
ls -lh "$OUTDIR"/*.fna
