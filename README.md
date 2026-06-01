# NCPPB Xanthomonas Genome Audit

This repository develops a reproducible workflow to audit how NCPPB *Xanthomonas* strains are represented in public NCBI genomic records.

The project asks whether a specific preserved NCPPB strain can be linked to public NCBI records such as BioSample, SRA, BioProject, Assembly, and Taxonomy.

## Current Stage

This repository now contains:

- the Week 1 NCPPB *Xanthomonas* master table;
- the Week 2 NCBI smoke test;
- the Week 3 BioSample identifier workflow for the first 30 strains;
- a full 898-strain BioSample review table;
- rejected-result analyses for improving BioSample search terms and query fields.

Current full-scale local outputs include:

- 898 NCPPB *Xanthomonas* strains in `data/processed/ncppb_xanthomonas_master.csv`;
- 612 accepted BioSample rows covering 370 strains;
- an 898-row strain review table with 352 confirmed BioSample matches, 40 manual-review cases, and 506 strains with no confirmed BioSample match yet;
- compact rejected-result analysis tables showing that legacy `[All Fields]` queries produced many non-target hits.

These results are still pre-final. The assisted manual review table is a triage table, not the final human-reviewed result set.

## Main Workflow

```text
Saved NCPPB catalogue HTML/CSV
  -> clean NCPPB Xanthomonas master table
  -> extract Other references
  -> extract identifier candidates
  -> build BioSample query profiles
  -> harvest BioSample raw candidates
  -> filter with local strain evidence
  -> audit rejected/raw candidates for query optimisation
  -> build strain-level BioSample review table
  -> expand confirmed BioSamples to linked NCBI records
```

## Core BioSample Pipeline

```bash
python scripts/08_html_to_other_references.py \
  --input data/raw/ncppbresult.html \
  --output results/refactored_pipeline/01_other_references.tsv

python scripts/09_extract_other_reference_identifiers.py \
  --input results/refactored_pipeline/01_other_references.tsv \
  --output results/refactored_pipeline/02_other_reference_identifiers.tsv

python scripts/10_harvest_biosample_raw.py \
  --input results/refactored_pipeline/02_other_reference_identifiers.tsv \
  --output results/refactored_pipeline/03_biosample_raw_all.tsv \
  --query-profile strict_xanthomonas \
  --target-organism Xanthomonas \
  --cache-dir .cache/ncbi/biosample \
  --resume \
  --email YOUR_EMAIL@example.com

python scripts/11_filter_biosample_raw.py \
  --raw-input results/refactored_pipeline/03_biosample_raw_all.tsv \
  --identifiers results/refactored_pipeline/02_other_reference_identifiers.tsv \
  --matches-output results/refactored_pipeline/04_biosample_matches_all.tsv \
  --review-output results/refactored_pipeline/04_biosample_review_all.tsv
```


## Documentation

Start with:

- `docs/github_progress_report_en.md`
- `docs/current_progress_rejected_biosample_analysis.md`
- `docs/search_result_review_898_notes.md`
- `docs/current_workflow_deep_dive_and_completion_plan.md`
- `docs/biosample_raw_data_audit_strategy.md`
- `docs/ncppb_audit_framework_design.md`


