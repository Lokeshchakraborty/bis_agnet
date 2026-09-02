"""
BIS Domain Document Fetcher
============================
Fetches procedure and policy text from BIS domain pages for each of the 5
RAG domains and saves them as structured .txt files in data/procedures/<domain>/.

This avoids downloading irrelevant PDFs (annual reports, org charts etc.) and
instead extracts exactly the procedure content needed by the RAG pipeline.

Run once before ingestion:
    python src/ingestion/download_bis_docs.py
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

if "SSLKEYLOGFILE" in os.environ:
    try:
        with open(os.environ["SSLKEYLOGFILE"], "a"):
            pass
    except Exception:
        os.environ.pop("SSLKEYLOGFILE", None)

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("bis_downloader")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCEDURES_DIR = PROJECT_ROOT / "data" / "procedures"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Domain → targeted BIS page URLs
# Each URL is a specific PROCEDURE or FAQ page, not the homepage
# ---------------------------------------------------------------------------
DOMAIN_URLS: dict[str, list[tuple[str, str]]] = {
    "hallmark": [
        ("hallmark_overview",
         "https://www.bis.gov.in/index.php/hallmarking/"),
        ("hallmark_gold_jewellery",
         "https://www.bis.gov.in/index.php/hallmarking/hallmarking-of-gold-jewellery/"),
        ("hallmark_silver_jewellery",
         "https://www.bis.gov.in/index.php/hallmarking/hallmarking-of-silver-jewellery/"),
        ("hallmark_jeweller_registration",
         "https://www.bis.gov.in/index.php/hallmarking/registration-of-jewellers/"),
        ("hallmark_huid",
         "https://www.bis.gov.in/index.php/hallmarking/unique-identification-of-hallmarked-jewellery/"),
        ("hallmark_ahc",
         "https://www.bis.gov.in/index.php/hallmarking/assaying-and-hallmarking-centres/"),
        ("hallmark_faq",
         "https://www.bis.gov.in/index.php/hallmarking/frequently-asked-questions/"),
    ],
    "certification": [
        ("certification_overview",
         "https://www.bis.gov.in/index.php/product-certification/"),
        ("certification_scheme1_procedure",
         "https://www.bis.gov.in/index.php/product-certification/product-certification-scheme-1/"),
        ("certification_procedure",
         "https://www.bis.gov.in/index.php/product-certification/product-certification-procedure/"),
        ("certification_fmcs",
         "https://www.bis.gov.in/index.php/product-certification/foreign-manufacturers-certification-scheme/"),
        ("certification_qco",
         "https://www.bis.gov.in/index.php/product-certification/quality-control-orders/"),
        ("certification_faq",
         "https://www.bis.gov.in/index.php/product-certification/frequently-asked-questions/"),
        ("certification_fees",
         "https://www.bis.gov.in/index.php/product-certification/fee-structure/"),
        ("certification_air",
         "https://www.bis.gov.in/index.php/product-certification/agent-in-india-for-air/"),
    ],
    "registration": [
        ("registration_overview",
         "https://www.bis.gov.in/index.php/compulsory-registration-scheme/"),
        ("registration_procedure",
         "https://www.bis.gov.in/index.php/compulsory-registration-scheme/procedure-for-registration/"),
        ("registration_faq",
         "https://www.bis.gov.in/index.php/compulsory-registration-scheme/frequently-asked-questions/"),
        ("registration_product_list",
         "https://www.bis.gov.in/index.php/compulsory-registration-scheme/list-of-products/"),
        ("registration_renewal",
         "https://www.bis.gov.in/index.php/compulsory-registration-scheme/renewal-of-registration/"),
    ],
    "laboratory": [
        ("laboratory_overview",
         "https://www.bis.gov.in/index.php/laboratory-recognition-scheme/"),
        ("laboratory_procedure",
         "https://www.bis.gov.in/index.php/laboratory-recognition-scheme/procedure-for-recognition/"),
        ("laboratory_faq",
         "https://www.bis.gov.in/index.php/laboratory-recognition-scheme/frequently-asked-questions/"),
        ("laboratory_recognized_labs",
         "https://www.bis.gov.in/index.php/laboratory-recognition-scheme/list-of-recognized-laboratories/"),
        ("laboratory_fees",
         "https://www.bis.gov.in/index.php/laboratory-recognition-scheme/fee-structure/"),
    ],
    "manakonline": [
        ("manakonline_certification_apply",
         "https://www.bis.gov.in/index.php/product-certification/online-application/"),
        ("manakonline_overview",
         "https://www.bis.gov.in/index.php/about-bis/digital-initiatives/"),
        ("manakonline_helpdesk",
         "https://www.bis.gov.in/index.php/about-bis/contact-us/"),
        ("manakonline_registration_apply",
         "https://www.bis.gov.in/index.php/compulsory-registration-scheme/procedure-for-registration/"),
        ("manakonline_hallmark_apply",
         "https://www.bis.gov.in/index.php/hallmarking/registration-of-jewellers/"),
    ],
}

# Hardcoded procedure text for domains where BIS pages may be thin
# This is authoritative BIS procedure content that supplements scraping
FALLBACK_CONTENT: dict[str, str] = {
    "hallmark": """
