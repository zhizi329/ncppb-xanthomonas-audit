# Current BioSample Identifier Workflow Summary

This document summarises the current BioSample search workflow for the NCPPB
*Xanthomonas* audit. It is intended as a short overview of where the current
scripts are, how to run them, what they send to NCBI, what the outputs look
like, and what the current full-search results show.

This summary only covers the BioSample matching stage. It does not yet cover
linking accepted BioSamples to SRA, Assembly, BioProject, or other NCBI
datasets.

## Current Scripts

The current workflow is a four-script pipeline:

```text
08_html_to_other_references.py
  -> extracts NCPPB number and Other references text

09_extract_other_reference_identifiers.py
  -> extracts possible strain identifiers from Other references

10_harvest_biosample_raw.py
  -> searches NCBI BioSample and saves raw candidates

11_filter_biosample_raw.py
  -> classifies candidates into accepted matches and review/reject/no-data rows
```

The scripts are:

- [`scripts/08_html_to_other_references.py`](../scripts/08_html_to_other_references.py)
- [`scripts/09_extract_other_reference_identifiers.py`](../scripts/09_extract_other_reference_identifiers.py)
- [`scripts/10_harvest_biosample_raw.py`](../scripts/10_harvest_biosample_raw.py)
- [`scripts/11_filter_biosample_raw.py`](../scripts/11_filter_biosample_raw.py)

The main input table for the project is the cleaned NCPPB master table:

- [`data/processed/ncppb_xanthomonas_master.csv`](../data/processed/ncppb_xanthomonas_master.csv)

It currently contains 898 NCPPB *Xanthomonas* strain records.

## How To Run The Workflow

The commands below show the current BioSample workflow. Output paths can be
changed, but the required inputs and outputs should stay the same.

### Step 08: Extract Other References

```bash
python scripts/08_html_to_other_references.py \
  --input data/raw/ncppbresult.html \
  --output results/refactored_pipeline/01_other_references.tsv
```

Expected output:

- [`results/refactored_pipeline/01_other_references.tsv`](../results/refactored_pipeline/01_other_references.tsv)

This table contains one row per NCPPB strain, with the NCPPB number and the
free-text `Other references` field from the saved NCPPB HTML.

### Step 09: Extract Identifier Candidates

```bash
python scripts/09_extract_other_reference_identifiers.py \
  --input results/refactored_pipeline/01_other_references.tsv \
  --output results/refactored_pipeline/02_other_reference_identifiers.tsv
```

Expected output:

- [`results/refactored_pipeline/02_other_reference_identifiers.tsv`](../results/refactored_pipeline/02_other_reference_identifiers.tsv)

This table contains possible identifiers extracted from the `Other references`
text. Important output columns include:

```text
ncppb_number
matched_text
normalized_identifier
prefix
suffix
rule_name
confidence
include_for_search
biosample_query
context
```

The script is deliberately broad. It is designed to avoid missing possible
identifiers, even if this creates some extra false-positive search terms.

### Step 10: Search NCBI BioSample

```bash
python scripts/10_harvest_biosample_raw.py \
  --input results/refactored_pipeline/02_other_reference_identifiers.tsv \
  --output results/refactored_pipeline/03_biosample_raw_all.tsv \
  --api-key "$NCBI_API_KEY"
```

For a smaller test run, use:

```bash
python scripts/10_harvest_biosample_raw.py \
  --input results/refactored_pipeline/02_other_reference_identifiers.tsv \
  --output results/refactored_pipeline/03_biosample_raw_first30.tsv \
  --limit-strains 30 \
  --api-key "$NCBI_API_KEY"
```

Expected output:

- `results/refactored_pipeline/03_biosample_raw_all.tsv`

This file is a raw candidate table. It is not a final result table. A row in
this file only means that NCBI BioSample returned a candidate record for one
of the search terms.

### Step 11: Classify BioSample Evidence

```bash
python scripts/11_filter_biosample_raw.py \
  --raw-input results/refactored_pipeline/03_biosample_raw_all.tsv \
  --identifiers results/refactored_pipeline/02_other_reference_identifiers.tsv \
  --matches-output results/refactored_pipeline/04_biosample_matches_all.tsv \
  --review-output results/refactored_pipeline/04_biosample_review_all.tsv
```

Expected outputs:

- [`results/refactored_pipeline/04_biosample_matches_all.tsv`](../results/refactored_pipeline/04_biosample_matches_all.tsv)
- `results/refactored_pipeline/04_biosample_review_all.tsv`

