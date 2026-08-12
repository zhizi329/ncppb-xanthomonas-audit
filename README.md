# NCPPB Xanthomonas public-genome audit

Reproducible project materials for linking NCPPB *Xanthomonas* catalogue records to NCBI BioSample, Assembly, SRA and BioProject resources.

## Submission dataset

The frozen record-level table used for the project report is:

`runs/audit/2026-07-24_v3-922/results_availability.tsv`

It contains 922 NCPPB records returned by the frozen catalogue search: 892 records with a current *Xanthomonas* name and 30 scope-retained records whose current name is outside the genus. Among the 892-record main cohort, 375 records have an accepted BioSample link and 346 have an accepted Assembly or WGS resource under the frozen rules.

The table distinguishes record scope, identifier evidence, sequence availability, taxonomy review, preferred resources and downstream readiness. A missing accepted link means that no acceptable relationship was confirmed under the frozen identifiers and rules; it does not prove that a strain has never been sequenced.

## Repository structure

```text
ncppb_audit_v2/   audit library retained for reproducibility
scripts/          audit, validation and recovery tools
tests/            workflow tests
data/             catalogue baseline and processed tables
runs/audit/       frozen and archived record-level audit outputs
runs/phylogeny/   accession, QC and smoke-test tree evidence
docs/             method, field and review documentation
```

`runs/audit/2026-07-10_v2.1.1/` is an earlier validated 897-record run retained as provenance. It is not the submission denominator.

Public FASTA and FASTQ payloads are not stored in this repository. They can be recovered from the retained accessions and sequence manifests.

## Validation

The retained V2.1 workflow uses the Python standard library:

```bash
make hygiene
make test
make validate
```

Methods, fields and manual-review rules are described in:

- `docs/v2_1_open_source_cli.md`
- `docs/v2_1_validation_report.md`
- `docs/data_dictionary.md`
- `docs/decision_rules.md`
- `docs/manual_review_protocol.md`