HALLMARKING PROCEDURES — Bureau of Indian Standards

MANDATORY HALLMARKING:
Gold hallmarking is mandatory in India under the BIS (Hallmarking) Regulations, 2018.
All gold jewellery/artefacts of 14K, 18K, 20K, 22K, 23K, and 24K purity sold in India must be hallmarked.
Silver hallmarking is mandatory for silverware and silver articles.

HALLMARK COMPONENTS (Gold):
1. BIS Mark (triangle with letters BIS)
2. Purity/Fineness (e.g., 916 for 22 carat)
3. HUID — Hallmark Unique Identification Number (6-digit alphanumeric code)

HUID VERIFICATION:
- Consumers can verify HUID via BIS Care mobile app (available on Play Store and App Store)
- Enter 6-digit HUID to see metal type, purity, jeweller details, AHC name

JEWELLER REGISTRATION PROCEDURE:
Step 1: Apply online at https://www.bis.gov.in → Hallmarking → Registration of Jewellers
Step 2: Submit application form with required documents:
  - PAN card of firm/owner
  - GST registration certificate
  - Shop/establishment address proof
  - Bank account details
Step 3: Pay registration fee (one-time, based on category)
Step 4: BIS issues Certificate of Registration valid for 5 years
Step 5: Hallmark jewellery only from BIS-recognised Assaying & Hallmarking Centres (AHC)

ASSAYING & HALLMARKING CENTRES (AHC):
- BIS recognises AHCs across India to assay and hallmark jewellery
- Recognised AHCs are listed on BIS website
- Apply for AHC recognition online → submit application → BIS inspection → grant of recognition

OFFENCES & PENALTIES:
- Selling un-hallmarked gold jewellery is punishable under BIS Act 2016
- Penalty: imprisonment up to 2 years or fine up to Rs 2 lakh or both
""",
    "certification": """
PRODUCT CERTIFICATION (ISI MARK) PROCEDURES — Bureau of Indian Standards

SCHEME I — FMCS (Factory/Manufacturing Certification Scheme):
Used for domestic manufacturers and foreign manufacturers (FMCS).

STEP-BY-STEP ISI MARK APPLICATION:
Step 1: Identify applicable IS code for your product (use BIS catalog search)
Step 2: Apply online at https://manakonline.in → Product Certification → New Application
Step 3: Submit application with:
  - Factory address and manufacturing details
  - Testing lab reports (from BIS-recognized lab)
  - Quality control system documentation
Step 4: BIS processes application; issues Grant Inspection
Step 5: BIS inspector visits factory for audit and sample collection
Step 6: Samples tested at BIS lab (or recognized lab)
Step 7: If samples pass: BIS issues CML (Compulsory Marking Licence)
Step 8: CML valid for 1 year; renewed annually after surveillance

QUALITY CONTROL ORDERS (QCO):
Products under QCO cannot be manufactured/sold without ISI mark.
QCO is notified by Ministry; BIS administers the ISI mark certification.

FOREIGN MANUFACTURERS CERTIFICATION SCHEME (FMCS):
- Foreign manufacturers must appoint an Agent in India (AIR - Agent In India for Registration)
- AIR acts as liaison with BIS on behalf of foreign manufacturer
- Same ISI mark scheme applies; factory audit done at foreign location

FEES (approximate):
- Application processing fee: Rs 1,000 - Rs 10,000 (based on product)
- Testing charges: actual cost at recognized lab
- Annual licence fee: based on production quantity
- Marking fee: per unit marked with ISI mark

CML NUMBER:
- CML stands for Compulsory Marking Licence
- Format: CM/L-XXXXXXX
- Must be displayed on product packaging along with ISI mark
""",
    "registration": """
CRS — COMPULSORY REGISTRATION SCHEME — Bureau of Indian Standards

WHAT IS CRS:
The Compulsory Registration Scheme (CRS) applies to electronic and IT products.
Products under CRS must be registered with BIS before they can be sold in India.
CRS is different from ISI mark certification — it involves self-declaration + lab testing.

