from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "03_ncbi_smoke_test.py"
SPEC = importlib.util.spec_from_file_location("ncbi_smoke_test", SCRIPT_PATH)
ncbi_smoke_test = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = ncbi_smoke_test
SPEC.loader.exec_module(ncbi_smoke_test)

HARVEST_PATH = Path(__file__).resolve().parents[1] / "scripts" / "03_ncbi_harvest_candidates.py"
HARVEST_SPEC = importlib.util.spec_from_file_location("ncbi_harvest_candidates", HARVEST_PATH)
ncbi_harvest = importlib.util.module_from_spec(HARVEST_SPEC)
assert HARVEST_SPEC.loader is not None
sys.modules[HARVEST_SPEC.name] = ncbi_harvest
HARVEST_SPEC.loader.exec_module(ncbi_harvest)

CLASSIFY_PATH = Path(__file__).resolve().parents[1] / "scripts" / "04_ncbi_classify_candidates.py"
CLASSIFY_SPEC = importlib.util.spec_from_file_location("ncbi_classify_candidates", CLASSIFY_PATH)
ncbi_classify = importlib.util.module_from_spec(CLASSIFY_SPEC)
assert CLASSIFY_SPEC.loader is not None
sys.modules[CLASSIFY_SPEC.name] = ncbi_classify
CLASSIFY_SPEC.loader.exec_module(ncbi_classify)

GROUP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "05_ncbi_group_record_sets.py"
GROUP_SPEC = importlib.util.spec_from_file_location("ncbi_group_record_sets", GROUP_PATH)
ncbi_group = importlib.util.module_from_spec(GROUP_SPEC)
assert GROUP_SPEC.loader is not None
sys.modules[GROUP_SPEC.name] = ncbi_group
GROUP_SPEC.loader.exec_module(ncbi_group)

HTML_KEYWORD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "02_extract_html_keyword_audit.py"
HTML_KEYWORD_SPEC = importlib.util.spec_from_file_location("html_keyword_audit", HTML_KEYWORD_PATH)
html_keyword_audit = importlib.util.module_from_spec(HTML_KEYWORD_SPEC)
assert HTML_KEYWORD_SPEC.loader is not None
sys.modules[HTML_KEYWORD_SPEC.name] = html_keyword_audit
HTML_KEYWORD_SPEC.loader.exec_module(html_keyword_audit)

FILTER_BIOSAMPLE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "11_filter_biosample_raw.py"
FILTER_BIOSAMPLE_SPEC = importlib.util.spec_from_file_location("filter_biosample_raw", FILTER_BIOSAMPLE_PATH)
filter_biosample = importlib.util.module_from_spec(FILTER_BIOSAMPLE_SPEC)
assert FILTER_BIOSAMPLE_SPEC.loader is not None
sys.modules[FILTER_BIOSAMPLE_SPEC.name] = filter_biosample
FILTER_BIOSAMPLE_SPEC.loader.exec_module(filter_biosample)


IDENTIFIER_EXTRACT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "09_extract_other_reference_identifiers.py"
IDENTIFIER_EXTRACT_SPEC = importlib.util.spec_from_file_location("other_reference_identifiers", IDENTIFIER_EXTRACT_PATH)
other_reference_identifiers = importlib.util.module_from_spec(IDENTIFIER_EXTRACT_SPEC)
assert IDENTIFIER_EXTRACT_SPEC.loader is not None
sys.modules[IDENTIFIER_EXTRACT_SPEC.name] = other_reference_identifiers
IDENTIFIER_EXTRACT_SPEC.loader.exec_module(other_reference_identifiers)

BIOSAMPLE_HARVEST_PATH = Path(__file__).resolve().parents[1] / "scripts" / "10_harvest_biosample_raw.py"
BIOSAMPLE_HARVEST_SPEC = importlib.util.spec_from_file_location("biosample_harvest", BIOSAMPLE_HARVEST_PATH)
biosample_harvest = importlib.util.module_from_spec(BIOSAMPLE_HARVEST_SPEC)
assert BIOSAMPLE_HARVEST_SPEC.loader is not None
sys.modules[BIOSAMPLE_HARVEST_SPEC.name] = biosample_harvest
BIOSAMPLE_HARVEST_SPEC.loader.exec_module(biosample_harvest)

REJECTION_ANALYSIS_PATH = Path(__file__).resolve().parents[1] / "scripts" / "14_analyze_biosample_rejections.py"
REJECTION_ANALYSIS_SPEC = importlib.util.spec_from_file_location("biosample_rejection_analysis", REJECTION_ANALYSIS_PATH)
biosample_rejection_analysis = importlib.util.module_from_spec(REJECTION_ANALYSIS_SPEC)
assert REJECTION_ANALYSIS_SPEC.loader is not None
sys.modules[REJECTION_ANALYSIS_SPEC.name] = biosample_rejection_analysis
REJECTION_ANALYSIS_SPEC.loader.exec_module(biosample_rejection_analysis)

RAW_AUDIT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "15_audit_biosample_raw_candidates.py"
RAW_AUDIT_SPEC = importlib.util.spec_from_file_location("biosample_raw_audit", RAW_AUDIT_PATH)
biosample_raw_audit = importlib.util.module_from_spec(RAW_AUDIT_SPEC)
assert RAW_AUDIT_SPEC.loader is not None
sys.modules[RAW_AUDIT_SPEC.name] = biosample_raw_audit
RAW_AUDIT_SPEC.loader.exec_module(biosample_raw_audit)

SEARCH_REVIEW_PATH = Path(__file__).resolve().parents[1] / "scripts" / "17_build_search_result_review_table.py"
SEARCH_REVIEW_SPEC = importlib.util.spec_from_file_location("search_result_review", SEARCH_REVIEW_PATH)
search_result_review = importlib.util.module_from_spec(SEARCH_REVIEW_SPEC)
assert SEARCH_REVIEW_SPEC.loader is not None
sys.modules[SEARCH_REVIEW_SPEC.name] = search_result_review
SEARCH_REVIEW_SPEC.loader.exec_module(search_result_review)

