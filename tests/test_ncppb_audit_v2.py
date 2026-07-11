from __future__ import annotations

import tempfile
import unittest
import hashlib
import os
import time
from unittest.mock import patch
from pathlib import Path

from ncppb_audit_v2.catalogue import compare_to_v1, parse_catalogue_html
from ncppb_audit_v2.explorer import build_explorer_table
from ncppb_audit_v2.identifiers import (
    build_identifier_review_queue,
    extract_identifiers,
    identifier_strength,
    source_clause_identifiers,
    split_collection_payload,
)
from ncppb_audit_v2.matching import (
    apply_review_decisions,
    classify_candidate,
    compare_v1_v2,
    exact_field_match,
    pathovar_status,
)
from ncppb_audit_v2.ncbi import (
    NcbiClient,
    linked_summary,
    map_shared_ncppb_candidates,
    map_shared_other_prefix_candidates,
    parse_biosamples,
    merge_verified_resource_seeds,
)
from ncppb_audit_v2.queries import build_query_plan
from ncppb_audit_v2.retrieval import assembly_rank, build_retrieval_manifests, sra_metadata
from scripts.run_ncppb_audit_v2 import resolve_api_key


SAMPLE_HTML = """
<table>
<tr><td><a href="furtherinfo.cfm?ncppb_no=45">NCPPB No. 45:</a></td>
<td><strong>Catalogue name:</strong></td><td><i>Xanthomonas campestris</i> pv. campestris</td></tr>
<tr><td></td><td colspan="2"><table>
<tr><td><strong>Name as received:</strong></td><td>Xanthomonas campestris</td></tr>
<tr><td><strong>Other references:</strong></td><td>
The donor reference is 38/2<br>
This isolate is also in the collections; ICMP 204, LMG 673<br>
This isolate was isolated by A.C. Hayward B621<br>
</td></tr></table></td></tr>
<tr><td><a href="furtherinfo.cfm?ncppb_no=101">NCPPB No. 101:</a></td>
<td><strong>Catalogue name:</strong></td><td><i>Xanthomonas cassavae</i></td></tr>
<tr><td></td><td colspan="2"><table>
<tr><td><strong>Other references:</strong></td><td></td></tr>
</table></td></tr>
</table>
"""


