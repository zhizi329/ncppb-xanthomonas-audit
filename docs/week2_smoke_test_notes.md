# Week 2 NCBI Smoke Test Notes

## Run

The Week 2 smoke test queried NCBI metadata only. It did not download sequence data.

```bash
python scripts/03_ncbi_smoke_test.py \
  --input data/interim/search_terms.tsv \
  --limit-strains 10 \
  --email 0329zhizi@gmail.com \
  --timeout 30 \
  --output results/week2_ncbi_smoke_test.tsv
```

## Output

```text
results/week2_ncbi_smoke_test.tsv
```

The output is TSV rather than CSV so GitHub can preview it as a table.

## Pilot Strains

```text
NCPPB 45
NCPPB 101
NCPPB 109
NCPPB 113
NCPPB 151
NCPPB 174
NCPPB 181
NCPPB 182
NCPPB 184
NCPPB 185
```

## Summary

| Metric | Value |
|---|---:|
| Search result rows | 256 |
| Rows with at least one returned NCBI ID | 47 |
| Rows with status `ok` | 256 |
| Rows with status `error` | 0 |
| Total BioSample IDs returned | 35 |
| Total Assembly IDs returned | 34 |
| Total SRA IDs returned | 29 |
| Total Taxonomy IDs returned | 6 |

All 10 pilot NCPPB strains had at least one returned NCBI ID in BioSample, Assembly, SRA, or Taxonomy.

## Interpretation

The smoke test confirms that the Week 2 search-term workflow can retrieve NCBI metadata IDs. These IDs are candidate records only. Week 3 should fetch richer metadata fields and classify each candidate using the evidence levels in `docs/decision_rules.md`.
