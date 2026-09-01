"""
BIS Portal Scraper
==================
Searches the Bureau of Indian Standards website for IS codes, product standards,
and certification/hallmarking information.

Strategy order (fastest/most reliable first):
  1. BIS WordPress REST API  – returns structured JSON of matching pages
  2. BIS National Standards page search (requests + regex IS-code extraction)
  3. Playwright headless browser on BIS e-catalog (JS-rendered)

Exposes a single public function:
    scrape_bis_portal(search_query: str) -> str

Returns a plain-text string of extracted results (empty string on total failure).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("bis_scraper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_TIMEOUT = 20  # seconds

# IS code pattern – matches "IS 1234", "IS:1234", "IS 1234-1", "IS 1234 : 2021"
IS_CODE_RE = re.compile(r"\bIS[\s:]*\d[\d\-]+(?:[\s:]+\d{4})?", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helper: clean extracted text
# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_is_codes(text: str) -> list[str]:
    """Return a de-duplicated list of IS code strings found in `text`."""
    seen: set[str] = set()
    result: list[str] = []
    for m in IS_CODE_RE.finditer(text):
        code = _clean(m.group())
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


# ---------------------------------------------------------------------------
# Strategy 1: BIS WordPress REST API
# ---------------------------------------------------------------------------
def _search_bis_wp_api(query: str) -> Optional[str]:
    """
    Uses BIS's WordPress REST API to search for pages matching the query.
    Returns structured text with page titles, IS codes found, and URLs.
    """
    try:
        url = f"https://www.bis.gov.in/wp-json/wp/v2/search?search={quote_plus(query)}&per_page=10&type=post"
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list) or not data:
            return None

        lines: list[str] = [f"BIS Portal pages matching '{query}':"]
        for item in data[:8]:
            title = item.get("title", "")
            page_url = item.get("url", "")
            if title:
                lines.append(f"  • {title}")
                if page_url:
                    lines.append(f"    URL: {page_url}")

        if len(lines) > 1:
            return "\n".join(lines)
    except Exception as exc:
        logger.debug("BIS WP API failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Strategy 2: BIS Standards Catalog (national-standards page + IS-code regex)
# ---------------------------------------------------------------------------
def _search_bis_standards_page(query: str) -> Optional[str]:
    """
    Fetches the BIS national standards search page and uses regex to extract
    IS codes from the rendered HTML text. Works even without JS because the
    Liferay portal inlines some metadata in the HTML.
    """
    try:
        url = "https://www.bis.gov.in/index.php/standards/technical-department/national-standards"
        params = {
            "p_p_id": "com_liferay_portal_search_web_portlet_SearchPortlet",
            "p_p_lifecycle": "0",
            "_com_liferay_portal_search_web_portlet_SearchPortlet_keywords": query,
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)

        # Extract every IS-code-like pattern from the full page text
        is_codes = _extract_is_codes(text)

        # Also grab meaningful English sentences around IS codes
        # Split text into sentences and keep only those with IS codes or relevant keywords
        keywords = re.compile(
            r"\b(IS\s*\d|standard|specification|petroleum|product|certif|hallmark|registration)\b",
            re.IGNORECASE,
        )
        relevant_lines: list[str] = []
        for part in re.split(r"[।\.\n]{1,3}", text):
            part = _clean(part)
            if len(part) > 30 and keywords.search(part):
                # Filter out Hindi-heavy lines (mostly Hindi chars are non-ASCII)
                ascii_ratio = sum(1 for c in part if ord(c) < 128) / max(len(part), 1)
                if ascii_ratio > 0.5:
                    relevant_lines.append(part)

        if not is_codes and not relevant_lines:
            return None

        result_parts: list[str] = [f"BIS Standards search results for '{query}':"]
        if is_codes:
            result_parts.append(f"  IS Codes found: {', '.join(is_codes[:15])}")
        for line in relevant_lines[:8]:
            result_parts.append(f"  • {line[:200]}")

        return "\n".join(result_parts)

    except Exception as exc:
        logger.debug("BIS standards page search failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Strategy 3: BIS e-catalog via Playwright (JS-rendered)
# ---------------------------------------------------------------------------
def _search_with_playwright(query: str) -> Optional[str]:
    """
    Uses a headless Chromium browser to load the BIS e-catalog search and
    extract IS code listings from the dynamically rendered table.
    """
    try:
        import nest_asyncio
        nest_asyncio.apply()

        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=HEADERS["User-Agent"],
                extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
            )

            # BIS national standards Liferay search (JS-rendered results)
            search_url = (
                "https://www.bis.gov.in/index.php/standards/technical-department/national-standards"
                f"?p_p_id=com_liferay_portal_search_web_portlet_SearchPortlet"
                f"&p_p_lifecycle=0"
                f"&_com_liferay_portal_search_web_portlet_SearchPortlet_keywords={quote_plus(query)}"
            )
            try:
                page.goto(search_url, timeout=35_000, wait_until="networkidle")
                page.wait_for_timeout(3000)
            except PWTimeout:
                logger.debug("Playwright timed out loading BIS search page")
                browser.close()
                return None

            content = page.content()
            browser.close()

        soup = BeautifulSoup(content, "lxml")
        text = soup.get_text(" ", strip=True)
        is_codes = _extract_is_codes(text)

        # Grab result entries
        results: list[str] = []
        for sel in [".search-result", ".asset-summary", ".portlet-body li",
                    "article", ".entry-content"]:
            for item in soup.select(sel)[:10]:
                t = _clean(item.get_text(separator=" "))
                if len(t) > 30:
                    results.append(t[:200])
            if results:
                break

        if not is_codes and not results:
            return None

        parts: list[str] = [f"BIS Portal (dynamic) results for '{query}':"]
        if is_codes:
            parts.append(f"  IS Codes: {', '.join(is_codes[:15])}")
        for r in results[:6]:
            parts.append(f"  • {r}")
        return "\n".join(parts)

    except ImportError:
        logger.debug("Playwright not available")
    except Exception as exc:
        logger.debug("Playwright search failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Strategy 4: BIS Catalog keyword search via POST (Liferay AJAX)
# ---------------------------------------------------------------------------
def _search_bis_liferay_ajax(query: str) -> Optional[str]:
    """
    Attempts to hit the Liferay search portlet's AJAX endpoint directly,
    which sometimes returns structured JSON with standard titles.
    """
    try:
        url = "https://www.bis.gov.in/o/search/v1.0/search"
        payload = {
            "currentPage": 1,
            "delta": 10,
            "keywords": query,
            "scope": "everything",
        }
        resp = requests.post(
            url,
            json=payload,
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        hits = data.get("items") or data.get("hits") or data.get("results") or []
        if not hits:
            return None

        lines: list[str] = [f"BIS search results for '{query}':"]
        for item in hits[:10]:
            title = item.get("title") or item.get("name") or ""
            desc = item.get("description") or item.get("content") or ""
            if title:
                lines.append(f"  • {_clean(title)}")
                if desc:
                    lines.append(f"    {_clean(desc)[:150]}")

        is_codes = _extract_is_codes("\n".join(lines))
        if is_codes:
            lines.insert(1, f"  IS Codes mentioned: {', '.join(is_codes[:15])}")

        return "\n".join(lines) if len(lines) > 1 else None
    except Exception as exc:
        logger.debug("Liferay AJAX search failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def scrape_bis_portal(search_query: str) -> str:
    """
    Search the BIS portal for standards, IS codes, or product information.

    Tries four strategies in order (fastest/simplest first):
      1. BIS WordPress REST API (JSON)
      2. BIS national-standards search page (HTML + IS-code regex)
      3. Liferay AJAX endpoint (JSON)
      4. Playwright headless browser (JS-rendered, slowest)

    Args:
        search_query: Natural-language or IS-code query, e.g.
                      "petroleum products IS code" or
                      "certification procedure for cement".

    Returns:
        A plain-text string of extracted search results.
        Returns an empty string if all strategies fail.
    """
    logger.info("Scraping BIS portal for query: %r", search_query)

    # Normalize: strip common misspellings / expand abbreviations
    normalized = search_query.strip()

    # Strategy 1 — WP REST API (fast, structured)
    result = _search_bis_wp_api(normalized)
    if result:
        logger.info("BIS WP API returned results")
        return result

    time.sleep(0.3)

    # Strategy 2 — Standards page + regex
    result = _search_bis_standards_page(normalized)
    if result:
        logger.info("BIS standards page returned results")
        return result

    time.sleep(0.3)

    # Strategy 3 — Liferay AJAX
    result = _search_bis_liferay_ajax(normalized)
    if result:
        logger.info("Liferay AJAX returned results")
        return result

    time.sleep(0.3)

    # Strategy 4 — Playwright (JS, slowest, most complete)
    result = _search_with_playwright(normalized)
    if result:
        logger.info("Playwright returned results")
        return result

    logger.warning("All BIS scraping strategies failed for query: %r", search_query)
    return ""