MANUAL_REVIEW_PATH = Path(__file__).resolve().parents[1] / "scripts" / "18_assist_manual_biosample_review.py"
MANUAL_REVIEW_SPEC = importlib.util.spec_from_file_location("assist_manual_biosample_review", MANUAL_REVIEW_PATH)
assist_manual_review = importlib.util.module_from_spec(MANUAL_REVIEW_SPEC)
assert MANUAL_REVIEW_SPEC.loader is not None
sys.modules[MANUAL_REVIEW_SPEC.name] = assist_manual_review
MANUAL_REVIEW_SPEC.loader.exec_module(assist_manual_review)

ALL_FIELDS_ANALYSIS_PATH = Path(__file__).resolve().parents[1] / "scripts" / "19_analyze_rejected_all_fields_keywords.py"
ALL_FIELDS_ANALYSIS_SPEC = importlib.util.spec_from_file_location("all_fields_keyword_analysis", ALL_FIELDS_ANALYSIS_PATH)
all_fields_analysis = importlib.util.module_from_spec(ALL_FIELDS_ANALYSIS_SPEC)
assert ALL_FIELDS_ANALYSIS_SPEC.loader is not None
sys.modules[ALL_FIELDS_ANALYSIS_SPEC.name] = all_fields_analysis
ALL_FIELDS_ANALYSIS_SPEC.loader.exec_module(all_fields_analysis)

METADATA_ANALYSIS_PATH = Path(__file__).resolve().parents[1] / "scripts" / "20_analyze_rejected_biosample_metadata.py"
METADATA_ANALYSIS_SPEC = importlib.util.spec_from_file_location("rejected_biosample_metadata_analysis", METADATA_ANALYSIS_PATH)
metadata_analysis = importlib.util.module_from_spec(METADATA_ANALYSIS_SPEC)
assert METADATA_ANALYSIS_SPEC.loader is not None
sys.modules[METADATA_ANALYSIS_SPEC.name] = metadata_analysis
METADATA_ANALYSIS_SPEC.loader.exec_module(metadata_analysis)


