"""
Live Regulatory Intelligence, QCO & CRS Notification Crawler
============================================================
Crawls authoritative Quality Control Orders (QCOs), Gazette circulars,
CRS electronics products matrix, and Ministry notifications from
bis.gov.in and crsbis.in, then ingests structured updates into the knowledge base.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CONFIG, DATA_DIR
from src.ingestion.build_vectordb import get_embeddings_model, ingest_segment

logger = logging.getLogger("bis_crawler")

CRS_PRODUCTS_URL = "https://www.crsbis.in/BIS/products.do"
CRS_CIRCULARS_URL = "https://www.crsbis.in/BIS/biscirculars.do"
BIS_QCO_REGISTRY_URL = "https://www.bis.gov.in/upcoming-qcos-notified-and-due-for-implementation/?lang=en"
BIS_QCO_NOTIFICATIONS_URL = "https://www.bis.gov.in/qco-notifications/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _clean(text: str) -> str:
    """Collapse consecutive whitespace and trim."""
    return re.sub(r"\s+", " ", text).strip()


def crawl_live_qco_registry() -> List[Dict[str, str]]:
    """Crawl upcoming and active Quality Control Orders from official BIS registry."""
    logger.info("Crawling official BIS Quality Control Orders (QCO) registry...")
    qcos: List[Dict[str, str]] = []

    try:
        resp = requests.get(BIS_QCO_REGISTRY_URL, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if table:
                for r in table.find_all("tr")[1:]:
                    cells = [_clean(c.get_text()) for c in r.find_all(["th", "td"])]
                    if len(cells) >= 5:
                        # [Sr. No., Ministry/ Department, Product, Indian Standard, Enforcement date]
                        ministry = cells[1]
                        product = cells[2]
                        std_num = cells[3]
                        enf_date = cells[4]
                        if product and (std_num or ministry):
                            qcos.append({
                                "ministry": ministry,
                                "product": product,
                                "standard_number": std_num,
                                "enforcement_date": enf_date,
                                "source": "BIS Official Upcoming QCO Registry",
                                "url": BIS_QCO_REGISTRY_URL,
                            })
    except Exception as exc:
        logger.warning("Failed to crawl BIS QCO registry table: %s", exc)

    logger.info("Crawled %d official QCO records.", len(qcos))
    return qcos


def crawl_live_crs_products() -> List[Dict[str, str]]:
    """Crawl live electronics and IT products table under Compulsory Registration Scheme."""
    logger.info("Crawling live CRS electronics products from crsbis.in...")
    crs_products: List[Dict[str, str]] = []

    try:
        resp = requests.get(CRS_PRODUCTS_URL, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if table:
                for r in table.find_all("tr")[1:]:
                    cells = [_clean(c.get_text()) for c in r.find_all(["th", "td"])]
                    if len(cells) >= 4:
                        # [Sl. No., Product, Indian Standard number, Date of Implementation]
                        product = cells[1]
                        std_num = cells[2]
                        impl_date = cells[3]
                        if product:
                            crs_products.append({
                                "product": product,
                                "standard_number": std_num,
                                "implementation_date": impl_date,
                                "mandate": "Self-Declaration of Conformity (SDoC) + NABL/BIS lab report",
                                "source": "CRS Portal (crsbis.in)",
                                "url": CRS_PRODUCTS_URL,
                            })
    except Exception as exc:
        logger.warning("Failed to crawl CRS products table: %s", exc)

    logger.info("Crawled %d official CRS electronics products.", len(crs_products))
    return crs_products


def crawl_live_circulars_and_orders() -> List[Dict[str, str]]:
    """Crawl latest Gazette circulars and regulatory notifications."""
    logger.info("Crawling live circulars and Gazette orders from BIS and CRS portals...")
    notifs: List[Dict[str, str]] = []

    # 1. BIS QCO Notifications page
    try:
        resp = requests.get(BIS_QCO_NOTIFICATIONS_URL, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.select("a[href*='.pdf']")[:15]:
                title = _clean(link.get_text())
                href = link.get("href", "")
                if len(title) > 10 and not any(skip in title.lower() for skip in ["skip", "menu", "home"]):
                    full_url = href if href.startswith("http") else f"https://www.bis.gov.in{href}"
                    notifs.append({
                        "source": "BIS QCO Gazette Order",
                        "title": title,
                        "url": full_url,
                    })
    except Exception as exc:
        logger.warning("Failed to crawl BIS QCO notifications page: %s", exc)

    # 2. CRS Guidelines and Circulars
    try:
        resp = requests.get(CRS_CIRCULARS_URL, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for r in soup.find_all("tr")[1:10]:
                cells = [_clean(c.get_text()) for c in r.find_all(["th", "td"])]
                if len(cells) >= 2:
                    subj = cells[1]
                    if len(subj) > 15:
                        notifs.append({
                            "source": "CRS Guidelines & Circular",
                            "title": subj,
                            "url": CRS_CIRCULARS_URL,
                        })
    except Exception as exc:
        logger.warning("Failed to crawl CRS circulars: %s", exc)

    logger.info("Crawled %d live circular notifications.", len(notifs))
    return notifs


def sync_crawler_data_to_db() -> Dict[str, int]:
    """
    Save crawled QCOs, CRS products, and circulars into structured domain text files
    and ingest them into ChromaDB / Vector Store.
    """
    qcos = crawl_live_qco_registry()
    crs_prods = crawl_live_crs_products()
    circulars = crawl_live_circulars_and_orders()

    cert_dir = DATA_DIR / "procedures" / "certification"
    reg_dir = DATA_DIR / "procedures" / "registration"
    cert_dir.mkdir(parents=True, exist_ok=True)
    reg_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save QCO Master Registry
    if qcos:
        qco_lines = [
            "=== AUTHORITATIVE QUALITY CONTROL ORDERS (QCO) REGISTRY — Bureau of Indian Standards ===",
            "Mandatory compliance is governed under Section 16 & Section 29 of the Bureau of Indian Standards Act, 2016.",
            "Violations carry statutory penalties including imprisonment and fines under Section 29.",
            "",
        ]
        for q in qcos:
            qco_lines.append(
                f"• Product: {q['product']}\n"
                f"  Ministry / Department: {q['ministry']}\n"
                f"  Applicable Indian Standard: {q['standard_number']}\n"
                f"  Enforcement Deadline: {q['enforcement_date']}\n"
                f"  Statutory Status: Mandatory / Quality Control Order In Force or Notified\n"
            )
        (cert_dir / "qco_master_registry.txt").write_text("\n".join(qco_lines), encoding="utf-8")
        logger.info("Saved QCO master registry to %s", cert_dir / "qco_master_registry.txt")

    # 2. Save CRS Products Registry
    if crs_prods:
        crs_lines = [
            "=== COMPULSORY REGISTRATION SCHEME (CRS) PRODUCTS REGISTRY — MeitY & MNRE ===",
            "Regulated under Compulsory Registration Scheme Order. Requires testing at a BIS-recognized lab",
            "and filing Self-Declaration of Conformity (SDoC) on https://crsbis.in for grant of R-Number.",
            "",
        ]
        for c in crs_prods:
            crs_lines.append(
                f"• Product Category: {c['product']}\n"
                f"  Indian Standard (IS No.): {c['standard_number']}\n"
                f"  Statutory Enforcement Date: {c['implementation_date']}\n"
                f"  Compliance Requirement: {c['mandate']}\n"
                f"  Portal: https://crsbis.in\n"
            )
        (reg_dir / "crs_products_registry.txt").write_text("\n".join(crs_lines), encoding="utf-8")
        logger.info("Saved CRS products registry to %s", reg_dir / "crs_products_registry.txt")

    # 3. Save Circulars & Notifications
    if circulars:
        circ_lines = ["=== LATEST LIVE BIS & CRS REGULATORY CIRCULARS & GAZETTE ORDERS ==="]
        for n in circulars:
            circ_lines.append(f"• Source: {n['source']}\n  Title: {n['title']}\n  URL: {n['url']}\n")
        (reg_dir / "latest_qco_circulars.txt").write_text("\n".join(circ_lines), encoding="utf-8")
        (cert_dir / "latest_qco_circulars.txt").write_text("\n".join(circ_lines), encoding="utf-8")
        logger.info("Saved latest circular notifications to registration and certification directories.")

    # Ingest updated segments into Vector Store
    embeddings = get_embeddings_model()
    cert_count = ingest_segment("certification", embeddings, reset=False)
    reg_count = ingest_segment("registration", embeddings, reset=False)

    logger.info(
        "Sync complete. Ingested %d chunks into certification and %d chunks into registration.",
        cert_count,
        reg_count,
    )
    return {"certification": cert_count, "registration": reg_count}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_crawler_data_to_db()