class NcppbAuditV2Tests(unittest.TestCase):
    def test_catalogue_parser_preserves_break_clauses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.html"
            path.write_text(SAMPLE_HTML, encoding="utf-8")
            strains, clauses = parse_catalogue_html(path)
        self.assertEqual([row["ncppb_number"] for row in strains], ["NCPPB 45", "NCPPB 101"])
        self.assertEqual(len(clauses), 3)
        self.assertEqual([row["clause_type"] for row in clauses], ["donor_reference", "collection_list", "isolated_by"])
        self.assertEqual(clauses[0]["raw_value"], "38/2")

    def test_catalogue_hash_is_opt_in_and_never_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.html"
            path.write_text(SAMPLE_HTML, encoding="utf-8")
            strains, _ = parse_catalogue_html(path)
            recorded, _ = parse_catalogue_html(path, record_source_hash=True)
        self.assertEqual(strains[0]["source_snapshot_sha256"], "")
        self.assertEqual(
            recorded[0]["source_snapshot_sha256"],
            hashlib.sha256(SAMPLE_HTML.encode("utf-8")).hexdigest(),
        )

    def test_api_key_prompt_is_hidden_and_returns_prompted_value(self) -> None:
        with patch("scripts.run_ncppb_audit_v2.getpass.getpass", return_value="secret-key") as prompt:
            value = resolve_api_key("", prompt_requested=True, run_ncbi=True)
        self.assertEqual(value, "secret-key")
        prompt.assert_called_once()

    def test_identifier_extraction_never_turns_label_is_into_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.html"
            path.write_text(SAMPLE_HTML, encoding="utf-8")
            strains, clauses = parse_catalogue_html(path)
        identifiers, _ = extract_identifiers(strains, clauses)
        values = {(row["identifier_raw"], row["identifier_type"]) for row in identifiers}
        self.assertIn(("38/2", "donor_reference"), values)
        self.assertNotIn(("IS 38/2", "donor_reference"), values)
        self.assertIn(("ICMP 204", "collection_number"), values)
        self.assertIn(("B621", "isolate_code"), values)

    def test_source_parser_does_not_include_person_name(self) -> None:
        self.assertEqual(source_clause_identifiers("A.C. Hayward B621"), [("B621", "isolate_code")])
        self.assertEqual(
            source_clause_identifiers("ex ATCC 11726 ex W.H. Burkholder XB10"),
            [("ATCC 11726", "collection_number"), ("XB10", "isolate_code")],
        )

    def test_query_plan_uses_prefix_harvest_and_local_full_identifier_mapping(self) -> None:
        strains = [{"ncppb_number": "NCPPB 45", "expected_genus": "Xanthomonas"}]
        identifiers = [{
            "ncppb_number": "NCPPB 45",
            "identifier_raw": "NCPPB 45",
            "identifier_normalized": "NCPPB45",
            "identifier_type": "ncppb_number",
            "search_eligible": "yes",
        }]
        plan = build_query_plan(strains, identifiers)
        self.assertIn('NCPPB[All Fields]', plan[0]["query_term"])
        self.assertIn('NCPPB {number}', plan[0]["local_match_variants_json"])
        self.assertNotIn('NCPPB[Text Word] AND 45[Text Word]', plan[0]["query_term"])
        exact = [row for row in plan if row["query_tier"] == "exact_full_identifier"]
        self.assertEqual(len(exact), 1)
        self.assertIn('"NCPPB 45"[Text Word]', exact[0]["query_term"])
        self.assertIn('"NCPPB45"[Text Word]', exact[0]["query_term"])
        self.assertNotIn(" AND 45[", exact[0]["query_term"])
        self.assertEqual(len(plan), 3)

    def test_prefix_candidates_map_only_by_complete_bounded_ncppb_identifier(self) -> None:
        candidates = [
            {"ncppb_number": "ALL_NCPPB", "status": "ok", "ncbi_uid": "1", "strain": "NCPPB:45", "query_track": "ncppb_number"},
            {"ncppb_number": "ALL_NCPPB", "status": "ok", "ncbi_uid": "2", "strain": "NCPPB", "sample_name": "replicate 45", "query_track": "ncppb_number"},
        ]
        mapped, unmapped = map_shared_ncppb_candidates(candidates, [{"ncppb_number": "NCPPB 45"}])
        self.assertEqual([row["ncbi_uid"] for row in mapped], ["1"])
        self.assertEqual([row["ncbi_uid"] for row in unmapped], ["2"])

    def test_structured_exact_match_does_not_accept_separate_terms(self) -> None:
        self.assertEqual(exact_field_match("NCPPB 45", {"strain": "NCPPB:45"}), "strain")
        self.assertEqual(exact_field_match("XCP3", {"isolate": "Xcp-3"}), "isolate")
        self.assertEqual(exact_field_match("PXO86", {"isolate": "PXO 86"}), "isolate")
        self.assertEqual(
            exact_field_match("NCPPB 45", {"strain": "NCPPB", "sample_name": "replicate 45"}),
            "",
        )

    def test_taxonomy_conflict_preserves_strong_identity_but_flags_taxonomy_review(self) -> None:
        strain = {
            "ncppb_number": "NCPPB 45",
            "canonical_name": "Xanthomonas campestris",
            "current_name_raw": "Xanthomonas campestris pv. campestris",
        }
        candidate = {
            "status": "ok",
            "strain": "NCPPB 45",
            "organism": "Pseudomonas syringae",
        }
        identifiers = [{
            "identifier_raw": "NCPPB 45",
            "identifier_type": "ncppb_number",
            "search_eligible": "yes",
        }]
        result = classify_candidate(strain, candidate, identifiers)
        self.assertEqual(result["evidence_class"], "structured_exact_identifier")
        self.assertEqual(result["decision"], "accept")
        self.assertEqual(result["taxonomy_status"], "different_lineage")
        self.assertEqual(result["taxonomy_review_required"], "yes")
        self.assertEqual(result["manual_review_required"], "yes")

    def test_pathovar_is_compared_separately_from_species_name(self) -> None:
        strain = {"current_name_raw": "Xanthomonas campestris pv. campestris"}
        self.assertEqual(
            pathovar_status(strain, {"organism": "Xanthomonas campestris pv. campestris"}),
            "same_pathovar",
        )
        self.assertEqual(
            pathovar_status(strain, {"organism": "Xanthomonas campestris pv. vesicatoria"}),
            "pathovar_mismatch",
        )

    def test_review_decision_round_trip_preserves_automatic_decision(self) -> None:
        rows = [{
            "ncppb_number": "NCPPB 45",
            "biosample_accession": "SAMN1",
            "decision": "accept",
            "taxonomy_status": "different_lineage",
            "manual_review_required": "yes",
            "taxonomy_review_required": "yes",
        }]
        reviewed = apply_review_decisions(rows, [{
            "ncppb_number": "NCPPB 45",
            "biosample_accession": "SAMN1",
            "reviewer_decision": "approve_for_downstream",
            "reviewer_notes": "documented reclassification",
        }])
        self.assertEqual(reviewed[0]["original_decision"], "accept")
        self.assertEqual(reviewed[0]["reviewer_approved_for_downstream"], "yes")
        self.assertEqual(reviewed[0]["manual_review_required"], "no")

    def test_taxonomy_conflicted_resource_is_not_selected(self) -> None:
        supervisors = [{
            "ncppb_number": "NCPPB 45",
            "ncppb_current_name": "Xanthomonas campestris",
            "confirmed_biosample_accessions": "SAMN_BAD; SAMN_GOOD",
            "provisional_biosample_accessions": "",
            "taxonomy_review_required": "yes",
        }]
        matches = [
            {"ncppb_number": "NCPPB 45", "biosample_accession": "SAMN_BAD", "decision": "accept", "taxonomy_status": "different_lineage", "reviewer_approved_for_downstream": "no"},
            {"ncppb_number": "NCPPB 45", "biosample_accession": "SAMN_GOOD", "decision": "accept", "taxonomy_status": "same_name", "reviewer_approved_for_downstream": "no"},
        ]
        links = [
            {"ncppb_number": "NCPPB 45", "biosample_accession": "SAMN_BAD", "linked_database": "assembly", "linked_accession": "GCF_999.1", "assembly_level": "Complete Genome", "extra_json": "{}", "status": "ok"},
            {"ncppb_number": "NCPPB 45", "biosample_accession": "SAMN_GOOD", "linked_database": "assembly", "linked_accession": "GCF_111.1", "assembly_level": "Contig", "extra_json": "{}", "status": "ok"},
        ]
        resources, phylogeny, _ = build_retrieval_manifests(supervisors, matches, links)
        selected = [row for row in resources if row.get("selected_for_phylogeny") == "yes"]
        self.assertEqual([row["resource_accession"] for row in selected], ["GCF_111.1"])
        bad = next(row for row in resources if row.get("resource_accession") == "GCF_999.1")
        self.assertEqual(bad["downstream_block_reason"], "taxonomy_review_required")
        self.assertEqual(phylogeny[0]["preferred_sequence_accessions"], "GCF_111.1")

    def test_medium_identifier_is_provisional_even_when_exact(self) -> None:
        strain = {"ncppb_number": "NCPPB 45", "canonical_name": "Xanthomonas campestris"}
        candidate = {"status": "ok", "strain": "B621", "organism": "Pseudomonas syringae"}
        identifiers = [{
            "identifier_raw": "B621",
            "identifier_type": "isolate_code",
            "identifier_strength": "medium",
            "search_eligible": "yes",
        }]
        result = classify_candidate(strain, candidate, identifiers)
        self.assertEqual(result["decision"], "review")
        self.assertIn("medium_identifier_requires_corroboration", result["review_reason"])

    def test_period_separates_two_formal_collection_identifiers(self) -> None:
        self.assertEqual(
            split_collection_payload("CFBP 2526. ATCC 43911"),
            ["CFBP 2526", "ATCC 43911"],
        )

    def test_short_other_reference_is_not_searchable_strength(self) -> None:
        self.assertEqual(identifier_strength("R1", "isolate_code"), "weak")
        self.assertEqual(identifier_strength("B621", "isolate_code"), "medium")

    def test_identifier_review_queue_excludes_preserved_source_prose(self) -> None:
        rows = [
            {"ncppb_number": "NCPPB 45", "identifier_raw": "A person", "identifier_type": "source_reference_raw", "validation_status": "review_required"},
            {"ncppb_number": "NCPPB 45", "identifier_raw": "ABC", "identifier_type": "collection_candidate", "validation_status": "review_required"},
        ]
        queue = build_identifier_review_queue(rows)
        self.assertEqual([row["identifier_raw"] for row in queue], ["ABC"])

    def test_collection_prefix_harvest_maps_alias_field(self) -> None:
        candidates = [{
            "ncppb_number": "ALL_OTHER_PREFIX:CFBP",
            "query_track": "other_references",
            "status": "ok",
            "ncbi_uid": "3",
            "identity_aliases": "CFBP 2526",
        }]
        identifiers = [{
            "ncppb_number": "NCPPB 45",
            "identifier_raw": "CFBP 2526",
            "identifier_type": "collection_number",
            "search_eligible": "yes",
        }]
        mapped, unmapped = map_shared_other_prefix_candidates(candidates, identifiers)
        self.assertEqual(mapped[0]["ncppb_number"], "NCPPB 45")
        self.assertEqual(unmapped, [])

    def test_v1_v2_comparison_uses_sets_and_category_aliases(self) -> None:
        v1 = [{
            "ncppb_number": "NCPPB 45",
            "sequence_data_category": "no_confirmed_public_sequence_data",
            "biosample_accessions": "SAMN2; SAMN1",
        }]
        v2 = [{
            "ncppb_number": "NCPPB 45",
            "sequence_availability_category": "no_confirmed_public_data",
            "confirmed_biosample_accessions": "SAMN1; SAMN2",
        }]
        rows = compare_v1_v2(v1, v2, [{"ncppb_number": "NCPPB 45", "snapshot_status": "present_in_both"}])
        self.assertEqual(rows[0]["sequence_category_changed"], "no")
        self.assertEqual(rows[0]["biosample_accessions_changed"], "no")

    def test_snapshot_diff_keeps_missing_v1_strain(self) -> None:
        rows = compare_to_v1(
            [{"ncppb_number": "NCPPB 4416", "current_name": "Xanthomonas old"}],
            [{"ncppb_number": "NCPPB 45", "current_name_raw": "Xanthomonas current"}],
        )
        status = {row["ncppb_number"]: row["snapshot_status"] for row in rows}
        self.assertEqual(status["NCPPB 4416"], "missing_from_v2_snapshot")
        self.assertEqual(status["NCPPB 45"], "added_in_v2_snapshot")

    def test_explorer_union_keeps_historical_missing_row_with_zero_counts(self) -> None:
        supervisor = [{
            "ncppb_number": "NCPPB 45",
            "ncppb_current_name": "Xanthomonas campestris",
            "confirmed_biosample_accessions": "SAMN1",
            "assembly_accessions": "GCF_1.1",
        }]
        snapshot = [
            {"ncppb_number": "NCPPB 45", "snapshot_status": "present_in_both"},
            {"ncppb_number": "NCPPB 4416", "snapshot_status": "missing_from_v2_snapshot", "v1_current_name": "Xanthomonas old"},
        ]
        rows = build_explorer_table(supervisor, snapshot, [])
        self.assertEqual(len(rows), 2)
        missing = next(row for row in rows if row["ncppb_number"] == "NCPPB 4416")
        self.assertEqual(missing["ncbi_record_match_count"], "0")
        self.assertEqual(missing["has_confirmed_ncbi_data"], "no")

    def test_biosample_xml_keeps_identity_fields_separate(self) -> None:
        xml = """<BioSampleSet><BioSample id="123" accession="SAMN000001">
        <Ids><Id db="BioSample">SAMN000001</Id><Id db="SRA">SRS1</Id></Ids>
        <Description><Title>sample title</Title><Organism taxonomy_id="339" taxonomy_name="Xanthomonas campestris"/></Description>
        <Attributes>
          <Attribute attribute_name="strain">NCPPB:45</Attribute>
          <Attribute attribute_name="isolate">WHRI 6379</Attribute>
          <Attribute attribute_name="culture collection">NCPPB 45</Attribute>
          <Attribute attribute_name="isolate-name-alias">CFBP 2526</Attribute>
          <Attribute attribute_name="Other_CC">ATCC 43911</Attribute>
          <Attribute attribute_name="host">Brassica oleracea</Attribute>
          <Attribute attribute_name="geo_loc_name">United Kingdom</Attribute>
          <Attribute attribute_name="collection_date">1984-05</Attribute>
          <Attribute attribute_name="isolation_source">leaf lesion</Attribute>
        </Attributes></BioSample></BioSampleSet>"""
        records = parse_biosamples(xml, Path("cache.xml"))
        row = records["123"]
        self.assertEqual(row["strain"], "NCPPB:45")
        self.assertEqual(row["isolate"], "WHRI 6379")
        self.assertEqual(row["culture_collection"], "NCPPB 45")
        self.assertEqual(row["identity_aliases"], "CFBP 2526; ATCC 43911")
        self.assertEqual(row["taxid"], "339")
        self.assertEqual(row["host"], "Brassica oleracea")
        self.assertEqual(row["geographic_location"], "United Kingdom")
        self.assertEqual(row["collection_date"], "1984-05")
        self.assertEqual(row["isolation_source"], "leaf lesion")

    def test_link_summary_extracts_accessions_from_json_esummary(self) -> None:
        assembly = linked_summary(
            "assembly",
            "1",
            {"assemblyaccession": "GCF_000001.1", "assemblystatus": "Complete Genome"},
        )
        sra = linked_summary("sra", "2", {"runs": '<Run acc="SRR123"/><Run acc="ERR456"/>'})
        project = linked_summary("bioproject", "3", {"project_acc": "PRJNA123"})
        self.assertEqual(assembly[0], "GCF_000001.1")
        self.assertEqual(assembly[2], "Complete Genome")
        self.assertEqual(sra[0], "SRR123; ERR456")
        self.assertEqual(project[0], "PRJNA123")

    def test_sra_metadata_recovers_project_and_wgs_layout(self) -> None:
        metadata = sra_metadata(
            '{"expxml":"<Study acc=\\"SRP1\\"></Study><LIBRARY_STRATEGY>WGS</LIBRARY_STRATEGY>'
            '<LIBRARY_SOURCE>GENOMIC</LIBRARY_SOURCE><LIBRARY_LAYOUT><PAIRED/></LIBRARY_LAYOUT>'
            '<Bioproject>PRJNA123</Bioproject>","runs":"<Run acc=\\"SRR1\\" total_bases=\\"5000\\"/>"}'
        )
        self.assertEqual(metadata["bioproject"], "PRJNA123")
        self.assertEqual(metadata["library_strategy"], "WGS")
        self.assertEqual(metadata["library_layout"], "paired")
        self.assertEqual(metadata["runs"], {"SRR1": "5000"})

    def test_assembly_selection_prefers_level_before_refseq(self) -> None:
        complete_gca = {
            "assembly_level": "Complete Genome",
            "assembly_source": "GenBank",
            "assembly_contig_n50": "4000000",
            "assembly_total_length": "4000000",
            "resource_accession": "GCA_1",
        }
        scaffold_gcf = {
            "assembly_level": "Scaffold",
            "assembly_source": "RefSeq",
            "assembly_contig_n50": "500000",
            "assembly_total_length": "4000000",
            "resource_accession": "GCF_1",
        }
        self.assertGreater(assembly_rank(complete_gca), assembly_rank(scaffold_gcf))

    def test_cache_max_age_rejects_stale_entry_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = NcbiClient(
                email="test@example.org",
                cache_dir=Path(directory),
                offline_cache_only=True,
                cache_max_age_hours=1,
            )
            params = {"db": "biosample", "term": "NCPPB", "retmode": "xml"}
            cache = client.cache_path("esearch", {**params, "email": client.email, "tool": "ncppb_audit_v2"})
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text("<eSearchResult/>", encoding="utf-8")
            old = time.time() - 7200
            os.utime(cache, (old, old))
            with self.assertRaisesRegex(RuntimeError, "expired"):
                client.request("esearch", params)

    def test_verified_resource_seed_requires_accepted_biosample(self) -> None:
        matches = [{"ncppb_number": "NCPPB 45", "biosample_accession": "SAMN1", "decision": "accept"}]
        seed = [{
            "ncppb_number": "NCPPB 45",
            "biosample_accession": "SAMN1",
            "linked_database": "assembly",
            "linked_accession": "GCF_000001.1",
            "verification_status": "verified_against_biosample",
            "provenance": "PhytoBacExplorer comparison",
        }]
        merged = merge_verified_resource_seeds([], seed, matches)
        self.assertEqual(merged[0]["link_method"], "verified_external_seed")
        with self.assertRaisesRegex(ValueError, "verification_status"):
            merge_verified_resource_seeds([], [{**seed[0], "verification_status": "pending"}], matches)


if __name__ == "__main__":
    unittest.main()
