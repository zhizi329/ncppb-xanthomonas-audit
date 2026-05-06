# Week 1 Dataset Notes

## Input Used

Primary input file:

```text
data/raw/ncppbresult_original.html
```

This file was saved from the NCPPB catalogue result page for Xanthomonas.

A previous `view-source:` save is also kept as raw backup:

```text
data/raw/ncppbresult.html
```

## Extracted Files

```text
data/raw/ncppb_catalogue.csv
data/processed/ncppb_xanthomonas_master.csv
data/interim/search_terms.csv
```

## Current Counts

| Item | Count |
|---|---:|
| NCPPB records extracted | 898 |
| Master table rows | 898 |
| Search terms generated | 5394 |
| Records with name as received | 706 |
| Records with alternative/other names | 500 |
| Records with pathovar parsed | 686 |
| Records with host | 856 |
| Records with country | 875 |
| Records with other collection numbers parsed | 299 |
| Records with catalogue sequencing links | 16 |
| Records with catalogue sequencing type field | 2 |
| Type strain field present | 898 |
| Pathotype strain field present | 897 |

## Interpretation

The NCPPB catalogue provides enough metadata to build the Week 1 master table. The most useful fields for later matching are:

- NCPPB number;
- catalogue/current name;
- name as received;
- alternative names;
- other collection numbers;
- catalogue sequencing links;
- type/pathotype status;
- country and host metadata.

The catalogue itself contains only limited explicit sequencing links. Therefore, the main Week 2 task is still needed: query NCBI metadata programmatically and classify each candidate record using evidence levels.

## Data Quality Notes

- The NCPPB page uses nested HTML rows rather than a clean downloadable table.
- Some fields are absent for some strains, especially `name_as_received`, `alternative_names`, and `host`.
- Other collection numbers were parsed from free text, mainly from `other_references`; this should be manually checked during the pilot stage.
- Name matching alone is not enough. Strain-level evidence should still be based on NCPPB number, equivalent collection number, BioSample strain/culture collection fields, or clear accession links.
