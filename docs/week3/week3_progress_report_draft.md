# Week 3 Progress Report Draft

Week 3 focused on refining the search strategy based on the Week 2 smoke test.

In Week 2, the script showed that NCBI E-utilities could retrieve candidate BioSample, Assembly, and SRA IDs. However, those results only showed that candidate records existed.

The main goal of Week 3 was to build a pilot table for the first 30 NCPPB *Xanthomonas* strains and identify a reliable workflow. The work included one clear false start: I initially tried to use almost all visible keywords from the NCPPB webpages and master table, but this produced too many irrelevant candidates. I then narrowed the strategy to a BioSample-only identifier search.

## Search Strategies Tested

### Round 1: Broad Keyword Harvest

The first strategy aimed to maximize recall. Keywords were extracted from the NCPPB catalogue and webpage HTML files, including NCPPB number, compact NCPPB number, catalogue name, name as received, other names, other references, and some current or historical species names. The search also covered multiple NCBI databases, including BioSample, Assembly, and SRA.

This approach produced 7,728 raw candidates from only 30 strains. If applied to the full NCPPB dataset of about 900 strains, it would require many search commands and create a large manual review burden. The high number of candidates showed that this strategy was too broad.

Most candidates came from species names, pathovar names, or other general text. Many were only taxon-level hits, non-*Xanthomonas* records, or records for other NCPPB strains within the same species. These records were not useful for confirming the identity of a specific strain.

However, this step was still informative. After strict filtering, the 7,728 raw candidates still produced confirmed record sets for only 10 strains.

### Round 2: BioSample-Only Identifier Harvest

The second strategy searched only BioSample and used only identifier-based keywords. Two types of search terms were kept:

- `NCPPB + number`, such as `NCPPB 45`.
- Identifier-style terms from other references or collection number fields, such as `LMG 33367`, `NBC5720`, and `ICMP 204`.

This round did not use species name, pathovar name, catalogue name, host, country, or broad taxonomic labels as NCBI search terms. These terms can produce many taxon-level candidates, but they cannot confirm strain identity.

The new query format split each identifier into a prefix and a number, for example:

```text
NCPPB[All Fields] AND 45[All Fields]
LMG[All Fields] AND 33367[All Fields]
NBC[All Fields] AND 5720[All Fields]
```

This format was used to cover different metadata formats, such as `NCPPB 45`, `NCPPB45`, `NCPPB:45`, or `NCPPB_Number: 45`. False positives may still occur, but they can be removed during local filtering.

The results for the first 30 strains were:

| Metric | Count |
|---|---:|
| Planned BioSample identifier queries | 42 |
| Raw BioSample candidate rows | 132 |
| Accepted BioSample records | 11 |
| Review rows, including no-match summaries | 141 |
| BioSample-centred record sets | 11 |
| Strains with confirmed BioSample record sets | 10 / 30 |

Both search strategies confirmed records for the same number of strains: 10 out of 30. This shows that the second strategy greatly reduced the number of raw candidates without losing any confirmed results under the current filtering rules.

## Technical Details

### Keywords Extracted From the Week 1 Master Table

The Week 1 master table is the main structured input for the workflow:

```text
data/processed/ncppb_xanthomonas_master.csv
```

It was created from the saved NCPPB webpage output. The table keeps the original strain-level information needed for searching and checking, including:

- `ncppb_number`, for example `NCPPB 45`.
- `ncppb_number_compact`, for example `NCPPB45`.
- `current_name`, the catalogue name currently used by NCPPB.
- `name_as_received`, the name originally received by the collection.
- `alternative_names`, including historical or synonym names.
- `pathovar`, where it can be extracted from the name.
- `host` and `country`.
- `other_collection_numbers`, such as ICMP, LMG, DSM, ATCC, or CFBP numbers.
- `other_references`, which may contain donor reference numbers or collection references.
- `raw_record_text`, which preserves the visible text from the original NCPPB record.

In the first broad strategy, many of these fields were used as search terms. This included name-based terms such as catalogue name, name as received, and alternative names. This was useful as an exploratory step, but it produced too many taxon-level candidates.

In the refined Week 3 strategy, the final BioSample search only uses identifier-style fields:

- the NCPPB number;
- other collection numbers;
- identifier-like terms extracted from `other_references`.

Name-based fields are still kept in the master table because they are useful for interpretation and manual review, but they are no longer used as NCBI search terms.

### Extracting Identifier Terms From `Other references`

The `Other references` field is important because some public records may not use the NCPPB number. Instead, they may use another collection or donor reference number. For example:

```text
The donor reference is NBC5720
This isolate is also in the collections; LMG 33367
This isolate was isolated by Harrie Koenraadt
The source of this isolate was University of Florida, North Florida Research and Education Center Plant Disease
```

From this kind of text, the workflow should extract terms such as:

```text
NBC 5720
LMG 33367
```

The extraction is done using regular expression rules. The script looks for a short letter prefix followed by a number. Compact forms are normalized into a standard prefix-plus-number format. For example:

