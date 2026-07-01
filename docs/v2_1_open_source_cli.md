# V2.1 Open-Source Command-Line Workflow

## Complete run from a user-supplied HTML file

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html /absolute/path/NCPPB_catalogue.html \
  --run-ncbi \
  --email researcher@example.org \
  --prompt-api-key \
  --outdir results/my_v2_1_run
```

The API-key prompt is hidden. Press Enter to continue without a key. The key is not written to output tables, cache keys or the run manifest. Non-interactive environments may use `NCBI_EMAIL` and `NCBI_API_KEY` environment variables.

The HTML path is mandatory. No bundled or author-local HTML is selected implicitly. No fixed HTML hash is checked. `--record-input-hash` is an optional provenance feature and never rejects an input.

## Optional V1 regression inputs

V1 files are not required for a new run. Project-specific regression can be enabled with:

```bash
  --v1-master data/processed/ncppb_xanthomonas_master.csv \
  --v1-sequence-table results/refactored_pipeline/11_supervisor_sequence_availability.tsv
```

Without a baseline, current catalogue rows receive `current_snapshot_no_v1_baseline` and the V1 regression tables contain headers but no historical pairs.

## Local parsing and query-plan only

Omit `--run-ncbi`:

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html /absolute/path/NCPPB_catalogue.html \
  --outdir results/local_plan
```

## Output groups

### Catalogue and identifier intermediates

- `catalogue_strains.tsv`
- `other_reference_clauses.tsv`
- `catalogue_snapshot_diff.tsv`
- `strain_identifiers.tsv`
- `parser_review_queue.tsv`
- `ncbi_query_plan.tsv`

### NCBI execution and evidence intermediates

- `ncbi_query_execution.tsv`
- `biosample_candidates.tsv`
- `biosample_match_decisions.tsv`
- `linked_ncbi_records.tsv`
- `manual_review_queue.tsv`

### Final research-facing outputs

- `supervisor_sequence_availability.tsv`
- `sequence_resource_manifest.tsv`
- `phylogeny_input_manifest.tsv`
- `bioproject_mapping.tsv`

### Optional V1 comparison outputs

- `v1_v2_comparison.tsv`
- `v1_regression_recall_audit.tsv`
- `v1_v2_accession_changes.tsv`

## Validation

Generic open-source run:

```bash
python3 scripts/validate_ncppb_audit_v2.py --outdir results/my_v2_1_run
```

Project-specific snapshot regression:

```bash
python3 scripts/validate_ncppb_audit_v2.py \
  --outdir results/v2_1_pipeline \
  --expected-current-records 897 \
  --expected-missing-number "NCPPB 4416"
```

Validation checks query coverage and truncation, remote errors, accepted-evidence strength, confirmed BioSample resource coverage, phylogeny-resource selection and BioProject provenance classification.

## Count definitions

Counts must distinguish strains, evidence rows and accessions:

- V1: 370 strains with at least one confirmed BioSample, 612 accepted evidence rows, 552 strain–BioSample pairs and 549 unique BioSample accessions;
- V2.1: 360 strains with at least one confirmed BioSample and 533 confirmed strain–BioSample pairs/unique BioSample accessions.

The supervisor question “what sequence data are available for each strain?” should be answered from the one-row-per-strain table, not from evidence-row counts.
