"""
BIS Domain Procedure & Policy Document Fetcher
==============================================
Fetches targeted procedure text from BIS domain pages and seeds authoritative
procedure documentation into data/procedures/<domain>/ for ingestion.

Usage:
    python src/ingestion/download_docs.py
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup

from src.config import CONFIG, DATA_DIR

logger = logging.getLogger("bis_downloader")

PROCEDURES_DIR = Path(CONFIG.procedures_path)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

DOMAIN_URLS: Dict[str, List[Tuple[str, str]]] = {
    "hallmark": [
        ("hallmark_overview", "https://www.bis.gov.in/index.php/hallmarking/"),
        ("hallmark_gold", "https://www.bis.gov.in/index.php/hallmarking/hallmarking-of-gold-jewellery/"),
        ("hallmark_jeweller_reg", "https://www.bis.gov.in/index.php/hallmarking/registration-of-jewellers/"),
        ("hallmark_huid", "https://www.bis.gov.in/index.php/hallmarking/unique-identification-of-hallmarked-jewellery/"),
        ("hallmark_ahc", "https://www.bis.gov.in/index.php/hallmarking/assaying-and-hallmarking-centres/"),
    ],
    "certification": [
        ("certification_overview", "https://www.bis.gov.in/index.php/product-certification/"),
        ("certification_scheme1", "https://www.bis.gov.in/index.php/product-certification/product-certification-scheme-1/"),
        ("certification_fmcs", "https://www.bis.gov.in/index.php/product-certification/foreign-manufacturers-certification-scheme/"),
        ("certification_qco", "https://www.bis.gov.in/index.php/product-certification/quality-control-orders/"),
    ],
    "registration": [
        ("registration_overview", "https://www.bis.gov.in/index.php/compulsory-registration-scheme/"),
        ("registration_proc", "https://www.bis.gov.in/index.php/compulsory-registration-scheme/procedure-for-registration/"),
        ("registration_faq", "https://www.bis.gov.in/index.php/compulsory-registration-scheme/frequently-asked-questions/"),
    ],
    "laboratory": [
        ("laboratory_overview", "https://www.bis.gov.in/index.php/laboratory-recognition-scheme/"),
        ("laboratory_proc", "https://www.bis.gov.in/index.php/laboratory-recognition-scheme/procedure-for-recognition/"),
        ("laboratory_faq", "https://www.bis.gov.in/index.php/laboratory-recognition-scheme/frequently-asked-questions/"),
    ],
    "manakonline": [
        ("manakonline_apply", "https://www.bis.gov.in/index.php/product-certification/online-application/"),
        ("manakonline_overview", "https://www.bis.gov.in/index.php/about-bis/digital-initiatives/"),
    ],
}

AUTHORITATIVE_SEEDS: Dict[str, str] = {
    "hallmark": """
HALLMARKING PROCEDURES — Bureau of Indian Standards

MANDATORY HALLMARKING:
Gold hallmarking is mandatory in India under the BIS (Hallmarking) Regulations, 2018.
All gold jewellery and artefacts of 14K, 18K, 20K, 22K, 23K, and 24K purity sold in notified districts must be hallmarked.

HALLMARK MARKS (Gold):
1. BIS Standard Mark (triangle logo)
2. Purity / Fineness (e.g., 916 for 22 carat, 750 for 18 carat)
3. HUID (Hallmark Unique Identification) - 6-digit alphanumeric code assigned per piece.

VERIFICATION:
Consumers can verify HUID using the official BIS Care App.

REGISTRATION FOR JEWELLERS:
Apply online at https://www.manakonline.in under Hallmarking portal. Submit PAN, GST, address proof, and pay registration fee.
Certificate of Registration is valid for 5 years.
""",
    "certification": """
PRODUCT CERTIFICATION (ISI MARK) PROCEDURES — Bureau of Indian Standards

SCHEME I — Standard Product Certification & FMCS:
Mandatory for products under Quality Control Orders (QCOs).

APPLICATION PROCESS:
1. Identify product standard IS Code.
2. Submit online application at https://manakonline.in.
3. Factory audit and inspection by BIS officers.
4. Independent sample testing at BIS/NABL recognized lab.
5. Grant of Licence (CML Number CM/L-XXXXXXX).

FOREIGN MANUFACTURERS (FMCS):
Foreign manufacturers must appoint an Authorized Indian Representative (AIR) to apply and maintain compliance.
""",
    "registration": """
COMPULSORY REGISTRATION SCHEME (CRS) — Bureau of Indian Standards

CRS SCOPE:
Applies to electronics, IT hardware, solar photovoltaics, and LED products under MeitY and MNRE orders.

PROCESS:
1. Product sample testing at a BIS-recognized testing laboratory.
2. Submission of test report and Self-Declaration of Conformity (SDoC) at https://crsbis.in.
3. Grant of R-number (Registration Number).
4. Marking: Standard BIS CRS label with R-number and applicable IS standard.
""",
    "laboratory": """
LABORATORY RECOGNITION SCHEME (LRS) — Bureau of Indian Standards

LRS OBJECTIVE:
Recognizes third-party and in-house testing laboratories across India to test products against Indian Standards.

CRITERIA:
- NABL accreditation as per ISO/IEC 17025.
- Technical competency, calibrated test equipment, and qualified testing personnel.
- Regular surveillance audits and proficiency testing.
""",
    "manakonline": """
MANAKONLINE PORTAL & DIGITAL INITIATIVES — Bureau of Indian Standards

PORTAL CAPABILITIES (https://manakonline.in):
- e-BIS: Complete end-to-end digital lifecycle for BIS applications.
- Product Certification (ISI Mark) online application, fee payment, and renewal.
- CRS online portal for electronics registration.
- Hallmarking Jeweller registration and AHC portal.
- Laboratory Information Management System (LIMS).
- Know Your Standards & Standards portal (standards.bis.gov.in).
- BIS Care Mobile App for consumers to verify ISI marks and HUIDs.
""",
}


def download_and_seed_docs() -> None:
    """Download online procedure pages and write authoritative reference texts."""
    PROCEDURES_DIR.mkdir(parents=True, exist_ok=True)

    for domain, urls in DOMAIN_URLS.items():
        domain_folder = PROCEDURES_DIR / domain
        domain_folder.mkdir(parents=True, exist_ok=True)

        # 1. Seed authoritative offline reference
        seed_path = domain_folder / f"{domain}_procedures_reference.txt"
        if domain in AUTHORITATIVE_SEEDS:
            seed_path.write_text(AUTHORITATIVE_SEEDS[domain].strip(), encoding="utf-8")
            logger.info("Saved authoritative reference for %s", domain)

        # 2. Scrape live procedure pages
        for name, url in urls:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text("\n", strip=True)
                    text = re.sub(r"\n{3,}", "\n\n", text)
                    if len(text) > 200:
                        doc_path = domain_folder / f"{name}.txt"
                        doc_path.write_text(text, encoding="utf-8")
                        logger.info("Saved %s from %s", doc_path.name, url)
                time.sleep(0.3)
            except Exception as exc:
                logger.debug("Failed to fetch %s: %s", url, exc)


if __name__ == "__main__":
    download_and_seed_docs()