class CandidateClassificationTests(unittest.TestCase):
    def test_accepts_exact_ncppb_identifier(self) -> None:
        context = ncbi_smoke_test.make_strain_context({"ncppb_number": "NCPPB 45"})
        metadata = {
            "organism": "Xanthomonas campestris pv. campestris",
            "metadata_text": "Genome sequencing of Xcc WHRI 6379 (NCPPB 45)",
        }

        result = ncbi_smoke_test.classify_candidate(context, metadata)

        self.assertEqual(result.evidence_level, "strong_strain_match")
        self.assertEqual(result.matched_identifier, "NCPPB 45")
        self.assertEqual(result.matched_identifier_type, "ncppb_number")
        self.assertEqual(result.reject_reason, "")

    def test_rejects_conflicting_ncppb_identifier(self) -> None:
        context = ncbi_smoke_test.make_strain_context({"ncppb_number": "NCPPB 45"})
        metadata = {
            "organism": "Xanthomonas graminis pv. graminis",
            "metadata_text": "Draft genome sequence of Xanthomonas graminis NCPPB 3709",
        }

        result = ncbi_smoke_test.classify_candidate(context, metadata)

        self.assertEqual(result.evidence_level, "ambiguous")
        self.assertEqual(result.reject_reason, "conflicting_ncppb_number:3709")

    def test_rejects_non_xanthomonas_record_with_unrelated_number(self) -> None:
        context = ncbi_smoke_test.make_strain_context({"ncppb_number": "NCPPB 45"})
        metadata = {
            "organism": "Ralstonia solanacearum",
            "metadata_text": "NCPPB_Number NCPPB 1584 Replicate 45",
        }

        result = ncbi_smoke_test.classify_candidate(context, metadata)

        self.assertEqual(result.evidence_level, "ambiguous")
        self.assertEqual(result.reject_reason, "non_xanthomonas_organism")

    def test_accepts_equivalent_collection_number(self) -> None:
        context = ncbi_smoke_test.make_strain_context(
            {"ncppb_number": "NCPPB 101", "other_collection_numbers": "ICMP 204; LMG 673"}
        )
        metadata = {
            "organism": "Xanthomonas cassavae",
            "metadata_text": "Microbe sample from Xanthomonas cassavae strain ICMP 204",
        }

        result = ncbi_smoke_test.classify_candidate(context, metadata)

        self.assertEqual(result.evidence_level, "strong_strain_match")
        self.assertEqual(result.matched_identifier, "ICMP 204")
        self.assertEqual(result.matched_identifier_type, "other_collection_number")

    def test_marks_xanthomonas_without_strain_identifier_as_taxon_only(self) -> None:
        context = ncbi_smoke_test.make_strain_context({"ncppb_number": "NCPPB 45"})
        metadata = {
            "organism": "Xanthomonas campestris pv. campestris",
            "metadata_text": "Xanthomonas campestris pv. campestris genome assembly",
        }

        result = ncbi_smoke_test.classify_candidate(context, metadata)

        self.assertEqual(result.evidence_level, "taxon_level_only")
        self.assertEqual(result.reject_reason, "no_exact_strain_identifier_match")

    def test_split_keeps_only_strong_matches_in_match_output(self) -> None:
        rows = [
            {"status": "ok", "evidence_level": "strong_strain_match", "ncbi_accession": "SAMN36346970"},
            {"status": "ok", "evidence_level": "ambiguous", "reject_reason": "conflicting_ncppb_number:3709"},
            {"status": "ok", "evidence_level": "taxon_level_only", "reject_reason": "no_exact_strain_identifier_match"},
            {"status": "error", "evidence_level": "ambiguous", "reject_reason": "query_error"},
        ]

        matches, review = ncbi_smoke_test.split_match_review_rows(rows)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["ncbi_accession"], "SAMN36346970")
        self.assertEqual(len(review), 3)

    def test_fallback_exact_identifier_requires_review(self) -> None:
        context = ncbi_smoke_test.make_strain_context({"ncppb_number": "NCPPB 45"})
        query = ncbi_smoke_test.QuerySpec(
            tier="tier3_taxon_fallback",
            label="taxon_plus_number",
            db="biosample",
            term="Xanthomonas[All Fields] AND 45[All Fields]",
            allow_match=False,
        )
        summary = {
            "accession": "SAMN00000000",
            "title": "Genome sequencing of Xcc WHRI 6379 (NCPPB 45)",
            "organism": "Xanthomonas campestris pv. campestris",
            "taxonomy": "340",
            "identifiers": "BioSample: SAMN00000000",
            "infraspecies": "strain: WHRI 6379 (NCPPB 45)",
            "sampledata": "<BioSample></BioSample>",
        }

        row = ncbi_smoke_test.build_candidate_row(context, query, "1", summary, 1)

        self.assertEqual(row["evidence_level"], "probable_strain_match")
        self.assertEqual(row["reject_reason"], "fallback_requires_manual_review")

    def test_harvest_keywords_use_only_identifiers(self) -> None:
        context = ncbi_smoke_test.make_strain_context(
            {
                "ncppb_number": "NCPPB 101",
                "current_name": "Xanthomonas cassavae (ex Wiehe & Dowson 1953) Vauterin et al. 1995",
                "name_as_received": "X. cassavae.",
                "alternative_names": "Xanthomonas campestris pv. cassavae",
                "other_collection_numbers": "ICMP 204",
                "other_references": "This isolate is also in the collections; ICMP 204",
            }
        )

        keywords = ncbi_smoke_test.build_harvest_keywords(context)
        keyword_pairs = {(keyword.source, keyword.value) for keyword in keywords}

        self.assertIn(("ncppb_number", "NCPPB 101"), keyword_pairs)
        self.assertIn(("other_collection_number", "ICMP 204"), keyword_pairs)
        self.assertNotIn(("catalogue_name", "Xanthomonas cassavae (ex Wiehe & Dowson 1953) Vauterin et al. 1995"), keyword_pairs)
        self.assertNotIn(("name_as_received", "X. cassavae."), keyword_pairs)
        self.assertNotIn(("other_name", "Xanthomonas campestris pv. cassavae"), keyword_pairs)
        self.assertNotIn(("other_references", "This isolate is also in the collections"), keyword_pairs)
        self.assertNotIn(("ncppb_number", "NCPPB101"), keyword_pairs)
        self.assertNotIn(("other_collection_number", "ICMP204"), keyword_pairs)

    def test_other_references_collection_numbers_become_identifiers(self) -> None:
        context = ncbi_smoke_test.make_strain_context(
            {
                "ncppb_number": "NCPPB 101",
                "other_collection_numbers": "",
                "other_references": "This isolate is also in the collections; ICMP 204, LMG 673, DSM 18958",
            }
        )
        metadata = {
            "organism": "Xanthomonas cassavae",
            "metadata_text": "Xanthomonas cassavae strain LMG 673",
        }

        result = ncbi_smoke_test.classify_candidate(context, metadata)
        keywords = ncbi_smoke_test.build_harvest_keywords(context)
        keyword_pairs = {(keyword.source, keyword.value) for keyword in keywords}

        self.assertEqual(result.evidence_level, "strong_strain_match")
        self.assertEqual(result.matched_identifier, "LMG 673")
        self.assertEqual(result.matched_identifier_type, "other_reference_identifier")
        self.assertIn(("other_reference_identifier", "ICMP 204"), keyword_pairs)
        self.assertIn(("other_reference_identifier", "LMG 673"), keyword_pairs)
        self.assertIn(("other_reference_identifier", "DSM 18958"), keyword_pairs)

    def test_other_references_extract_donor_reference_ids(self) -> None:
        context = ncbi_smoke_test.make_strain_context(
            {
                "ncppb_number": "NCPPB 999",
                "other_references": "The donor reference is NBC5720. This isolate was isolated by Harrie Koenraadt.",
            }
        )

        keywords = ncbi_smoke_test.build_harvest_keywords(context)
        keyword_pairs = {(keyword.source, keyword.value) for keyword in keywords}

        self.assertIn(("other_reference_identifier", "NBC 5720"), keyword_pairs)

    def test_harvest_queries_use_all_fields_and_biosample_only(self) -> None:
        context = ncbi_smoke_test.make_strain_context(
            {
                "ncppb_number": "NCPPB 45",
                "current_name": "Xanthomonas campestris pv. campestris",
            }
        )

        queries = ncbi_smoke_test.build_harvest_queries(context, ncbi_smoke_test.HARVEST_DBS)
        query_terms = {query.term for query in queries}

        self.assertEqual(ncbi_smoke_test.HARVEST_DBS, ["biosample"])
        self.assertTrue(all(query.tier == "recall_harvest" for query in queries))
        self.assertTrue(all(query.db == "biosample" for query in queries))
        self.assertIn("NCPPB[All Fields] AND 45[All Fields]", query_terms)
        self.assertNotIn("Xanthomonas campestris pv. campestris", query_terms)
        self.assertNotIn("NCPPB45", query_terms)
        self.assertNotIn("NCPPB:45", query_terms)
        self.assertTrue(all(" AND " in query.term for query in queries))

    def test_output_columns_do_not_include_search_keywords(self) -> None:
        columns = ncbi_smoke_test.output_columns()

        self.assertNotIn("query_tier", columns)
        self.assertNotIn("query_label", columns)
        self.assertNotIn("search_term", columns)
        self.assertNotIn("id_count_returned", columns)

    def test_raw_output_columns_keep_query_and_metadata_text(self) -> None:
        columns = ncbi_harvest.raw_output_columns()

        self.assertIn("query_label", columns)
        self.assertIn("search_term", columns)
        self.assertIn("metadata_text", columns)
        self.assertIn("id_count_returned", columns)

    def test_classify_raw_row_accepts_exact_identifier(self) -> None:
        context = ncbi_smoke_test.make_strain_context({"ncppb_number": "NCPPB 45"})
        raw_row = {
            "ncppb_number": "NCPPB 45",
            "ncbi_db": "biosample",
            "ncbi_uid": "36346970",
            "ncbi_accession": "SAMN36346970",
            "data_type": "BioSample",
            "organism": "Xanthomonas campestris pv. campestris",
            "metadata_text": "Genome sequencing of Xcc WHRI 6379 (NCPPB 45)",
            "status": "ok",
        }

        row = ncbi_classify.classify_raw_row(context, raw_row)

        self.assertEqual(row["evidence_level"], "strong_strain_match")
        self.assertEqual(row["matched_identifier"], "NCPPB 45")
        self.assertNotIn("search_term", row)

    def test_classify_promotes_records_linked_to_accepted_biosample(self) -> None:
        rows = [
            {
                "ncppb_number": "NCPPB 45",
                "ncbi_db": "biosample",
                "ncbi_accession": "SAMN36346970",
                "biosample_accession": "SAMN36346970",
                "status": "ok",
                "evidence_level": "strong_strain_match",
                "matched_identifier": "NCPPB 45",
                "matched_identifier_type": "ncppb_number",
                "reject_reason": "",
            },
            {
                "ncppb_number": "NCPPB 45",
                "ncbi_db": "assembly",
                "ncbi_accession": "GCA_035026565.1",
                "biosample_accession": "SAMN36346970",
                "status": "ok",
                "evidence_level": "taxon_level_only",
                "matched_identifier": "",
                "matched_identifier_type": "",
                "reject_reason": "no_exact_strain_identifier_match",
                "evidence_text": "assembly linked to BioSample",
            },
        ]

        promoted = ncbi_classify.promote_rows_linked_to_accepted_biosamples(rows)

        self.assertEqual(promoted[1]["evidence_level"], "strong_strain_match")
        self.assertEqual(promoted[1]["matched_identifier"], "NCPPB 45")
        self.assertEqual(promoted[1]["matched_identifier_type"], "linked_accepted_biosample")
        self.assertEqual(promoted[1]["linked_from_accession"], "SAMN36346970")

    def test_group_matches_uses_biosample_as_record_set(self) -> None:
        rows = [
            {
                "ncppb_number": "NCPPB 45",
                "ncbi_db": "biosample",
                "ncbi_accession": "SAMN36346970",
                "data_type": "BioSample",
                "matched_identifier": "NCPPB 45",
                "matched_identifier_type": "ncppb_number",
                "biosample_accession": "SAMN36346970",
                "organism": "Xanthomonas campestris pv. campestris",
                "taxid": "340",
                "source_url": "https://www.ncbi.nlm.nih.gov/biosample/SAMN36346970",
            },
            {
                "ncppb_number": "NCPPB 45",
                "ncbi_db": "assembly",
                "ncbi_accession": "GCA_035026565.1",
                "data_type": "Assembly",
                "matched_identifier": "NCPPB 45",
                "matched_identifier_type": "ncppb_number",
                "biosample_accession": "SAMN36346970",
                "assembly_level": "Contig",
                "organism": "Xanthomonas campestris pv. campestris",
                "taxid": "340",
                "source_url": "https://www.ncbi.nlm.nih.gov/assembly/GCA_035026565.1",
            },
            {
                "ncppb_number": "NCPPB 45",
                "ncbi_db": "sra",
                "ncbi_accession": "SRX20931011",
                "data_type": "SRA:WGS",
                "matched_identifier": "NCPPB 45",
                "matched_identifier_type": "ncppb_number",
                "biosample_accession": "SAMN36346970",
                "sra_library_strategy": "WGS",
                "organism": "Xanthomonas campestris pv. campestris",
                "taxid": "340",
                "source_url": "https://www.ncbi.nlm.nih.gov/sra/SRX20931011",
            },
        ]

        grouped = ncbi_group.group_matches(rows)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["record_set_id"], "SAMN36346970")
        self.assertEqual(grouped[0]["record_count"], 3)
        self.assertEqual(grouped[0]["best_data_category"], "draft_assembly_available")
        self.assertEqual(grouped[0]["assembly_accessions"], "GCA_035026565.1")
        self.assertEqual(grouped[0]["sra_accessions"], "SRX20931011")

    def test_strain_summary_marks_unmatched_strains_as_no_confirmed_data(self) -> None:
        record_sets = [
            {
                "ncppb_number": "NCPPB 45",
                "best_data_category": "draft_assembly_available",
                "biosample_accessions": "SAMN36346970",
                "assembly_accessions": "GCA_035026565.1",
                "assembly_levels": "Contig",
                "sra_accessions": "SRX20931011",
            }
        ]
        review_rows = [
            {
                "ncppb_number": "NCPPB 109",
                "evidence_level": "no_public_data_found",
                "reject_reason": "no_accepted_strain_level_match",
            }
        ]

        summaries = ncbi_group.strain_summary(
            ["NCPPB 45", "NCPPB 109"],
            {
                "NCPPB 45": {"current_name": "Xanthomonas campestris"},
                "NCPPB 109": {"current_name": "Xanthomonas sp."},
            },
            record_sets,
            review_rows,
        )

        self.assertEqual(summaries[0]["best_audit_category"], "draft_assembly_available")
        self.assertEqual(summaries[0]["confirmed_record_sets"], 1)
        self.assertEqual(summaries[1]["best_audit_category"], "no_confirmed_public_data_found")
        self.assertEqual(summaries[1]["confirmed_record_sets"], 0)

    def test_html_keyword_audit_keeps_all_visible_labels(self) -> None:
        html = """
        <table>
          <tr>
            <td><a href="furtherinfo.cfm?ncppb_no=101">101</a></td>
            <td><strong>Catalogue name:</strong></td>
            <td>Xanthomonas cassavae</td>
          </tr>
          <tr>
            <td>
              <table>
                <tr><td><strong>Name as received:</strong></td><td>Xanthomonas cassavae</td></tr>
                <tr><td><strong>Other references:</strong></td><td>This isolate is also in the collections; ICMP 204</td></tr>
                <tr><td><strong>Unexpected label:</strong></td><td>Unexpected visible value</td></tr>
              </table>
            </td>
          </tr>
        </table>
        """

        rows = html_keyword_audit.parse_html_keyword_rows(html)
        observed = {(row["source_label"], row["keyword"]) for row in rows}

        self.assertIn(("ncppb_number", "NCPPB 101"), observed)
        self.assertIn(("catalogue_name", "Xanthomonas cassavae"), observed)
        self.assertIn(("name_as_received", "Xanthomonas cassavae"), observed)
        self.assertIn(("other_references", "This isolate is also in the collections; ICMP 204"), observed)
        self.assertIn(("unexpected_label", "Unexpected visible value"), observed)
        self.assertIn(("collection_identifier", "ICMP 204"), observed)

    def test_script11_accepts_exact_ncppb_identifier(self) -> None:
        identifier_rows = [{"ncppb_number": "NCPPB 45", "include_for_search": "no"}]
        patterns = filter_biosample.build_patterns(identifier_rows, include_ncppb_number=True)
        row = {
            "ncppb_number": "NCPPB 45",
            "status": "ok",
            "organism": "Xanthomonas campestris pv. campestris",
            "metadata_text": "Genome sequencing of Xcc WHRI 6379 (NCPPB 45)",
        }

        evidence = filter_biosample.classify_row(row, patterns["NCPPB 45"])

        self.assertEqual(evidence.evidence_decision, "accept")
        self.assertEqual(evidence.evidence_class, "confirmed_ncppb_identifier")
        self.assertEqual(evidence.evidence_score, 100)
        self.assertEqual(evidence.matched_identifier, "NCPPB 45")

    def test_script11_accepts_known_collection_identifier(self) -> None:
        identifier_rows = [
            {
                "ncppb_number": "NCPPB 101",
                "normalized_identifier": "LMG 673",
                "rule_name": "known_collection_prefix",
                "confidence": "high",
                "include_for_search": "yes",
            }
        ]
        patterns = filter_biosample.build_patterns(identifier_rows, include_ncppb_number=True)
        row = {
            "ncppb_number": "NCPPB 101",
            "status": "ok",
            "organism": "Xanthomonas cassavae",
            "metadata_text": "Microbe sample from Xanthomonas cassavae strain LMG 673",
        }

        evidence = filter_biosample.classify_row(row, patterns["NCPPB 101"])

        self.assertEqual(evidence.evidence_decision, "accept")
        self.assertEqual(evidence.evidence_class, "confirmed_equivalent_collection_identifier")
        self.assertEqual(evidence.matched_identifier, "LMG 673")

    def test_script11_sends_local_identifier_only_to_review(self) -> None:
        identifier_rows = [
            {
                "ncppb_number": "NCPPB 999",
                "normalized_identifier": "NBC 5720",
                "rule_name": "contextual_reference_code",
                "confidence": "medium",
                "include_for_search": "yes",
            }
        ]
        patterns = filter_biosample.build_patterns(identifier_rows, include_ncppb_number=True)
        row = {
            "ncppb_number": "NCPPB 999",
            "status": "ok",
            "organism": "Xanthomonas sp.",
            "metadata_text": "Xanthomonas sp. isolate NBC5720",
        }

        evidence = filter_biosample.classify_row(row, patterns["NCPPB 999"])

        self.assertEqual(evidence.evidence_decision, "review")
        self.assertEqual(evidence.evidence_level, "probable_strain_match")
        self.assertEqual(evidence.evidence_class, "review_local_or_donor_identifier_only")
        self.assertEqual(evidence.matched_identifier, "NBC 5720")

    def test_script11_conflicting_ncppb_number_overrides_identifier_match(self) -> None:
        identifier_rows = [{"ncppb_number": "NCPPB 45", "include_for_search": "no"}]
        patterns = filter_biosample.build_patterns(identifier_rows, include_ncppb_number=True)
        row = {
            "ncppb_number": "NCPPB 45",
            "status": "ok",
            "organism": "Xanthomonas campestris",
            "metadata_text": "Mixed metadata mentions NCPPB 45 and NCPPB 3709",
        }

        evidence = filter_biosample.classify_row(row, patterns["NCPPB 45"])

        self.assertEqual(evidence.evidence_decision, "reject")
        self.assertEqual(evidence.evidence_class, "reject_conflicting_identifier")
        self.assertEqual(evidence.reject_reason, "conflicting_ncppb_number:3709")

    def test_script11_rejects_weak_identifier_in_non_xanthomonas_record(self) -> None:
        identifier_rows = [
            {
                "ncppb_number": "NCPPB 999",
                "normalized_identifier": "NBC 5720",
                "rule_name": "contextual_reference_code",
                "confidence": "medium",
                "include_for_search": "yes",
            }
        ]
        patterns = filter_biosample.build_patterns(identifier_rows, include_ncppb_number=True)
        row = {
            "ncppb_number": "NCPPB 999",
            "status": "ok",
            "organism": "Ralstonia solanacearum",
            "metadata_text": "Ralstonia solanacearum isolate NBC5720",
        }

        evidence = filter_biosample.classify_row(row, patterns["NCPPB 999"])

        self.assertEqual(evidence.evidence_decision, "reject")
        self.assertEqual(evidence.evidence_class, "reject_weak_identifier_non_target_organism")
        self.assertEqual(evidence.matched_identifier, "NBC 5720")

    def test_script11_reviews_strong_identifier_in_non_xanthomonas_record(self) -> None:
        identifier_rows = [{"ncppb_number": "NCPPB 45", "include_for_search": "no"}]
        patterns = filter_biosample.build_patterns(identifier_rows, include_ncppb_number=True)
        row = {
            "ncppb_number": "NCPPB 45",
            "status": "ok",
            "organism": "Ralstonia solanacearum",
            "metadata_text": "Possible mislabeled metadata for NCPPB 45",
        }

        evidence = filter_biosample.classify_row(row, patterns["NCPPB 45"])

        self.assertEqual(evidence.evidence_decision, "review")
        self.assertEqual(evidence.evidence_class, "review_strong_identifier_non_target_organism")
        self.assertEqual(evidence.matched_identifier, "NCPPB 45")


    def test_script09_excludes_single_letter_local_codes_from_search(self) -> None:
        candidates = other_reference_identifiers.extract_candidates(
            "NCPPB 273",
            "The donor reference is B67. This isolate was isolated by a local submitter.",
        )
        observed = {candidate.normalized_identifier: candidate for candidate in candidates}

        self.assertIn("B 67", observed)
        self.assertEqual(observed["B 67"].confidence, "low")
        self.assertEqual(observed["B 67"].include_for_search, "no")
        self.assertEqual(observed["B 67"].biosample_query, "")

    def test_script09_known_collection_queries_use_text_word(self) -> None:
        candidates = other_reference_identifiers.extract_candidates(
            "NCPPB 101",
            "This isolate is also in the collections; ICMP 204, LMG 673.",
        )
        observed = {candidate.normalized_identifier: candidate for candidate in candidates}

        self.assertEqual(observed["ICMP 204"].rule_name, "known_collection_prefix")
        self.assertEqual(observed["ICMP 204"].include_for_search, "yes")
        self.assertIn("ICMP[Text Word]", observed["ICMP 204"].biosample_query)
        self.assertNotIn("[All Fields]", observed["ICMP 204"].biosample_query)

    def test_script10_strict_profile_uses_text_word_and_organism_filter(self) -> None:
        rows = [
            {
                "ncppb_number": "NCPPB 45",
                "include_for_search": "yes",
                "normalized_identifier": "ICMP 204",
                "prefix": "ICMP",
                "suffix": "204",
                "rule_name": "known_collection_prefix",
                "confidence": "high",
            }
        ]

        specs = biosample_harvest.query_specs(
            rows,
            include_ncppb_number=True,
            query_profile="strict_xanthomonas",
            target_organism="Xanthomonas",
        )
        terms = {spec["search_term"] for spec in specs}

        self.assertIn("(NCPPB[Text Word] AND 45[Text Word]) AND Xanthomonas[Organism]", terms)
        self.assertIn("(ICMP[Text Word] AND 204[Text Word]) AND Xanthomonas[Organism]", terms)
        self.assertTrue(all("[All Fields]" not in term for term in terms))
        self.assertTrue(all(spec["query_profile"] == "strict_xanthomonas" for spec in specs))

    def test_script10_current_all_fields_profile_is_reproducible_only(self) -> None:
        rows = [
            {
                "ncppb_number": "NCPPB 45",
                "include_for_search": "yes",
                "normalized_identifier": "ICMP 204",
                "prefix": "ICMP",
                "suffix": "204",
                "rule_name": "known_collection_prefix",
                "confidence": "high",
                "biosample_query": "ICMP[All Fields] AND 204[All Fields]",
            }
        ]

        specs = biosample_harvest.query_specs(
            rows,
            include_ncppb_number=True,
            query_profile="current_all_fields",
            target_organism="Xanthomonas",
        )
        terms = {spec["search_term"] for spec in specs}

        self.assertIn("NCPPB[All Fields] AND 45[All Fields]", terms)
        self.assertIn("ICMP[All Fields] AND 204[All Fields]", terms)

    def test_script10_known_collection_strict_skips_local_codes(self) -> None:
        rows = [
            {
                "ncppb_number": "NCPPB 101",
                "include_for_search": "yes",
                "normalized_identifier": "ICMP 204",
                "prefix": "ICMP",
                "suffix": "204",
                "rule_name": "known_collection_prefix",
                "confidence": "high",
            },
            {
                "ncppb_number": "NCPPB 273",
                "include_for_search": "yes",
                "normalized_identifier": "B 67",
                "prefix": "B",
                "suffix": "67",
                "rule_name": "source_context_single_letter_code",
                "confidence": "low",
            },
        ]

        specs = biosample_harvest.query_specs(
            rows,
            include_ncppb_number=False,
            query_profile="known_collection_strict",
            target_organism="Xanthomonas",
        )

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["normalized_identifier"], "ICMP 204")
        self.assertNotIn("B[Text Word]", specs[0]["search_term"])

    def test_script10_raw_output_columns_include_query_diagnostics(self) -> None:
        columns = biosample_harvest.output_columns()

        self.assertIn("query_profile", columns)
        self.assertIn("rule_name", columns)
        self.assertIn("confidence", columns)
        self.assertIn("target_organism_filter", columns)
        self.assertIn("count_returned", columns)
        self.assertIn("ids_fetched", columns)
        self.assertIn("retmax_saturated", columns)
        self.assertIn("id_count_returned", columns)

    def test_script14_builds_rejection_analysis_tables(self) -> None:
        matches = [
            {
                "ncppb_number": "NCPPB 101",
                "search_term": "ICMP[All Fields] AND 204[All Fields]",
                "prefix": "ICMP",
                "query_source": "other_reference",
            }
        ]
        review = [
            {
                "ncppb_number": "NCPPB 273",
                "search_term": "B[All Fields] AND 67[All Fields]",
                "prefix": "B",
                "query_source": "other_reference",
                "reject_reason": "non_xanthomonas_organism",
                "status": "ok",
                "organism": "Homo sapiens",
                "title": "Human sample",
            },
            {
                "ncppb_number": "NCPPB 3615",
                "search_term": "XCC[All Fields] AND 3[All Fields]",
                "prefix": "XCC",
                "query_source": "other_reference",
                "evidence_level": "taxon_level_only",
                "reject_reason": "no_exact_strain_identifier_match",
                "ncbi_accession": "SAMN0001",
            },
            {
                "ncppb_number": "NCPPB 45",
                "search_term": "NCPPB[All Fields] AND 45[All Fields]",
                "prefix": "NCPPB",
                "query_source": "ncppb_number",
                "evidence_level": "ambiguous",
                "reject_reason": "conflicting_ncppb_number:3709",
                "ncbi_accession": "SAMEA0001",
            },
        ]

        tables = biosample_rejection_analysis.build_analysis_tables(matches, review, [])
        reason_rows = tables["rejection_counts_by_reason.tsv"][0]
        manual_rows = tables["manual_review_priority_candidates.tsv"][0]

        self.assertEqual(reason_rows[0]["reject_reason"], "non_xanthomonas_organism")
        self.assertEqual(reason_rows[0]["rows"], 1)
        self.assertEqual({row["priority"] for row in manual_rows}, {"P1_taxon_level_only_check", "P2_conflicting_ncppb_number_check"})

    def test_script15_audits_exact_identifier_as_productive(self) -> None:
        raw_rows = [
            {
                "ncppb_number": "NCPPB 45",
                "query_source": "ncppb_number",
                "search_term": "NCPPB[All Fields] AND 45[All Fields]",
                "status": "ok",
                "organism": "Xanthomonas campestris pv. campestris",
                "metadata_text": "Genome sequencing of Xcc WHRI 6379 (NCPPB 45)",
                "ncbi_accession": "SAMN36346970",
                "ncbi_uid": "36346970",
            }
        ]
        matches = [
            {
                "ncppb_number": "NCPPB 45",
                "search_term": "NCPPB[All Fields] AND 45[All Fields]",
                "status": "ok",
                "ncbi_accession": "SAMN36346970",
                "ncbi_uid": "36346970",
                "evidence_level": "strong_strain_match",
                "matched_identifier": "NCPPB 45",
            }
        ]

        audited = biosample_raw_audit.audit_raw_rows(raw_rows, [{"ncppb_number": "NCPPB 45"}], matches, [])

        self.assertEqual(audited[0]["raw_audit_decision"], "supports_accept")
        self.assertEqual(audited[0]["keyword_match_class"], "target_ncppb_identifier_match")
        self.assertEqual(audited[0]["prior_classification"], "accepted")
        self.assertEqual(audited[0]["keyword_policy_signal"], "productive_exact")

    def test_script15_recommends_disabling_noisy_short_code_prefixes(self) -> None:
        identifiers = [
            {
                "ncppb_number": "NCPPB 273",
                "normalized_identifier": "B 67",
                "prefix": "B",
                "suffix": "67",
                "rule_name": "source_context_single_letter_code",
                "confidence": "low",
                "include_for_search": "no",
            }
        ]
        raw_rows = [
            {
                "ncppb_number": "NCPPB 273",
                "query_source": "other_reference",
                "normalized_identifier": "B 67",
                "prefix": "B",
                "suffix": "67",
                "rule_name": "source_context_single_letter_code",
                "confidence": "low",
                "search_term": "B[All Fields] AND 67[All Fields]",
                "status": "ok",
                "organism": "Homo sapiens",
                "metadata_text": "Human sample B 67",
                "ncbi_accession": f"SAMN{i:05d}",
                "ncbi_uid": str(i),
            }
            for i in range(20)
        ]
        review_rows = [
            {
                "ncppb_number": row["ncppb_number"],
                "search_term": row["search_term"],
                "status": row["status"],
                "ncbi_accession": row["ncbi_accession"],
                "ncbi_uid": row["ncbi_uid"],
                "reject_reason": "non_xanthomonas_organism",
            }
            for row in raw_rows
        ]

        audited = biosample_raw_audit.audit_raw_rows(raw_rows, identifiers, [], review_rows)
        prefix_rows = biosample_raw_audit.prefix_recommendation_rows(audited)

        self.assertTrue(all(row["raw_audit_decision"] == "clear_noise" for row in audited))
        self.assertEqual(prefix_rows[0]["prefix"], "B")
        self.assertEqual(prefix_rows[0]["keyword_policy_recommendation"], "disable_default")

    def test_script15_flags_low_confidence_target_identifier_as_rescue(self) -> None:
        identifiers = [
            {
                "ncppb_number": "NCPPB 273",
                "normalized_identifier": "B 67",
                "prefix": "B",
                "suffix": "67",
                "rule_name": "source_context_single_letter_code",
                "confidence": "low",
                "include_for_search": "no",
            }
        ]
        raw_rows = [
            {
                "ncppb_number": "NCPPB 273",
                "query_source": "other_reference",
                "normalized_identifier": "B 67",
                "prefix": "B",
                "suffix": "67",
                "rule_name": "source_context_single_letter_code",
                "confidence": "low",
                "search_term": "B[All Fields] AND 67[All Fields]",
                "status": "ok",
                "organism": "Xanthomonas campestris",
                "metadata_text": "Xanthomonas campestris isolate B 67",
                "ncbi_accession": "SAMNRESCUE",
            }
        ]

        audited = biosample_raw_audit.audit_raw_rows(raw_rows, identifiers, [], [])
        rescue = biosample_raw_audit.rescue_candidate_rows(audited)

        self.assertEqual(audited[0]["raw_audit_decision"], "possible_false_negative_rescue")
        self.assertEqual(audited[0]["best_identifier_include_for_search"], "no")
        self.assertEqual(rescue[0]["priority"], "P1_low_confidence_identifier_in_target_taxon")

    def test_script15_keeps_target_taxon_query_terms_as_review_only(self) -> None:
        identifiers = [
            {
                "ncppb_number": "NCPPB 3615",
                "normalized_identifier": "XC 3",
                "prefix": "XC",
                "suffix": "3",
                "rule_name": "uppercase_general_code",
                "confidence": "medium",
                "include_for_search": "yes",
            }
        ]
        raw_rows = [
            {
                "ncppb_number": "NCPPB 3615",
                "query_source": "other_reference",
                "normalized_identifier": "XC 3",
                "prefix": "XC",
                "suffix": "3",
                "rule_name": "uppercase_general_code",
                "confidence": "medium",
                "search_term": "XC[All Fields] AND 3[All Fields]",
                "status": "ok",
                "organism": "Xanthomonas campestris",
                "metadata_text": "Xanthomonas campestris XC locus group 3",
                "ncbi_accession": "SAMNQUERYONLY",
            }
        ]

        audited = biosample_raw_audit.audit_raw_rows(raw_rows, identifiers, [], [])
        rescue = biosample_raw_audit.rescue_candidate_rows(audited)

        self.assertEqual(audited[0]["raw_audit_decision"], "supports_review")
        self.assertEqual(audited[0]["keyword_match_class"], "query_terms_present_separately")
        self.assertEqual(rescue[0]["priority"], "P2_target_taxon_query_terms_only")

    def test_script17_builds_confirmed_manual_and_no_confirmed_statuses(self) -> None:
        master = [
            {"ncppb_number": "NCPPB 45", "current_name": "Xanthomonas campestris", "other_references": ""},
            {"ncppb_number": "NCPPB 109", "current_name": "Xanthomonas sp.", "other_references": "Donor ref B67"},
            {"ncppb_number": "NCPPB 211", "current_name": "Xanthomonas sp.", "other_references": ""},
        ]
        identifiers = [
            {
                "ncppb_number": "NCPPB 45",
                "normalized_identifier": "ICMP 204",
                "rule_name": "known_collection_prefix",
                "confidence": "high",
                "include_for_search": "yes",
            },
            {
                "ncppb_number": "NCPPB 109",
                "normalized_identifier": "B 67",
                "rule_name": "source_context_single_letter_code",
                "confidence": "low",
                "include_for_search": "no",
            },
            {"ncppb_number": "NCPPB 211", "rule_name": "no_identifier_found", "include_for_search": "no"},
        ]
        matches = [
            {
                "ncppb_number": "NCPPB 45",
                "ncbi_accession": "SAMN45",
                "organism": "Xanthomonas campestris",
                "title": "NCPPB 45 BioSample",
                "matched_identifier": "NCPPB 45",
                "matched_identifier_type": "ncppb_number",
            }
        ]
        review = [
            {
                "ncppb_number": "NCPPB 109",
                "ncbi_accession": "SAMN109",
                "evidence_level": "ambiguous",
                "reject_reason": "conflicting_ncppb_number:999",
            }
        ]

        rows = search_result_review.build_review_table(master, identifiers, matches, review, [], [])
        observed = {row["ncppb_number"]: row for row in rows}

        self.assertEqual(observed["NCPPB 45"]["search_result_review_status"], "confirmed_biosample_match")
        self.assertEqual(observed["NCPPB 45"]["has_confirmed_biosample"], "yes")
        self.assertEqual(observed["NCPPB 45"]["high_confidence_identifiers"], "ICMP 204")
        self.assertEqual(observed["NCPPB 109"]["search_result_review_status"], "manual_review_required")
        self.assertEqual(observed["NCPPB 109"]["review_priority"], "P2_conflicting_identifier_review")
        self.assertEqual(observed["NCPPB 109"]["manual_only_identifiers"], "B 67")
        self.assertEqual(observed["NCPPB 211"]["search_result_review_status"], "no_confirmed_match_yet")

    def test_script17_flags_accepted_rows_with_raw_audit_conflicts(self) -> None:
        master = [{"ncppb_number": "NCPPB 646", "current_name": "Xanthomonas phaseoli"}]
        matches = [{"ncppb_number": "NCPPB 646", "ncbi_accession": "SAMN03175008"}]
        raw_audit = [
            {
                "ncppb_number": "NCPPB 646",
                "ncbi_accession": "SAMN03175008",
                "prior_classification": "accepted",
                "raw_audit_decision": "supports_review",
                "conflicting_ncppb_numbers": "1646",
            }
        ]

        rows = search_result_review.build_review_table(master, [], matches, [], raw_audit, [])

        self.assertEqual(rows[0]["has_confirmed_biosample"], "yes")
        self.assertEqual(rows[0]["search_result_review_status"], "manual_review_required")
        self.assertEqual(rows[0]["review_priority"], "P1_conflicting_accepted_match")
        self.assertEqual(rows[0]["accepted_needs_review_accessions"], "SAMN03175008")

    def test_script18_keeps_unflagged_accepted_match_with_side_hits(self) -> None:
        rows = [
            {
                "ncppb_number": "NCPPB 45",
                "current_name": "Xanthomonas campestris",
                "search_result_review_status": "manual_review_required",
                "review_priority": "P2_conflicting_identifier_review",
                "has_confirmed_biosample": "yes",
                "accepted_biosample_accessions": "SAMN36346970",
                "accepted_needs_review_accessions": "",
                "conflicting_accessions": "SAMEA4072397",
                "conflict_rows": "1",
                "taxon_only_rows": "0",
                "rescue_candidate_count": "1",
            }
        ]

        assisted = assist_manual_review.build_assisted_review_rows(rows)

        self.assertEqual(assisted[0]["assistant_audit_decision"], "keep_confirmed_match_review_side_hits")
        self.assertEqual(assisted[0]["recommended_has_status"], "confirmed_biosample_match")
        self.assertEqual(assisted[0]["accepted_to_keep"], "SAMN36346970")

    def test_script19_recommends_disabling_noisy_all_fields_queries_not_biosample_field(self) -> None:
        strategy, reason = all_fields_analysis.field_strategy(
            prefix="X",
            rule_name="source_context_single_letter_code",
            confidence="low",
            raw=100,
            accepted=0,
            non_target=100,
        )

        self.assertEqual(strategy, "disable_default_do_not_replace_with_biosample")
        self.assertIn("no accepted productivity", reason)

    def test_script20_summarizes_rejected_hit_metadata_fields(self) -> None:
        rows = [
            {
                "ncppb_number": "NCPPB 273",
                "ncbi_accession": "SAMN0001",
                "search_term": "B[All Fields] AND 67[All Fields]",
                "status": "ok",
                "title": "Human sample B 67",
                "prior_classification": "review",
                "organism_class": "non_target_organism",
                "raw_audit_decision": "clear_noise",
                "audit_reason": "non_target_organism_without_local_identifier",
                "prior_reject_reason": "non_xanthomonas_organism",
                "keyword_match_class": "query_terms_present_separately",
                "query_term_fields": "B:title,metadata_text;67:attributes,metadata_text",
            }
        ]

        field_rows = metadata_analysis.metadata_field_rows(rows)
        observed = {row["metadata_field"]: row for row in field_rows}

        self.assertIn("title", observed)
        self.assertIn("attributes", observed)
        self.assertEqual(observed["metadata_text"]["non_target_rows"], 1)

    def test_script20_classifies_biosample_attribute_evidence(self) -> None:
        raw_rows = [
            {
                "ncppb_number": "NCPPB 45",
                "ncbi_uid": "1",
                "ncbi_accession": "SAMN45",
                "search_term": "NCPPB[All Fields] AND 45[All Fields]",
                "status": "ok",
                "attributes": "strain: WHRI 6379 (NCPPB 45); culture_collection: NCPPB:45; host: Brassica napus",
                "infraspecies": "strain: WHRI 6379 (NCPPB 45)",
            }
        ]
        audit_rows = [
            {
                "ncppb_number": "NCPPB 45",
                "ncbi_uid": "1",
                "ncbi_accession": "SAMN45",
                "search_term": "NCPPB[All Fields] AND 45[All Fields]",
                "status": "ok",
                "prior_classification": "accepted",
                "organism_class": "target_organism",
                "raw_audit_decision": "supports_accept",
                "title": "Genome sequencing of Xcc WHRI 6379 (NCPPB 45)",
            }
        ]

        tables = metadata_analysis.build_tables(raw_rows, audit_rows)
        attribute_rows = tables["rejected_by_biosample_attribute.tsv"][0]
        categories = {(row["attribute_key"], row["attribute_category"]) for row in attribute_rows}

        self.assertIn(("strain", "strain_or_isolate"), categories)
        self.assertIn(("culture_collection", "culture_collection_or_voucher"), categories)
        self.assertIn(("host", "host"), categories)

    def test_script20_recommendations_reject_biosample_field_substitution(self) -> None:
        rows = [
            {
                "ncppb_number": "NCPPB 273",
                "search_term": "X[All Fields] AND 3[All Fields]",
                "prior_classification": "review",
                "organism_class": "non_target_organism",
                "keyword_match_class": "query_terms_present_separately",
                "raw_audit_decision": "clear_noise",
                "rule_name": "source_context_single_letter_code",
            }
        ]

        recommendations = metadata_analysis.recommendation_rows(rows, [])
        joined_text = " ".join(row["recommended_change"] + " " + row["implementation_detail"] for row in recommendations)

        self.assertIn("Do not emit PREFIX[BioSample]", joined_text)
        self.assertIn("[Text Word]", joined_text)


if __name__ == "__main__":
    unittest.main()
