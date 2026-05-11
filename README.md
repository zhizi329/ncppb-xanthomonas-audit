# NCPPB Xanthomonas Genome Audit

This project develops a reproducible workflow to audit how NCPPB Xanthomonas strains are represented in public NCBI genomic records.

The project asks whether a specific preserved NCPPB strain can be linked to NCBI records such as BioSample, SRA, Assembly, and Taxonomy.

## Current Stage

This repository is currently set up for week 1 work:

1. Build the NCPPB Xanthomonas master table.
2. Generate traceable search terms for each strain.

## Project Logic

```text
NCPPB catalogue
  -> clean strain master table
  -> search dictionary
  -> NCBI metadata retrieval
  -> evidence-based matching
  -> audit categories and summary figures
```

## Commands

```bash

# browser results of NCPPB page as HTML:
python scripts/00_extract_ncppb_html.py \
  --input data/raw/ncppbresult.html \
  --output data/raw/ncppb_catalogue.csv

python scripts/01_clean_ncppb_catalogue.py \
  --input data/raw/ncppb_catalogue.csv \
  --output data/processed/ncppb_xanthomonas_master.csv

python scripts/02_make_search_terms.py \
  --input data/processed/ncppb_xanthomonas_master.csv \
  --output data/interim/search_terms.tsv

python scripts/03_ncbi_smoke_test.py \
  --input data/interim/search_terms.tsv \
  --limit-strains 10 \
  --email YOUR_EMAIL@example.com \
  --output results/week2_ncbi_smoke_test.tsv
```
