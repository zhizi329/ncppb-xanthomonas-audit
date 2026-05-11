# Week 2 Plan: Search Terms and NCBI Smoke Test

## Main Goal

Do a small test on 5-10 strains to check whether the NCBI query and matching logic works.

## Why This Matters

A full collection-wide search is only useful after the matching rules are tested. Week 2 is about proving that the workflow can retrieve useful metadata and store evidence clearly.

## Tasks

1. Generate search terms from the NCPPB master table.
2. Choose 5-10 representative strains.
3. Query NCBI BioSample, Assembly, SRA, and Taxonomy using Biopython Entrez.
4. Save candidate records to a TSV so GitHub can preview the results as a table.
5. Manually compare several results with the NCBI website.
6. Update the decision rules.

## Target Outputs

```text
data/interim/search_terms.tsv
results/week2_ncbi_smoke_test.tsv
docs/week2_smoke_test_notes.md
docs/decision_rules.md
```

## Success Criteria

By the end of Week 2, you should be able to classify a candidate NCBI result as:

- strong strain match;
- probable strain match;
- taxon-level only;
- ambiguous;
- no public data found.