The matches table contains accepted BioSample records. The review table
contains rows that were not accepted automatically, including weak matches,
clear false positives, conflicting identifiers, and no-hit rows.

## What Query Is Sent To NCBI?

The workflow searches NCBI BioSample only.

It does not search by broad species names, pathovar names, host names, or
country names. These terms created many taxon-level hits during the earlier
Week 2 search, but they did not prove strain identity.

The current search uses strain-level identifiers:

```text
NCPPB number
identifier-like terms extracted from Other references
```

Examples:

```text
NCPPB 101
ICMP 204
LMG 673
DSM 18958
NBC 5720
```

The actual NCBI query uses `[All Fields]`. For example:

```text
NCPPB 101 -> NCPPB[All Fields] AND 101[All Fields]
ICMP 204  -> ICMP[All Fields] AND 204[All Fields]
LMG 673   -> LMG[All Fields] AND 673[All Fields]
```

This is intentionally broader than an exact phrase search. It can find records
where the same identifier is written in different ways, for example:

```text
NCPPB 101
NCPPB101
NCPPB:101
NCPPB-101
NCPPB_101
```

The disadvantage is that `[All Fields]` can also return false positives,
especially for short local or donor identifiers such as `B 67` or `PC 5`.
For this reason, script `10` only harvests candidates. Script `11` then checks
the returned BioSample metadata and accepts only records with strong
strain-level evidence.

## Example Output

An accepted BioSample match looks like this:

| NCPPB strain | BioSample accession | Example title | Accepted evidence |
|---|---|---|---|
| NCPPB 45 | SAMN36346970 | Genome sequencing of Xcc WHRI 6379 (NCPPB 45) | Target NCPPB number appears in BioSample metadata |

This is accepted because the BioSample metadata contains the exact target
strain identifier, `NCPPB 45`.

A weak candidate is not accepted if it only has a related taxonomic name but
no exact strain identifier. For example, a BioSample labelled only as
*Xanthomonas campestris* is not enough to prove that it represents a specific
NCPPB strain.

## First 30 Strain Validation

The first 30 strains were used as a validation set before applying the workflow
to all 898 strains.

For these 30 strains:

| Result | Count |
|---|---:|
| Planned BioSample queries | 44 |
| NCPPB-number queries | 30 |
| Other-reference identifier queries | 14 |
| Raw BioSample candidate rows | 251 |
| Accepted BioSample rows | 11 |
| Accepted NCPPB strains | 10 |
| Rows outside the accepted table | 240 |

The first-30 result is:

| NCPPB strain | Current BioSample result |
|---|---|
| NCPPB 45 | Accepted: SAMN36346970 |
| NCPPB 101 | Accepted: SAMN22555467 |
| NCPPB 109 | No confirmed BioSample match |
| NCPPB 113 | Accepted: SAMN42178446 |
| NCPPB 151 | Accepted: SAMN56511362 |
| NCPPB 174 | No confirmed BioSample match |
| NCPPB 181 | No confirmed BioSample match |
| NCPPB 182 | No confirmed BioSample match |
| NCPPB 184 | No confirmed BioSample match |
| NCPPB 185 | No confirmed BioSample match |
| NCPPB 186 | No confirmed BioSample match |
| NCPPB 187 | No confirmed BioSample match |
| NCPPB 195 | No confirmed BioSample match |
| NCPPB 196 | No confirmed BioSample match |
| NCPPB 200 | No confirmed BioSample match |
| NCPPB 205 | No confirmed BioSample match |
| NCPPB 206 | Accepted: SAMN00991256; SAMN36357966 |
| NCPPB 208 | No confirmed BioSample match |
| NCPPB 210 | No confirmed BioSample match |
| NCPPB 211 | Accepted: SAMN13783128 |
| NCPPB 212 | No confirmed BioSample match |
| NCPPB 220 | Accepted: SAMN03262509 |
| NCPPB 226 | Accepted: SAMN13783184 |
| NCPPB 230 | Accepted: SAMN40354569 |
| NCPPB 232 | Accepted: SAMEA6962647 |
| NCPPB 240 | No confirmed BioSample match |
| NCPPB 241 | No confirmed BioSample match |
| NCPPB 243 | No confirmed BioSample match |
| NCPPB 273 | No confirmed BioSample match |
| NCPPB 279 | No confirmed BioSample match |