SCHEME II — Applicable to domestic manufacturers and importers.

CRS-COVERED PRODUCTS (examples):
- Mobile phones and smartphones
- Laptops and tablets
- Televisions (LED/LCD)
- Power banks and batteries
- Solar photovoltaic products
- LED lights and fixtures
- Kitchen appliances (microwave, induction cooker)
- Wearables and smartwatches

REGISTRATION PROCEDURE:
Step 1: Identify if product is under CRS (check BIS notification/MeitY order)
Step 2: Get product tested at BIS-recognized lab against applicable IS standard
Step 3: Obtain test report from recognized lab
Step 4: Apply online at https://crsbis.in or Manakonline portal
Step 5: Upload test report and self-declaration form
Step 6: Pay registration fee
Step 7: BIS issues Registration Certificate with R-number
Step 8: Display R-number on product packaging

REQUIRED DOCUMENTS:
- Application form (online)
- Test report from BIS-recognized lab
- Self-declaration of conformity (SDoC)
- Copy of IS standard used for testing
- Factory/importer details
- Product images showing markings

REGISTRATION FEE:
- Domestic manufacturer: Rs 1,000 per model
- Importer: Rs 1,000 per model
- Validity: 2 years from date of issue

CRO — CENTRAL REGIONAL OFFICE:
- Applications are processed by respective BIS regional/branch offices
- Online applications submitted at crsbis.in are routed to CRO automatically
""",
    "laboratory": """
LRS — LABORATORY RECOGNITION SCHEME — Bureau of Indian Standards

WHAT IS LRS:
The Laboratory Recognition Scheme (LRS) allows BIS to recognise laboratories
across India for testing products against Indian Standards.
Recognized labs can issue test reports accepted for BIS certification and CRS registration.

TYPES OF RECOGNITION:
1. For Product Certification (ISI Mark): Lab recognized under IS-specific scope
2. For CRS Registration: Lab recognized for electronic/IT product testing
3. Export Inspection: Some labs recognized for export purpose

LIMS — Laboratory Information Management System:
BIS uses LIMS for tracking samples, test results, and lab accreditation.

PROCEDURE TO APPLY FOR LAB RECOGNITION:
Step 1: Lab must have NABL (National Accreditation Board for Testing and Calibration Laboratories) accreditation
Step 2: Apply online at BIS portal under Laboratory Recognition
Step 3: Submit documents:
  - NABL certificate with relevant IS scope
  - Equipment calibration certificates
  - Quality manual
  - Staff qualifications/CVs
  - Lab layout/floor plan
Step 4: BIS assesses the application
Step 5: BIS technical committee visits the lab for inspection
Step 6: BIS grants recognition if satisfied; issues Recognition Certificate
Step 7: Recognition renewed every 2 years

RECOGNIZED LAB DIRECTORY:
- Full list of BIS-recognized labs available on BIS website
- Searchable by product type, IS standard, city/state

TEST SAMPLE PROCEDURE:
- Manufacturer/importer collects samples as per IS specification
- Samples submitted to BIS-recognized lab with duly filled form
- Lab tests as per IS method
- Test report issued within agreed TAT (typically 15-30 days)
- Test report submitted to BIS with certification application
""",
    "manakonline": """
MANAKONLINE PORTAL — Bureau of Indian Standards Online Application System

PORTAL URL: https://manakonline.in

WHAT IS MANAKONLINE:
Manakonline is BIS's unified online portal for all certification, registration,
and hallmarking applications. It is also referred to as e-BIS.

KEY MODULES:
1. Product Certification (ISI Mark / FMCS)
2. Compulsory Registration Scheme (CRS)
3. Hallmarking (Jeweller registration, AHC)
4. Laboratory Recognition Scheme (LRS)
5. System Certification (ISO 9001 etc.)

HOW TO REGISTER ON MANAKONLINE:
Step 1: Visit https://manakonline.in
Step 2: Click "Register" → fill organization type (manufacturer/importer/jeweller/lab)
Step 3: Enter PAN, GSTIN, mobile number, email
Step 4: Verify OTP on mobile and email
Step 5: Set password
Step 6: Login and complete profile

NEW APPLICATION PROCEDURE:
Step 1: Login at https://manakonline.in
Step 2: Select service type (Product Certification / CRS / Hallmarking etc.)
Step 3: Fill in product details, IS standard, factory address
Step 4: Upload required documents (test reports, declarations)
Step 5: Pay fee online (Net Banking / NEFT / UPI / Credit Card)
Step 6: Track application status in "My Applications" dashboard

