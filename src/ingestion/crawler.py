"""
Live QCO Circular & Regulatory Notification Crawler
==================================================
Crawls recent Quality Control Orders (QCOs), Gazette circulars, and amendments
from crsbis.in and bis.gov.in, and ingests updates into ChromaDB.
"""
from __future__ import annotations

import logging
import re
import requests
from bs4 import BeautifulSoup
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CONFIG, DATA_DIR
from src.ingestion.build_vectordb import ingest_segment, get_embeddings_model

logger = logging.getLogger("bis_crawler")

CRS_NOTIFICATIONS_URL = "https://www.crsbis.in/BIS/products-others.do"
BIS_QCO_URL = "https://www.bis.gov.in/index.php/standards/technical-department/qco-notifications/"


def crawl_live_circulars() -> List[Dict[str, str]]:
    """Fetch latest Quality Control Orders and notifications from official portals."""
    logger.info("Crawling live BIS/CRS circulars and QCO notifications...")
    crawled_notifs: List[Dict[str, str]] = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # 1. BIS Technical QCO Notifications Page
    try:
        resp = requests.get(BIS_QCO_URL, headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.select("a[href*='.pdf']")[:10]:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if len(title) > 15:
                    crawled_notifs.append({
                        "source": "bis.gov.in QCO",
                        "title": title,
                        "url": href if href.startswith("http") else f"https://www.bis.gov.in{href}",
                    })
    except Exception as exc:
        logger.warning("Failed to crawl BIS QCO notifications page: %s", exc)

    # 2. CRS Products & Orders Page
    try:
        resp = requests.get(CRS_NOTIFICATIONS_URL, headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("tr td")[:15]:
                txt = item.get_text(strip=True)
                if "IS" in txt and len(txt) > 20:
                    crawled_notifs.append({
                        "source": "crsbis.in Notification",
                        "title": txt[:200],
                        "url": CRS_NOTIFICATIONS_URL,
                    })
    except Exception as exc:
        logger.warning("Failed to crawl CRS notifications page: %s", exc)

    logger.info("Crawled %d live circular notification items.", len(crawled_notifs))
    return crawled_notifs


def sync_circulars_to_db() -> int:
    """Save crawled circular notifications to text file and ingest into ChromaDB."""
    notifs = crawl_live_circulars()
    if not notifs:
        logger.info("No new circulars found to ingest.")
        return 0

    target_dir = DATA_DIR / "procedures" / "registration"
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / "latest_qco_circulars.txt"

    lines = ["=== LATEST LIVE BIS & CRS QCO CIRCULARS & NOTIFICATIONS ==="]
    for n in notifs:
        lines.append(f"• Source: {n['source']}\n  Title: {n['title']}\n  URL: {n['url']}\n")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved circular notifications to %s", out_file)

    # Re-ingest registration segment
    embeddings = get_embeddings_model()
    count = ingest_segment("registration", embeddings, reset=False)
    logger.info("Sync complete. Ingested %d chunks into Chroma DB registration collection.", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_circulars_to_db()
