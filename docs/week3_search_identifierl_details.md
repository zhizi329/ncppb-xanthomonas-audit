# BioSample Identifier Workflow Report

## Short Summary

The current workflow includes scripts `08` to `11`:

```text
08 saved NCPPB HTML
  -> NCPPB number + Other references

09 Other references
  -> identifier candidates
  -> BioSample query terms

10 BioSample search
  -> raw BioSample candidates

11 raw BioSample candidates
  -> accepted matches
  -> review / reject / no-data rows
```

## Week 2 to Week 3 Strategy Change

### Week 2: Broad Keyword Search

The first strategy used many fields from the Week 1 master table:

```text
data/processed/ncppb_xanthomonas_master.csv
```

The search terms included:

```text
ncppb_number
ncppb_number_compact
current_name
name_as_received
alternative_names
pathovar
host
country
other_collection_numbers
other_references
raw_record_text
```

This method of saturation coverage was useful for exploration. It showed that NCBI records could be found.

But it also created too many weak candidates. Species names, pathovar names, host names, and country names often returned taxon-level records. These records may not prove that the exact NCPPB strain is present.

Another critical issue was search speed. Only 30 strains generated approximately 8,000 search terms. Even with a maximum search speed of 10 queries per second, this was too expensive. The search terms had to be optimized.

### Week 3: BioSample-Only Identifier Search

The strategy was then narrowed.

The new search uses only:

```text
NCPPB number
identifier-like terms from Other references
```

Examples:

```text
NCPPB 45
ICMP 204
LMG 673
DSM 18958
NBC 5720
XS 52/5
```

The search is BioSample-only.

This is because BioSample is the NCBI record type closest to strain metadata. SRA and BioProject are useful later, but they are weaker for proving strain identity.

The new workflow separates two jobs:

```text
search stage: be broad enough to avoid missed records
filter stage: be strict enough to avoid false accepted matches
```

## Explanation of the Workflow Strategy

The `Other references` field is free text. It is not fully regular.

Some identifiers are easy:

```text
ICMP 204
LMG 673
DSM 18958
```

Some are less clear:

```text
NBC5720
B67
PC5
XS52/5
```

There is no perfect rule that can extract every true identifier and never extract a false one.

Script `09` is designed for keyword extraction. It should maximize recall while allowing some false positives. At the same time, the workflow uses precision-oriented filtering downstream.

## Script 08: HTML to Other References

Script:

```text
scripts/08_html_to_other_references.py
```

Input:

```text
data/raw/ncppbresult.html
```

Output:

```text
ncppb_number
other_references
```

This script only extracts source text. It does not extract keywords or search NCBI.

## Script 09: Other References to Identifier Candidates

Script:

```text
scripts/09_extract_other_reference_identifiers.py
```

Input:

```text
ncppb_number
other_references
```

Output includes:

```text
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

Script `09` uses simple deterministic rules to extract possible strain identifiers from `Other references`.

Main rule:

```text
letter prefix + number suffix
```

Examples:

```text
ICMP 204
LMG 673
DSM 18958
NBC5720
B67
XS52/5
```

It then normalizes them:

```text
NBC5720  -> NBC 5720
LMG-673  -> LMG 673
NCPPB:45 -> NCPPB 45
XS52/5   -> XS 52/5
```

### Rule 1: Known Collection Prefixes

It first looks for known collection prefixes, such as:

```text
ATCC, CFBP, DSM, ICMP, LMG, NCTC, NRRL, VKM, WDCM
```

These are treated as high-confidence identifiers.

Examples:

```text
LMG 673
DSM 18958
ICMP 204
```

### Rule 2: General Local or Donor Codes

It also looks for short letter-number codes that may be donor or local reference numbers.

Examples:

```text
NBC5720
B67
PC5
XV101
XS52/5
```

These are lower confidence, but they are still kept for search to avoid missing records.

### Rule 3: Context Check

The script checks nearby words.

If the text says things like:

```text
donor reference
also in the collections
collection
accession
```

then the code is more likely to be useful.

### Rule 4: Reject Obvious Noise

Some prefixes are rejected because they are common words, not identifiers.

Examples:

```text
AND
THE
FROM
IN
OF
IS
WITH
```

## Role of the LLM Review in Script 09

The LLM review table was used only during rule development.

The source text from script `08` and the extraction output from script `09` were used as audit material for the LLM. The LLM read the `Other references` text and produced its own table of expected identifiers.

The purpose was simple:

```text
check whether script 09 missed useful identifiers
```

The LLM table was not used as input for NCBI search. It was also not used to accept or reject BioSample records.

It only replaced part of manual rule checking. If the LLM found a useful pattern that script `09` missed, that pattern had to be added back into script `09` as a deterministic rule.

This design is mainly about avoiding low recall. A missed identifier can cause a true BioSample record to never be searched. Extra identifiers are less dangerous because script `11` can reject weak candidates later.

Current audit counts:

```text
script 09 total output rows:                  1657
script 09 included search identifier rows:    1464
script 09 unique included identifiers:        1443
script 09 rejected candidate rows:              96
script 09 no-identifier rows:                   97

LLM expected identifier rows:                 1253
LLM unique expected identifiers:              1238