| Original text | Normalized identifier |
|---|---|
| `NBC5720` | `NBC 5720` |
| `LMG 33367` | `LMG 33367` |
| `ICMP204` | `ICMP 204` |
| `NCPPB:45` | `NCPPB 45` |

The query is then written as prefix and number joined with `AND`:

```text
NBC[All Fields] AND 5720[All Fields]
LMG[All Fields] AND 33367[All Fields]
NCPPB[All Fields] AND 45[All Fields]
```

This is deliberately broader than searching for only one exact string. It can match different metadata formats, including `NCPPB 45`, `NCPPB45`, `NCPPB:45`, or `NCPPB_Number 45`.

However, extraction alone is not treated as proof. These identifiers only generate candidate BioSample records. The returned metadata must still pass the filtering step before it is counted as a confirmed strain-level match.

### Implementation of Non-standard Identifiers in `Other references`

The non-standard identifiers in `Other references` are handled in `scripts/03_ncbi_smoke_test.py`. The aim is to find useful code-like strings without using the whole free-text sentence as a search term.

The implementation uses two identifier patterns.

The first pattern detects known culture collection prefixes:

```text
ATCC, BCCM, CCUG, CFBP, CIP, DSM, DSMZ, ICMP, JCM, LMG, NCTC, NIB, NRRL, PDDCC, PD, RIV, UQM, VKM, WDCM
```

This catches standard or semi-standard collection identifiers such as:

```text
ICMP 204
LMG 673
DSM 18958
ATCC 13901
CFBP 7162
```

The second pattern is more general and is used for donor or local reference codes. It looks for:

```text
letter prefix, 2-10 characters long + optional separator + number
```

Examples include:

```text
NBC5720 -> NBC 5720
XV101 -> XV 101
PC5 -> PC 5
B67 -> B 67
```

The code does not try to understand the biological meaning of these prefixes at the extraction stage. It only treats them as possible identifiers because they appear in the NCPPB `Other references` field.

The extraction process is:

1. Read the `other_references` text for one NCPPB strain.
2. Run the known-collection pattern and the general donor-reference pattern.
3. Split each match into `prefix` and `number`.
4. Convert the prefix to uppercase.
5. Normalize compact forms into a spaced form, for example `NBC5720` becomes `NBC 5720`.
6. Remove duplicates for the same strain.
7. Add the result to the strain's identifier list as `other_reference_identifier`.

These extracted identifiers are then used to generate BioSample search terms. For example:

```text
NBC 5720 -> NBC[All Fields] AND 5720[All Fields]
XV 101   -> XV[All Fields] AND 101[All Fields]
PC 5     -> PC[All Fields] AND 5[All Fields]
```

This rule is designed to reduce false negatives. If NCBI uses the donor reference instead of the NCPPB number, a strict `NCPPB`-only search would miss the record. Searching extracted donor/reference codes gives the workflow another chance to find the BioSample.

The rule can generate false positives, especially for short identifiers such as `PC 5` or `B 67`. This is acceptable at the harvest stage because these are not accepted automatically. They only produce candidate BioSample rows. The filtering step still requires the returned metadata to contain the expected identifier for the target strain before the record is accepted.

In short, the `Other references` rule is deliberately recall-oriented:

```text
free-text Other references
  -> extract code-like prefix+number terms
  -> normalize them
  -> search BioSample broadly
  -> verify exact identifier in metadata
  -> accept only confirmed strain-level matches
```

### How the Rules Reduce False Negatives

The main risk in this project is not only false positives. False negatives are also important, because a real public record may be missed if the search is too narrow. The refined strategy tries to reduce false negatives in several ways.

First, the NCPPB number is always searched as two parts: the prefix and the number. For example, `NCPPB 45` is searched as:

```text
NCPPB[All Fields] AND 45[All Fields]
```

This avoids depending on one exact punctuation format. A BioSample record may write the same strain as `NCPPB 45`, `NCPPB45`, `NCPPB:45`, `NCPPB-45`, or `NCPPB_Number 45`. Searching the prefix and number separately makes it less likely that a real record is missed because of spacing or punctuation.

Second, the workflow also uses alternative identifiers from `other_collection_numbers` and `Other references`. This is important because public NCBI records may use an ICMP, LMG, DSM, ATCC, CFBP, donor, or local reference number instead of the NCPPB number. If the search only used NCPPB numbers, those records could become false negatives.

Third, compact identifiers are normalized before searching. For example, `NBC5720` is converted to `NBC 5720`, then searched as:

```text
NBC[All Fields] AND 5720[All Fields]
```

This means the same rule can catch both compact and spaced formats in NCBI metadata.

Fourth, the search is performed in BioSample `All Fields`, not only in one specific field such as title or organism. This helps because strain identifiers may appear in different BioSample fields, including title, isolate, strain, culture collection, infraspecies, attributes, or free-text sample metadata.

Fifth, the workflow does not use species or pathovar names to confirm records, but it also does not require the species name to be identical during the search. This avoids missing records where taxonomy has changed, where NCBI uses an older name, or where NCPPB and NCBI use different taxonomic labels for the same strain.

