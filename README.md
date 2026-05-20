# NCPPB Xanthomonas Genome Audit

This project develops a reproducible workflow to audit how NCPPB Xanthomonas strains are represented in public NCBI genomic records.

The project asks whether a specific preserved NCPPB strain can be linked to NCBI records such as BioSample, SRA, Assembly, and Taxonomy.

## Current Stage

This repository now contains:

- the Week 1 NCPPB *Xanthomonas* master table;
- the Week 2 NCBI smoke test;
- the Week 3 BioSample identifier workflow for the first 30 strains.

The current BioSample identifier workflow confirms public BioSample data for 10 of the first 30 strains. This matches the earlier broad keyword search result, but uses fewer and cleaner search terms.

## Project Logic

```text
NCPPB catalogue
  -> clean strain master table
  -> extract Other references
  -> extract identifier-style search terms
  -> BioSample raw retrieval
  -> evidence-based BioSample filtering
  -> accepted / review / reject outputs
```

## Week 1 and Week 2 Commands

```bash
# Browser results of NCPPB page as HTML:
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

## Week 3 BioSample Identifier Workflow

The first 30 strain review package is in:

```text
review_packages/first30_biosample_identifier_workflow/
```

Run the workflow:

```bash
python review_packages/first30_biosample_identifier_workflow/scripts/08_html_to_other_references.py \
  --input data/raw/ncppbresult.html \
  --output review_packages/first30_biosample_identifier_workflow/data/01_other_references_first30.tsv

python review_packages/first30_biosample_identifier_workflow/scripts/09_extract_other_reference_identifiers.py \
  --input review_packages/first30_biosample_identifier_workflow/data/01_other_references_first30.tsv \
  --output review_packages/first30_biosample_identifier_workflow/data/02_other_reference_identifiers_first30.tsv

python review_packages/first30_biosample_identifier_workflow/scripts/10_harvest_biosample_raw.py \
  --input review_packages/first30_biosample_identifier_workflow/data/02_other_reference_identifiers_first30.tsv \
  --output review_packages/first30_biosample_identifier_workflow/data/04_biosample_raw_first30_live.tsv \
  --limit-strains 30 \
  --api-key "$NCBI_API_KEY"

python review_packages/first30_biosample_identifier_workflow/scripts/11_filter_biosample_raw.py \
  --raw-input review_packages/first30_biosample_identifier_workflow/data/04_biosample_raw_first30_live.tsv \
  --identifiers review_packages/first30_biosample_identifier_workflow/data/02_other_reference_identifiers_first30.tsv \
  --matches-output review_packages/first30_biosample_identifier_workflow/data/05_biosample_matches_first30_live.tsv \
  --review-output review_packages/first30_biosample_identifier_workflow/data/06_biosample_review_first30_live.tsv
```
