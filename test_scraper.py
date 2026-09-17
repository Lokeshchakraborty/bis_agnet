"""
Unit & Integration Tests for BIS Multi-Source Web Scraper
=========================================================
Tests standards scraping accuracy, relevance ranking, and non-IS regulatory
intelligence (QCOs, CRS electronics, Conformity Schemes, Fee structures, and Circulars).
"""
from __future__ import annotations

import unittest
from src.tools.scraper import (
    CircularRecord,
    CRSRecord,
    QCORecord,
    SchemeRecord,
    StandardRecord,
    StructuredScrapeResult,
    scrape_bis_portal,
    scrape_structured,
    _search_know_your_standards_api,
    _search_qcos,
    _search_crs_products,
    _match_schemes_and_procedures,
)


class TestBISScraper(unittest.TestCase):
    def test_01_standards_scraping_and_ranking_accuracy(self):
        """Verify that searching for a commodity ranks actual relevant standards at the top."""
        result = _search_know_your_standards_api("ordinary portland cement")
        self.assertIsInstance(result, list)
        if result:
            top_std = result[0]
            self.assertIsInstance(top_std, StandardRecord)
            self.assertTrue(top_std.standard_number.startswith("IS"))
            # Relevance score must be positive
            self.assertGreater(top_std.relevance_score, 0.0)
            # Top standard must be related to cement
            all_text = f"{top_std.standard_number} {top_std.title}".lower()
            self.assertIn("cement", all_text)

    def test_02_exact_is_code_search(self):
        """Verify searching by exact IS code prioritizes that code."""
        result = _search_know_your_standards_api("IS 12701")
        self.assertIsInstance(result, list)
        if result:
            numbers = [r.standard_number for r in result]
            self.assertTrue(any("12701" in num for num in numbers))

    def test_03_qco_scraping_non_is(self):
        """Verify Quality Control Orders (QCO) extraction including ministries and enforcement dates."""
        qcos = _search_qcos("linear alkyl benzene")
        self.assertIsInstance(qcos, list)
        if qcos:
            qco = qcos[0]
            self.assertIsInstance(qco, QCORecord)
            self.assertIn("chemical", qco.ministry.lower())
            self.assertTrue(bool(qco.enforcement_date))
            self.assertTrue(bool(qco.standard_number))

    def test_04_crs_electronics_scraping_non_is(self):
        """Verify Compulsory Registration Scheme (CRS) electronics extraction."""
        crs_items = _search_crs_products("automatic data processing")
        self.assertIsInstance(crs_items, list)
        if crs_items:
            item = crs_items[0]
            self.assertIsInstance(item, CRSRecord)
            self.assertIn("automatic data processing", item.product_category.lower())
            self.assertTrue("13252" in item.standard_number)
            self.assertTrue(bool(item.implementation_date))
            self.assertIn("meity", item.ministry.lower())

    def test_05_schemes_and_procedures_matching(self):
        """Verify Conformity Schemes matching for FMCS, Hallmarking, LRS, and Fees."""
        # 1. FMCS & AIR
        fmcs = _match_schemes_and_procedures("FMCS foreign manufacturer AIR requirements")
        self.assertTrue(any("FMCS" in s.scheme_name or "Foreign" in s.scheme_name for s in fmcs))
        fmcs_rec = next(s for s in fmcs if "Foreign" in s.scheme_name or "FMCS" in s.scheme_name)
        self.assertTrue(fmcs_rec.air_required)
        self.assertIn("manakonline", fmcs_rec.portal_url.lower())

        # 2. Hallmarking & HUID
        hm = _match_schemes_and_procedures("Gold hallmarking HUID 6 digit registration")
        self.assertTrue(any("Hallmarking" in s.scheme_name for s in hm))
        hm_rec = next(s for s in hm if "Hallmarking" in s.scheme_name)
        self.assertIn("HUID", hm_rec.marking_symbol)

        # 3. Fees and MSME concessions
        fees = _match_schemes_and_procedures("Marking fee and MSME concession")
        self.assertTrue(len(fees) >= 1)
        self.assertIn("concession", fees[0].fee_overview.lower())

    def test_06_structured_scrape_unified(self):
        """Verify scrape_structured returns a complete StructuredScrapeResult container."""
        res = scrape_structured("toys quality control order and safety standards")
        self.assertIsInstance(res, StructuredScrapeResult)
        self.assertEqual(res.query, "toys quality control order and safety standards")

        # Serializes cleanly to dictionary
        d = res.to_dict()
        self.assertIn("standards", d)
        self.assertIn("qcos", d)
        self.assertIn("crs_products", d)
        self.assertIn("schemes", d)
        self.assertIn("circulars", d)

        # Produces structured context text
        ctx = res.to_context_text()
        self.assertIsInstance(ctx, str)
        if res.has_results():
            self.assertTrue(
                "### [" in ctx or "OFFICIAL" in ctx or "QUALITY CONTROL" in ctx
            )

    def test_07_scrape_bis_portal_context_formatting(self):
        """Verify scrape_bis_portal produces structured context ready for LLM."""
        text = scrape_bis_portal("IS 12701 water tank standard and scheme")
        self.assertIsInstance(text, str)
        self.assertTrue(len(text) > 50)
        self.assertIn("IS", text)


if __name__ == "__main__":
    unittest.main()
