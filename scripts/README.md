# Current scripts

| Script | Purpose |
|---|---|
| `run_ncppb_audit_v2.py` | Complete catalogue-to-NCBI V2.1 workflow |
| `validate_ncppb_audit_v2.py` | Validate invariants, query coverage and hashes |
| `build_sequence_retrieval_manifest_v2.py` | Rebuild resource and phylogeny manifests |
| `fetch_ncppb_snapshot_v2.py` | Optional NCPPB HTML retrieval helper |
| `three_species_phylogeny.py` | Three-species smoke-test workflow and summaries |
| `recover_three_species_fastq.py` | Resume and MD5-verify ENA FASTQ recovery into external `../xanthomonas-data/` |
| `fetch_three_species_references.sh` | Reference-download helper |
| `refresh_run_manifest_hashes.py` | Refresh hashes after intentional byte changes |
| `check_repository_hygiene.py` | Reject deprecated directories and large payloads |

Legacy V1 numbered scripts and workbook-generation scripts were removed. Large reads remain local working data under ignored `work/` and are not uploaded to GitHub.
