# V2.1 GitHub Release File Manifest

## Included scope

### Entry point and package

- `scripts/run_ncppb_audit_v2.py`
- `scripts/validate_ncppb_audit_v2.py`
- `scripts/build_sequence_retrieval_manifest_v2.py`
- `ncppb_audit_v2/`
- `tests/test_ncppb_audit_v2.py`

### English documentation

- `README.md`
- `docs/data_dictionary.md`
- `docs/v2_1_architecture.md`
- `docs/v2_1_open_source_cli.md`
- `docs/sequence_retrieval_and_phylogeny_workflow.md`
- `docs/v2_1_validation_report.md`
- `docs/supervisor_progress_update_v2_1.md`
- `docs/v2_1_release_manifest.md`

### Validated result set

- `results/v2_1_pipeline/`

The result directory contains the one-row-per-strain supervisor table, all required intermediate evidence files, query execution audit, sequence resource and phylogeny manifests, BioProject provenance classification, V1 regression tables, summaries and a credential-free run manifest.

## Explicit exclusions

- user-supplied or browser-saved HTML files;
- `.cache/` and all NCBI response cache files;
- NCBI API keys, email credentials and shell environment files;
- local `outputs/` artifacts;
- diagnostic `results/v2_pipeline/`;
- unrelated V1/refactored-pipeline working files;
- Chinese-language project notes and local handoff documents;
- unrelated modified or untracked worktree files.

## Release checks

- all uploaded documentation and result schemas are English;
- no uploaded result contains the author's absolute local source path;
- HTML hash recording is disabled in the published run;
- no file exceeds GitHub's 100 MB single-file limit;
- 69 automated tests pass;
- the generic and project-specific validators pass.