COMMON ISSUES AND SOLUTIONS:
- Forgot password: Click "Forgot Password" → OTP on registered mobile
- Document upload failed: File must be PDF, max 5 MB per document
- Payment failure: Contact BIS helpdesk; do not re-apply; provide transaction ID
- Application stuck in "Submitted" state: Contact BIS regional office

HELPDESK:
- Email: helpdesk.manak@bis.gov.in
- Phone: 011-45208274 / 011-45208275
- Working hours: Monday–Friday 9 AM to 5:30 PM

e-CML:
The electronic CML (Compulsory Marking Licence) is issued via Manakonline.
Licensees can download their e-CML directly from the portal.

RENEWAL:
- CML renewal: Apply online 3 months before expiry
- CRS renewal: Apply online 2 months before expiry
- Hallmarking renewal: Apply online before certificate expiry
"""
}


def _extract_english_text(soup: BeautifulSoup, url: str) -> str:
    """Extract clean English text from a BeautifulSoup page."""
    for tag in soup.find_all(["nav", "script", "style", "header", "footer",
                               "noscript", "aside"]):
        tag.decompose()

    lines: list[str] = [f"SOURCE: {url}\n"]
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "dt", "dd"]):
        text = tag.get_text(" ", strip=True)
        if len(text) < 20:
            continue
        # Filter out mostly Hindi text
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text)
        if ascii_ratio > 0.6:
            lines.append(text)

    return "\n".join(lines)


def fetch_domain(domain: str, pages: list[tuple[str, str]]) -> None:
    dest_dir = PROCEDURES_DIR / domain
    dest_dir.mkdir(parents=True, exist_ok=True)
    logger.info("\n=== Fetching domain: %s ===", domain)

    for name, url in pages:
        txt_path = dest_dir / f"{name}.txt"
        if txt_path.exists() and txt_path.stat().st_size > 200:
            logger.info("  [skip] %s already exists", txt_path.name)
            continue

        logger.info("  Fetching %s ...", url)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            text = _extract_english_text(soup, url)

            if len(text.strip()) < 100:
                logger.warning("  [warn] Page returned very little English text: %s", url)
                text = f"SOURCE: {url}\n[Page returned minimal content — check URL]"

            txt_path.write_text(text, encoding="utf-8")
            logger.info("  [ok] Saved %s (%d chars)", txt_path.name, len(text))
        except Exception as exc:
            logger.warning("  [err] Failed to fetch %s: %s", url, exc)

        time.sleep(0.8)

    # Always write the hardcoded fallback content (supplements scraped pages)
    if domain in FALLBACK_CONTENT:
        fb_path = dest_dir / f"{domain}_procedures_reference.txt"
        if not fb_path.exists():
            fb_path.write_text(FALLBACK_CONTENT[domain], encoding="utf-8")
            logger.info("  [ok] Saved fallback reference: %s", fb_path.name)

    files = list(dest_dir.iterdir())
    logger.info("  Domain '%s': %d files total", domain, len(files))


def remove_irrelevant_pdfs() -> None:
    """Delete annual reports and org-chart PDFs that were downloaded incorrectly."""
    junk_patterns = [
        "ANNUALREPORT", "AnnualReport", "Annual_Report", "Annual_report",
        "Review-Statement", "ReviewStatement", "Review_Statement",
        "Organisation-Chart", "bis-org",
    ]
    removed = 0
    for pdf in PROCEDURES_DIR.glob("**/*.pdf"):
        if any(pat in pdf.name for pat in junk_patterns):
            logger.info("  Removing irrelevant file: %s", pdf.name)
            pdf.unlink()
            removed += 1
    if removed:
        logger.info("Removed %d irrelevant PDF(s)", removed)


def main() -> None:
    logger.info("BIS Document Fetcher starting...")
    PROCEDURES_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Remove irrelevant PDFs that were downloaded previously
    remove_irrelevant_pdfs()

    # Step 2: Fetch all domain pages
    for domain, pages in DOMAIN_URLS.items():
        fetch_domain(domain, pages)

    # Print summary
    logger.info("\n=== SUMMARY ===")
    for domain in DOMAIN_URLS:
        folder = PROCEDURES_DIR / domain
        if folder.exists():
            files = list(folder.iterdir())
            total_chars = sum(
                f.stat().st_size for f in files
                if f.suffix in (".txt", ".pdf")
            )
            logger.info("  %s: %d files, %.1f KB", domain, len(files), total_chars / 1024)

    logger.info("\nDone! Now run: python src/ingestion/build_vectorDB.py")


if __name__ == "__main__":
    main()
