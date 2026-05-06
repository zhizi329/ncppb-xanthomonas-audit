# Data Dictionary

## NCPPB Master Table

Each row should represent one NCPPB Xanthomonas strain record.

| Column | Meaning |
|---|---|
| `ncppb_number` | Standard NCPPB catalogue number, e.g. `NCPPB 1234`. |
| `ncppb_number_compact` | Compact number without space, e.g. `NCPPB1234`. Useful for search. |
| `current_name` | Current name shown in the NCPPB catalogue. |
| `name_as_received` | Name originally received by the collection, if available. |
| `alternative_names` | Synonyms, historical names, pathovar names, or other names. Use `;` to separate multiple values. |
| `pathovar` | Pathovar information if stated. |
| `host` | Host plant or source host, if available. |
| `country` | Country of origin, if available. |
| `other_collection_numbers` | Equivalent strain identifiers in other collections, if available. Use `;` to separate values. |
| `ncppb_catalogue_url` | URL for the NCPPB record. |
| `catalogue_sequence_links` | Sequence links already present in NCPPB catalogue, if any. |
| `notes` | Human notes about uncertainty or curation issues. |
| `sequencing_type` | Sequencing type explicitly shown in the NCPPB catalogue, if present. |
| `year_added` | Year the strain was added to NCPPB, if shown. |
| `type_strain_of_species` | Whether the catalogue marks this as a type strain of the species. |
| `pathotype_strain` | Whether the catalogue marks this as a pathotype strain. |
| `other_references` | Free-text references and collection notes from the NCPPB page. |
| `raw_record_text` | Full extracted text for the record, kept for traceability/debugging. |

## Important Rule

Do not delete original naming fields just because they look old or inconsistent. Old names may be exactly what appears in NCBI metadata.
