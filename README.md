# NCPPB Xanthomonas Genome Audit

This repository develops a reproducible workflow to audit how NCPPB *Xanthomonas* strains are represented in public NCBI genomic records.

The project asks whether a specific preserved NCPPB strain can be linked to public NCBI records such as BioSample, SRA, BioProject, Assembly, and Taxonomy.

## V2.1 open-source quick start

Supply the NCPPB HTML explicitly. No fixed HTML hash or historical V1 table is required:

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html /path/to/NCPPB_catalogue.html \
  --run-ncbi \
  --email your.email@example.org \
  --prompt-api-key \
  --outdir results/my_v2_1_run
```

The API key prompt is hidden and optional; press Enter to continue without a key. The key is never saved. HTML SHA-256 recording is disabled by default and is never used to accept or reject an uploaded file. Researchers who want a provenance fingerprint may opt in with `--record-input-hash`.

The primary final table is `supervisor_sequence_availability.tsv`. The run also produces auditable BioSample decisions, NCBI query execution records, linked Assembly/SRA/BioProject metadata, download commands, and one preferred phylogeny input per current NCPPB strain. See `docs/v2_1_open_source_cli.md`.

## Current Stage

The latest independently validated run is V2.1 in
`results/v2_1_pipeline/`. It contains 897 current catalogue rows, 533
confirmed BioSamples covering 360 strains, linked Assembly/SRA/BioProject
accessions, and a complete 552-pair V1 regression audit. All 1,376 planned
NCBI queries completed with zero truncation or request/link errors. See
`docs/v2_1_validation_report.md` and `docs/v2_1_architecture.md`.

V1 remains available as a historical high-recall baseline and
`results/v2_pipeline/` is retained as a diagnostic V2 run; neither is
overwritten by V2.1.

V2.1 now also writes reusable sequence-acquisition outputs:

- `sequence_resource_manifest.tsv` for BioSample/Assembly/SRA/BioProject resources and download commands;
- `phylogeny_input_manifest.tsv` for one preferred sequence source per NCPPB strain;
- `bioproject_mapping.tsv` to separate true sequence projects from annotation and ELink-only projects.

See `docs/sequence_retrieval_and_phylogeny_workflow.md` for the data-download and phylogeny-input architecture.

This repository now contains:

- the Week 1 NCPPB *Xanthomonas* master table;
- the Week 2 NCBI smoke test;
- the Week 3 BioSample identifier workflow for the first 30 strains;
- a full 898-strain BioSample review table;
- rejected-result analyses for improving BioSample search terms and query fields.

Current full-scale local outputs include:

- 898 NCPPB *Xanthomonas* strains in `data/processed/ncppb_xanthomonas_master.csv`;
- 612 accepted evidence rows covering 370 strains; after deduplication these represent 552 strain–BioSample pairs and 549 unique BioSample accessions;
- an 898-row strain review table with 352 confirmed BioSample matches, 40 manual-review cases, and 506 strains with no confirmed BioSample match yet;
- an 898-row supervisor sequence availability table that expands confirmed BioSamples to linked Assembly and SRA metadata;
- compact rejected-result analysis tables showing that legacy `[All Fields]` queries produced many non-target hits.

These results are still pre-final. Manual inspection of selected live NCBI BioSample pages is still in progress, so no final manually reviewed table is included yet.

Important provenance note: the current 898-strain `07_search_result_review_898.tsv`
checkpoint was derived from the historical high-recall `[All Fields]` harvest,
exact local strain-evidence filtering, and raw-candidate auditing. The
`strict_xanthomonas` consolidated wrapper is the improved full-rerun method
derived from rejected-result analysis; it has not yet been executed across all
898 strains. See `docs/technical_method_walkthrough_zh.md` for the distinction.

## Current Supervisor-Facing Outputs

The current interim deliverables are:

- `results/refactored_pipeline/07_search_result_review_898.tsv`
- `results/refactored_pipeline/11_supervisor_sequence_availability.tsv`
- `results/refactored_pipeline/11_supervisor_sequence_availability_summary.md`
- `results/refactored_pipeline/12_manual_review_queue.tsv`
- `results/refactored_pipeline/12_manual_review_queue_summary.md`
- `results/refactored_pipeline/13_final_audit_table.tsv`
- `results/refactored_pipeline/13_final_audit_summary.md`
- `results/refactored_pipeline/14_summary_figures/`

The sequence availability summary currently reports:

- 898 strain records reviewed;
- 370 strains with confirmed BioSample matches;
- 320 strains with linked public assemblies;
- 326 strains with linked SRA/raw-read records;
- 506 strains with no confirmed strain-level public sequence data in the current workflow;
- 40 strains flagged for manual review.

The sequence availability table also includes NCBI BioSample organism/taxid
metadata and `taxonomic_consistency_status` / `taxonomic_consistency_note`
columns to flag where NCPPB and NCBI names appear consistent or need review.

## Consolidated Workflow

Use the unnumbered wrapper for the deliverable workflow:

```bash
NCBI_EMAIL=YOUR_EMAIL@example.com python3 -B scripts/run_ncppb_audit.py \
  --outdir results/final_pipeline \
  --resume
```

For a small no-network check of the local catalogue and identifier-extraction stages:

```bash
python3 -B scripts/run_ncppb_audit.py \
  --steps other_references,identifiers \
  --outdir results/pilot_integrated_pipeline \
  --limit-strains 30
```

For sequence-metadata regeneration from an existing local NCBI cache, add
`--offline-cache-only`. The command will fail on a cache miss rather than
querying NCBI.

The wrapper writes these final-stage outputs:

- `other_references.tsv`
- `other_reference_identifiers.tsv`
- `biosample_raw.tsv`
- `biosample_matches.tsv`
- `biosample_review.tsv`
- `strain_search_review.tsv`
- `sequence_availability.tsv`
- `sequence_availability_summary.md`
- `manual_review_queue.tsv`
- `manual_review_queue_summary.md`
- `final_audit_table.tsv`
- `final_audit_summary.md`
- `summary_figures/`
- `validation_report.txt`

The current local supervisor workbook is:

- `outputs/ncppb_supervisor_package/NCPPB_Xanthomonas_sequence_availability_interim.xlsx`

To validate the current interim outputs without requiring all manual review to
be finished:

```bash
python3 -B scripts/24_validate_audit_outputs.py \
  --sequence-table results/refactored_pipeline/11_supervisor_sequence_availability.tsv \
  --manual-review-table results/refactored_pipeline/12_manual_review_queue.tsv \
  --final-table results/refactored_pipeline/13_final_audit_table.tsv
```

For the final frozen submission, add `--require-frozen`; this should only pass
after all manual-review decisions have been filled.

## Pipeline Logic

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
  -> build final audit draft, manual-review queue, and summary figures
```

## Documentation

Start with:

- `docs/technical_method_walkthrough_zh.md` (how the current results were technically derived, with worked strains)
- `docs/workflow_logic_and_reproducibility_zh.md` (Chinese step-by-step logic and exact replay guide)
- `docs/completion_audit.md`
- `docs/deliverable_manifest.md`
- `docs/final_pipeline_tasks.md`
- `docs/manual_review_protocol.md`
- `docs/submission_checklist.md`
- `docs/decision_rules.md`
- `docs/data_dictionary.md`
- `scripts/README.md`