missing from script 09 compared with LLM:        0
extra in script 09 compared with LLM:          211
unique extra identifiers in script 09:         208
```

These counts mean that script `09` was more permissive than the LLM reference. That is expected. The rule set is designed to avoid missing possible identifiers. The extra identifiers do not enter the accepted BioSample table automatically.

## Script 10: BioSample Raw Search

Script:

```text
scripts/10_harvest_biosample_raw.py
```

Input:

```text
identifier table from script 09
```

Script `10` uses deterministic inputs only. This is important because script `10` is the start of the production retrieval path. The retrieval must be reproducible from scripts and saved inputs.

The input table from script `09` gives script `10` both:

```text
the strain list
the identifiers extracted from Other references
```

The retrieval logic is:

```text
NCPPB number query
+ script 09 identifier queries
-> raw BioSample candidates
```

Script `10` searches one NCPPB-number query for each strain:

```text
NCPPB 101 -> NCPPB[All Fields] AND 101[All Fields]
```

It also adds every script `09` identifier with:

```text
include_for_search = yes
```

Examples:

```text
ICMP 204  -> ICMP[All Fields] AND 204[All Fields]
LMG 673   -> LMG[All Fields] AND 673[All Fields]
NBC 5720  -> NBC[All Fields] AND 5720[All Fields]
```

Output:

```text
raw BioSample candidate rows
```

This script sends searches to NCBI BioSample.

Technical choices:

- Script `10` is only a harvest step.
- It searches BioSample only.
- It uses NCBI ESearch to get BioSample IDs.
- It uses NCBI ESummary to get metadata.
- It saves all returned candidates.
- It writes `no_hit` rows when no BioSample is found.
- It writes `error` rows when a query fails.

The main metadata field for later filtering is:

```text
metadata_text
```

This combines BioSample title, organism, identifiers, infraspecies, and XML-like sample data.

## Script 11: BioSample Evidence Classifier

Script:

```text
scripts/11_filter_biosample_raw.py
```

Input:

```text
raw BioSample candidates from script 10
identifier candidates from script 09
```

Outputs:

```text
matches table
review table
```

Script `11` is the strict evidence step.

Script `11` does not use only alternative identifiers. By default, it uses both:

```text
the NCPPB number
the identifiers extracted by script 09
```

The NCPPB number is the strongest evidence class.

The pattern allows common separators:

```text
space
colon
hyphen
underscore
dot
slash
compact form
```

So these can match the same identifier:

```text
NCPPB 101
NCPPB101
NCPPB:101
NCPPB-101
NCPPB_101
```

### Output Decisions

Script `11` writes:

```text
evidence_decision
evidence_class
evidence_score
```

The main decisions are:

```text
accept
review
reject
no_data
```

### Accepted Evidence

Only strong strain evidence is accepted automatically.

Accepted classes:

```text
confirmed_ncppb_identifier
confirmed_equivalent_collection_identifier
```

Meaning:

- the BioSample metadata contains the target NCPPB number; or
- the BioSample metadata contains a known collection identifier, such as ICMP, LMG, or DSM.

### Review Evidence

Rows go to review when they may be useful but are not strong enough.

Review classes:

```text
review_local_or_donor_identifier_only
review_taxon_only
review_strong_identifier_non_target_organism
review_query_error
review_no_organism_or_strain_identifier
```

Important rule:

```text
local or donor codes do not auto-confirm a BioSample
```

Examples:

```text
NBC 5720
B 67
PC 5
```

These can find candidates, but they require review unless stronger evidence is also present.

### Reject Evidence

Rows are rejected when they are clearly not useful.

Reject classes:

```text
reject_conflicting_identifier
reject_non_target_taxon
reject_weak_identifier_non_target_organism
```

The most important reject rule is:

```text
if the organism is not Xanthomonas and only a weak local/donor code matched, reject the row
```

Another important rule is:

```text
if a different NCPPB number is present, reject the row
```

This reduces the manual review burden.

## First 30 Strain Validation

The first 30 strains used for validation were:

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
NCPPB 186
NCPPB 187
NCPPB 195
NCPPB 196
NCPPB 200
NCPPB 205
NCPPB 206
NCPPB 208
NCPPB 210
NCPPB 211
NCPPB 212
NCPPB 220
NCPPB 226
NCPPB 230
NCPPB 232
NCPPB 240
NCPPB 241
NCPPB 243
NCPPB 273
NCPPB 279
```

### Query Plan for First 30 Strains

The first 30 strains produced:

```text
planned BioSample queries: 44
NCPPB-number queries:      30
Other-reference queries:   14
```

### Validation Result

Using the saved raw BioSample candidates for those 30 strains:

```text
raw BioSample rows: 251
accepted rows:      11
accepted strains:   10
accepted BioSamples: 11
review table rows:  240
```

This means that 10 of the first 30 strains had confirmed BioSample data.

This result is the same as the earlier broad keyword search. The earlier search used many fields from the master table and worked like a saturated search. It also found confirmed data for 10 of the first 30 strains.

The important point is:

```text
the narrower identifier workflow found the same confirmed strains
but with a cleaner and more controlled search strategy
```

So the new workflow reduced broad taxon-level noise without losing the confirmed first-30-strain result seen in the earlier workflow.

Review table decisions:

```text
reject:  220
no_data: 19
review:  1
```

Review table classes:

```text
reject_non_target_taxon:                   199
no_biosample_candidate:                     19
reject_conflicting_identifier:              15
reject_weak_identifier_non_target_organism:  6
review_strong_identifier_non_target_organism: 1
```

This means only one row from the first 30-strain validation needs manual review under the new script `11` rules.

## Final Logic

The final logic is:

```text
08 keeps the source text simple.
09 extracts possible identifiers broadly.
10 saves raw BioSample candidates without judging them.
11 accepts only strong strain-level BioSample evidence.
```

This solves the main problem:

```text
false negatives are controlled by broad identifier search
false positives are controlled by strict BioSample evidence classes
manual review is limited to a small gray area
```
