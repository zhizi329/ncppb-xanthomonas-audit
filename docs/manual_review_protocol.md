# V2.1.1 manual review

The current run has 92 strain-level review rows and 112 strain-BioSample candidate pairs.

Use `runs/audit/2026-07-10_v2.1.1/manual_review_candidates.tsv` as evidence. Create a decision TSV with:

```text
ncppb_number	biosample_accession	reviewer_decision	reviewer_notes
```

Allowed decisions:

- `approve_for_downstream`: accept and permit sequence use;
- `reject_match`: reject the pair;
- `keep_pending`: leave unresolved.

Review P1 before P2. Check structured strain/culture-collection fields, conflicting NCPPB numbers, organism lineage, pathovar and mutant/derivative status.

Never edit a frozen run in place. Create a new run:

```bash
python3 scripts/run_ncppb_audit_v2.py \
  --catalogue-html "private_inputs/National Collection of Plant Pathogenic Bacteria Catalogue.html" \
  --run-ncbi \
  --review-decisions decisions.tsv \
  --require-reviewed \
  --outdir runs/audit/YYYY-MM-DD_v2.1.1-reviewed
```

Use the normal cache or a newly generated one. `--require-reviewed` fails while any pair remains unresolved. Validate the new output before using final counts.