The narrower identifier-based workflow found the same 10 confirmed strains as
the earlier broad keyword search, but with a cleaner and more controlled
search strategy.

## Full 898-Strain BioSample Results

The same BioSample workflow was then applied to all 898 NCPPB *Xanthomonas*
strain records.

| Result | Count |
|---|---:|
| NCPPB strains searched | 898 |
| Identifier extraction rows from script 09 | 1,657 |
| Identifiers included for BioSample search | 1,464 |
| Raw BioSample candidate rows from script 10 | 33,829 |
| Accepted BioSample match rows from script 11 | 612 |
| Unique NCPPB strains with accepted BioSample matches | 370 |
| NCPPB strains without confirmed BioSample matches | 528 |

This means that 370 of 898 NCPPB *Xanthomonas* strains currently have a
confirmed BioSample match under the strict identifier-based rules.

The remaining 528 strains should be described as having no confirmed
strain-level BioSample match under the current workflow. This does not prove
that no public sequence data exist. It means that the current automated
BioSample search did not find enough strain-level metadata evidence to accept
a match.

## Evidence Used For Accepted Matches

Accepted matches required strong strain-level evidence. Species or pathovar
names alone were not accepted.

| Evidence type | Accepted rows | Unique strains |
|---|---:|---:|
| Target NCPPB number found in BioSample metadata | 425 | 296 |
| Other reference identifier found in BioSample metadata | 187 | 101 |

Some strains were supported by both evidence types, so the unique-strain
counts are not additive.

## Review And Rejected Results

The non-accepted output is:

- `results/refactored_pipeline/04_biosample_review_all.tsv`

This table still needs further processing. It should not be interpreted as
"all rows need manual review". Most rows are clear false positives or no-hit
rows. The useful point is that the table shows where the current search
strategy creates noise, and which weak candidates may need manual checking.

Current non-accepted row summary:

| Category | Rows | Interpretation |
|---|---:|---|
| Non-*Xanthomonas* organism | 31,827 | Clear false positives, mostly caused by broad `[All Fields]` searches with short identifiers |
| No BioSample candidate found | 1,242 | Query returned no BioSample records |
| Conflicting NCPPB number | 79 | Candidate contains a different NCPPB number, so it should not be accepted |
| Taxon-level only | 69 | Related *Xanthomonas* record, but no exact strain identifier |

The most useful manual-review group is the taxon-level-only group. These rows
may be biologically related, but they cannot be counted as confirmed matches
unless stronger strain-level evidence can be found.

The rejected table may still contain useful information for improving the
workflow. In particular, it can help identify:

- short local identifiers that create many false positives;
- repeated prefixes that should be excluded from future searches;
- cases where a query finds another NCPPB strain instead of the target strain;
- *Xanthomonas* taxon-level records that may need curator checking.

## Problems Found So Far

The main problem is false positives from broad `[All Fields]` queries.

Using `[All Fields]` is helpful because NCBI metadata are not formatted
consistently. The same identifier may appear in a title, strain field,
isolate field, culture collection field, or free-text attribute. However, this
also means that short identifiers can match many unrelated records.

Examples of riskier identifiers include short local or donor codes such as:

```text
B 67
PC 5
M 9
```

These can return many records that are not *Xanthomonas*. The current workflow
controls this by not accepting a BioSample unless the returned metadata
contains strong strain-level evidence.

There is also a possible false-negative problem. Some real public BioSample
records may not contain the NCPPB number or any known equivalent identifier.
Those records would not be accepted by the current strict rules.

## Current Project Status

The BioSample identifier search is working for the main purpose of this stage:
it can search all 898 NCPPB *Xanthomonas* strain records and produce a strict
set of accepted BioSample matches.

Current completed work:

- NCPPB master table prepared for 898 strains.
- `Other references` extracted from the saved NCPPB HTML.
- Identifier candidates extracted from free text.
- BioSample search completed for all 898 strains.
- Accepted BioSample matches separated from weak, rejected, and no-data rows.

Current work still to do:

- Process the rejected/review table more carefully to identify useful patterns.
- Manually check the taxon-level-only and other weak candidates.
- Decide whether any short local or donor identifiers should be excluded from
  future full searches.
- Produce a final one-row-per-strain BioSample audit table.

At this stage, the BioSample search workflow is usable, but the rejected result
table still needs interpretation before the BioSample stage can be considered
fully finished.