Finally, candidates are not discarded simply because the initial search is noisy. The search step is allowed to return false positives, and the filtering step decides whether each candidate is accepted, rejected, or kept for review. This design reduces false negatives because weak but potentially useful candidates can still be inspected instead of being removed too early.

The remaining false-negative risk is metadata absence. If a real NCBI record does not contain the NCPPB number or any known equivalent identifier, and only uses a private laboratory name, the current automated workflow may not confirm it. These cases would require manual curation or additional external mapping information.

### Verifying Extracted Identifiers

After BioSample candidates are retrieved, each candidate is checked locally. The workflow builds an exact identifier list for each NCPPB strain. This list includes:

- the standard NCPPB number, such as `NCPPB 45`;
- equivalent collection numbers from `other_collection_numbers`, such as `ICMP 204`;
- donor or reference identifiers extracted from `Other references`, such as `NBC 5720`.

The returned BioSample metadata are then searched for these identifiers. The matching pattern allows common separator differences, such as spaces, hyphens, colons, underscores, and optional words like `Number` or `No.`. This is necessary because public metadata may write the same identifier in different ways.

For example, the same NCPPB number may appear as:

```text
NCPPB 45
NCPPB45
NCPPB:45
NCPPB_Number NCPPB 45
```

Only records containing the expected strain identifier are accepted as `strong_strain_match`. If a record only has a compatible species name but no strain-level identifier, it is not accepted.

### Filtering Strategy

The filtering step is performed by:

```text
scripts/04_ncbi_classify_candidates.py
```

It reads the raw BioSample candidate table and classifies each row without making further NCBI requests.

The current filtering logic is:

1. If the `organism` field is present and is not *Xanthomonas*, the record is rejected as `non_xanthomonas_organism`.
2. If the metadata contains the target NCPPB number or an accepted equivalent identifier, the record is accepted as `strong_strain_match`.
3. If the metadata contains a different NCPPB number, the record is rejected as `conflicting_ncppb_number`.
4. If the record is *Xanthomonas* but has no exact strain identifier, it is kept as `taxon_level_only`.
5. If no accepted match is found for a strain, a no-match summary row is added.

This filtering is intentionally strict. A species or pathovar name alone is not enough to prove that a public record belongs to the target NCPPB strain.

### Verifying Links Between BioSample and Other NCBI Records

The refined Week 3 search confirms BioSample records first. This is because BioSample is the most appropriate NCBI layer for strain-level metadata. It can contain organism name, strain name, isolate name, culture collection number, and other sample attributes.

SRA, Assembly, BioProject, and BioCollection should then be linked from accepted BioSample accessions rather than searched directly by broad keywords.

The intended relationship check is:

```text
NCPPB strain
  -> accepted BioSample
  -> linked SRA / Assembly / BioProject / BioCollection evidence
```

For SRA, the workflow should retrieve SRA records linked to the accepted BioSample accession. A linked SRA record should only be counted if its BioSample field matches the accepted BioSample accession. The SRA record can then show whether raw reads exist and what library strategy was used, such as WGS or RNA-Seq.

For Assembly, the workflow should retrieve Assembly records linked to the accepted BioSample accession. The Assembly summary should be checked to confirm that its `biosample_accession` matches the accepted BioSample. Assembly level can then be used to distinguish complete genome, chromosome-level assembly, scaffold-level assembly, or contig-level assembly.

For BioProject, the workflow should record the BioProject accession linked through the accepted BioSample or through linked SRA/Assembly records. BioProject is useful for understanding the submission context, but it is not itself sequence evidence for a strain unless it is connected through the accepted BioSample.

For BioCollection, the workflow should treat it as collection metadata rather than sequence evidence. BioCollection or culture collection fields can help interpret identifiers such as NCPPB, ICMP, LMG, DSM, or ATCC, but they should not replace strain-level matching. A BioCollection-related identifier is useful only when it supports the same accepted BioSample record.

The key rule is that BioSample accession is the bridge. A linked SRA, Assembly, BioProject, or BioCollection entry should not be counted for the NCPPB strain unless it can be connected back to an accepted BioSample record.

### Record Set Logic

The final output should be organized as BioSample-centred record sets. One record set represents one accepted BioSample and any linked public records attached to it.

If a BioSample has linked Assembly and SRA records, all of them should be grouped under the same BioSample-centred record set. This avoids counting the same biological sample multiple times across different NCBI databases.

The record set can then be assigned a data availability category:

| Evidence found through accepted BioSample | Category |
|---|---|
| Complete genome assembly | `complete_genome_available` |
| Chromosome, scaffold, or contig-level assembly | `draft_assembly_available` |
| SRA reads but no assembly | `reads_only` |
| BioSample only, with no linked reads or assembly yet | `biosample_only` |
| No accepted BioSample | `no_confirmed_public_data_found` |

In the current Week 3 final run, only BioSample was searched directly, so the accepted records are currently classified as `biosample_only`. The next technical step is to add a BioSample-based linkage step to retrieve and verify SRA, Assembly, BioProject, and BioCollection relationships.
