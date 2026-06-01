# Prompt for LLM Audit of `Other references` Identifier Extraction

Use this prompt in another LLM conversation together with these two TSV files:

```text
results/llm_audit/other_references_source_all.tsv
results/llm_audit/other_reference_llm_review_template.tsv
```

## Prompt

You are auditing identifier extraction from NCPPB `Other references` free text.

Goal: check whether the script-extracted identifiers are complete and reliable for BioSample search candidate generation.

Input:

1. `other_references_source_all.tsv` contains two columns:
   - `ncppb_number`
   - `other_references`

2. `other_reference_llm_review_template.tsv` contains:
   - `ncppb_number`
   - `other_references`
   - `script_identifiers`
   - `script_biosample_search_terms`
   - blank LLM review columns

Task:

For each row, read `other_references` and decide which identifier-like terms should be extracted for NCBI BioSample searching.

Treat an identifier-like term as a short code made from a letter prefix plus a number, including:

- known culture collection identifiers, e.g. `ICMP 204`, `LMG 673`, `DSM 18958`, `ATCC 13901`, `CFBP 7162`;
- donor or local reference identifiers, e.g. `NBC5720`, `XV101`, `PC5`, `B67`;
- compact, colon, hyphen, or spaced formats, e.g. `LMG33367`, `LMG-33367`, `LMG:33367`, `LMG 33367`.

Normalize all extracted identifiers as:

```text
PREFIX NUMBER
```

Examples:

```text
NBC5720 -> NBC 5720
XV101 -> XV 101
PC5 -> PC 5
LMG-33367 -> LMG 33367
```

Do not extract:

- person names;
- country names;
- host names;
- years alone;
- plain strain descriptions with no code-like prefix+number;
- sentence fragments such as `This isolate is also in the collections`.

For each row, fill these columns:

- `llm_expected_identifiers`: semicolon-separated normalized identifiers that should be extracted.
- `llm_missing_from_script`: identifiers that should be extracted but are absent from `script_identifiers`.
- `llm_false_positive_from_script`: identifiers present in `script_identifiers` but not justified by `other_references`.
- `llm_verdict`: one of `match`, `missing_identifier`, `false_positive`, `ambiguous`, or `no_identifier`.
- `llm_notes`: short explanation only when useful.

Output format:

Return a TSV with the same rows and these columns exactly:

```text
ncppb_number
other_references
script_identifiers
script_biosample_search_terms
llm_expected_identifiers
llm_missing_from_script
llm_false_positive_from_script
llm_verdict
llm_notes
```

Important:

- Do not change `ncppb_number`.
- Keep one output row for every input row.
- Use semicolons to separate multiple identifiers.
- If no identifier should be extracted, leave `llm_expected_identifiers` blank and set `llm_verdict` to `no_identifier`.
- If the text is unclear, set `llm_verdict` to `ambiguous` and explain why.
- Focus on avoiding false negatives: if a code-like donor/reference number may plausibly identify the strain, include it and explain uncertainty in `llm_notes`.

After the LLM-filled TSV is saved locally, compare it with the script output using:

```bash
python3 scripts/07_compare_other_reference_llm_audit.py \
  --review results/llm_audit/other_reference_llm_review_filled.tsv \
  --output results/llm_audit/other_reference_llm_vs_script_comparison.tsv
```
