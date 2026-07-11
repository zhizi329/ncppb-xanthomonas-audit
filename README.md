# NCPPB Xanthomonas public-genome audit

Minimal reproducible repository for linking NCPPB *Xanthomonas* strains to NCBI BioSample, Assembly, SRA, BioProject and Taxonomy records.

## Current state

The only authoritative audit run is `runs/audit/2026-07-10_v2.1.1/`.

- 897 current catalogue records;
- 1,376/1,376 NCBI queries completed;
- 533 accepted BioSamples covering 360 strains;
- 262 preferred assemblies and 46 WGS-read fallbacks;
- 92 strains still require identity and/or taxonomy review;
- validated interim dataset, not a frozen final dataset.

Start with:

| File | Purpose |
|---|---|
| `supervisor_sequence_availability.tsv` | One-row-per-strain authoritative table |
| `phylogeny_input_manifest.tsv` | Preferred sequence source and readiness/block status |
| `manual_review_queue.tsv` | Outstanding human review |
| `run_summary.md` | Headline counts |
| `run_manifest.json` | Version, parameters and SHA-256 manifest |

Supporting tables are explained in `runs/audit/2026-07-10_v2.1.1/README.md` and `docs/results_catalog_zh.md`.

## Run and validate

The audit workflow uses the Python standard library.

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html /path/to/NCPPB_catalogue.html \
  --run-ncbi \
  --email your.email@example.org \
  --prompt-api-key \
  --outdir runs/audit/my_run
```

```bash
make hygiene
make test
make validate
```

`make validate-reviewed` should fail until all required pair-level review decisions are complete.

## Minimal repository layout

```text
ncppb_audit_v2/   current audit library
scripts/          current audit CLI, validation and phylogeny smoke tooling
tests/            V2.1 tests
data/             small catalogue baseline tables
runs/audit/       frozen authoritative audit run
runs/phylogeny/   accession/QC/tree-only smoke-test summary
docs/             concise method and output documentation
private_inputs/   local proposal and saved NCPPB HTML; ignored by Git
```

FASTQ, BAM, environments, caches, old workbooks and superseded runs are intentionally not retained. Public reads are reconstructed from accession, ENA URL and MD5 metadata.

## Phylogeny smoke test

`runs/phylogeny/2026-07-10_three-species-snp-smoke-summary/` retains only:

- 145 selected paired Illumina runs and ENA MD5 values;
- fastp QC for all 145 runs;
- mapping QC, SNP distances and IQ-TREE outputs for 37 *X. citri* strains;
- iTOL annotations.

Raw and processed reads were deleted because they are reproducible from the retained accession manifest.

## Key documentation

- `docs/v2_1_open_source_cli.md`
- `docs/v2_1_validation_report_zh.md`
- `docs/data_dictionary.md`
- `docs/manual_review_protocol.md`
- `docs/sequence_retrieval_and_phylogeny_workflow_zh.md`
- `docs/project_structure_zh.md`
