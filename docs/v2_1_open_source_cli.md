# V2.1.1 Open-Source Command-Line Workflow

## Complete run from a user-supplied HTML file

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html /absolute/path/NCPPB_catalogue.html \
  --run-ncbi \
  --email researcher@example.org \
  --prompt-api-key \
  --outdir runs/audit/my_v2_1_run
```

The API-key prompt is hidden. Press Enter to continue without a key. The key is not written to output tables, cache keys or the run manifest. Non-interactive environments may use `NCBI_EMAIL` and `NCBI_API_KEY` environment variables.

The HTML path is mandatory. No bundled or author-local HTML is selected implicitly. No fixed HTML hash is checked. `--record-input-hash` is an optional provenance feature and never rejects an input.

## Cache freshness

Cache policy is explicit and written to `run_manifest.json`:

```bash
# Force a completely fresh NCBI retrieval
python3 scripts/run_ncppb_audit_v2.py ... --refresh-cache

# Reuse only responses no older than seven days
python3 scripts/run_ncppb_audit_v2.py ... --cache-max-age-hours 168

# Reproduce from cache without network access; fail on a missing or expired item
python3 scripts/run_ncppb_audit_v2.py ... --offline-cache-only
```

`--refresh-cache` and `--offline-cache-only` cannot be combined. If `--reuse-candidates` is requested, a refresh bypasses the saved candidate table; a maximum age also applies to that table.

## Manual-review round trip

`manual_review_candidates.tsv` contains one row per NCPPB--BioSample pair. Copy it outside the output directory, fill `reviewer_decision` with one of the following values, and rerun with `--review-decisions`:

- `approve_for_downstream`: retain/accept the pair and explicitly permit sequence use despite the flagged identity/taxonomy issue;
- `reject_match`: remove the pair from confirmed/provisional use;
- `keep_pending`: leave the automatic result unresolved.

```bash
python3 scripts/run_ncppb_audit_v2.py ... \
  --review-decisions decisions/reviewed_biosamples.tsv \
  --require-reviewed
```

The automatic result is preserved in `original_decision`; reviewer decision and notes are written to `biosample_match_decisions.tsv`. `--require-reviewed` fails if any pair remains unresolved.

## Resource accessions missed by BioSample ELink

An accession found by PhytoBacExplorer, a paper or direct NCBI search can be supplied with `--resource-seed-table`. Each seed must identify an already accepted NCPPB--BioSample pair and use `verification_status=verified_against_biosample`. Invalid accessions, unaccepted BioSamples and unverified rows stop the run. Seeded links remain marked `link_method=verified_external_seed` with their provenance; they do not bypass the taxonomy safety gate.

## Optional historical regression inputs

Historical files are not required for a new run. The repository retains the 898-row catalogue baseline, but no longer maintains the superseded V1 sequence-output directory. Without a complete historical baseline, current rows receive `current_snapshot_no_v1_baseline` and regression tables contain headers only. The frozen V2.1.1 run retains the completed historical regression evidence.

## Local parsing and query-plan only

Omit `--run-ncbi`:

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html /absolute/path/NCPPB_catalogue.html \
  --outdir runs/audit/local_plan
```

## Output groups

### Catalogue and identifier intermediates

- `catalogue_strains.tsv`
- `other_reference_clauses.tsv`
- `catalogue_snapshot_diff.tsv`
- `strain_identifiers.tsv`
- `parser_review_queue.tsv`
- `identifier_review_queue.tsv`
- `ncbi_query_plan.tsv`

### NCBI execution and evidence intermediates

- `ncbi_query_execution.tsv`
- `biosample_candidates.tsv`
- `biosample_match_decisions.tsv`
- `linked_ncbi_records.tsv`
- `manual_review_queue.tsv`
- `manual_review_candidates.tsv`

### Final research-facing outputs

- `explorer_strain_catalogue.tsv` (one row per current/baseline-union strain, with numeric NCBI counts)
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
python3 scripts/validate_ncppb_audit_v2.py --outdir runs/audit/my_v2_1_run
```

Project-specific snapshot regression:

```bash
python3 scripts/validate_ncppb_audit_v2.py \
  --outdir runs/audit/2026-07-10_v2.1.1 \
  --expected-current-records 897 \
  --expected-missing-number "NCPPB 4416"
```

Validation checks query coverage and truncation, remote errors, accepted-evidence strength, confirmed BioSample resource coverage, taxonomy/pathovar eligibility, phylogeny-resource selection and BioProject provenance classification. Add `--require-reviewed` for a frozen result.

## Count definitions

Counts must distinguish strains, evidence rows and accessions:

- V1: 370 strains with at least one confirmed BioSample, 612 accepted evidence rows, 552 strain–BioSample pairs and 549 unique BioSample accessions;
- V2.1: 360 strains with at least one confirmed BioSample and 533 confirmed strain–BioSample pairs/unique BioSample accessions.

The supervisor question “what sequence data are available for each strain?” should be answered from the one-row-per-strain table, not from evidence-row counts.

In `explorer_strain_catalogue.tsv`, `ncbi_assembly_count`, `ncbi_sra_run_count`, `ncbi_bioproject_count` and `ncbi_record_match_count` count all identity-confirmed linked records, including taxonomy-blocked evidence. The parallel `ncbi_eligible_*` columns count only resources currently permitted for downstream analysis. Thus a strain can correctly have a non-zero NCBI match count and zero eligible sequence resources.
