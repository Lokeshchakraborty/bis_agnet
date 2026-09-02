"""
BIS Portal & Standards Web Scraper
==================================
Extracts authoritative standard titles, IS codes, and portal information from the
Bureau of Indian Standards website and API endpoints.

Strategies (in execution order):
  1. BIS 'Know Your Standards' Official API (standardsadmin.bis.gov.in)
  2. BIS WordPress Search API
  3. BIS National Standards Page HTML Parser with IS Code extraction
  4. Playwright Headless Browser fallback (optional)
"""
from __future__ import annotations

import logging
import re
import time
from typing import List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("bis_scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_TIMEOUT = 15  # seconds
IS_CODE_RE = re.compile(r"\bIS[\s:]*\d[\d\-]+(?:[\s:]+\d{4})?", re.IGNORECASE)


def _clean(text: str) -> str:
    """Collapse consecutive whitespace and trim."""
    return re.sub(r"\s+", " ", text).strip()


def _extract_is_codes(text: str) -> List[str]:
    """Return a de-duplicated list of IS codes found in text."""
    seen: set[str] = set()
    result: List[str] = []
    for m in IS_CODE_RE.finditer(text):
        code = _clean(m.group())
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


def _search_know_your_standards_api(query: str) -> Optional[str]:
    """Query the official BIS 'Know Your Standards' JSON API."""
    is_match = re.search(r"\bIS\s*:?\s*\d+[\d\-]*(?:\s*\(Part\s*\d+\))?", query, re.IGNORECASE)
    search_candidates: List[str] = []
    if is_match:
        search_candidates.append(re.sub(r"\s+", " ", is_match.group(0).replace(":", " ")).strip())

    cleaned = re.sub(
        r"\b(what|is|tell|me|about|give|details|of|specification|specifications|standards|standard|for|kya|hai|batao|bataiye|ke|liye)\b",
        "",
        query,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[^\w\s]", " ", cleaned).strip()
    if cleaned and cleaned not in search_candidates:
        search_candidates.append(cleaned)
    if query.strip() not in search_candidates:
        search_candidates.append(query.strip())

    url = "https://standardsadmin.bis.gov.in/review-service//searchKnowStandards"
    headers = {
        **HEADERS,
        "Referer": "https://standards.bis.gov.in/",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }

    for search_term in search_candidates:
        try:
            payload = {
                "searchText": search_term,
                "token": None,
                "refreshToken": None,
                "clientId": None,
                "clientSecret": None,
                "sub": None,
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue
            data = resp.json()
            items = data.get("data")
            if not isinstance(items, list) or not items:
                continue

            lines: List[str] = [f"BIS 'Know Your Standards' results for '{search_term}':"]
            for item in items[:10]:
                num = item.get("standardNumber") or item.get("matched_standard") or ""
                name = item.get("standardName") or ""
                pub = item.get("publishedOn") or ""
                valid = item.get("validUpto") or ""
                if num or name:
                    entry = f"  • {num}: {name}"
                    details = []
                    if pub:
                        details.append(f"Published: {pub}")
                    if valid:
                        details.append(f"Valid Upto: {valid}")
                    if details:
                        entry += f" ({', '.join(details)})"
                    lines.append(entry)

            if len(lines) > 1:
                return "\n".join(lines)
        except Exception as exc:
            logger.debug("Know Your Standards API search failed for '%s': %s", search_term, exc)

    return None


def _search_bis_wp_api(query: str) -> Optional[str]:
    """Search BIS portal via WordPress REST API."""
    try:
        url = f"https://www.bis.gov.in/wp-json/wp/v2/search?search={quote_plus(query)}&per_page=8&type=post"
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list) or not data:
            return None

        lines: List[str] = [f"BIS Portal pages matching '{query}':"]
        for item in data[:6]:
            title = item.get("title", "")
            page_url = item.get("url", "")
            if title:
                lines.append(f"  • {title}")
                if page_url:
                    lines.append(f"    URL: {page_url}")

        if len(lines) > 1:
            return "\n".join(lines)
    except Exception as exc:
        logger.debug("BIS WordPress API failed for '%s': %s", query, exc)

    return None


def _search_bis_standards_page(query: str) -> Optional[str]:
    """Parse the BIS national standards search page."""
    try:
        url = "https://www.bis.gov.in/index.php/standards/technical-department/national-standards"
        params = {
            "p_p_id": "com_liferay_portal_search_web_portlet_SearchPortlet",
            "p_p_lifecycle": "0",
            "_com_liferay_portal_search_web_portlet_SearchPortlet_keywords": query,
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        is_codes = _extract_is_codes(text)
        keywords = re.compile(
            r"\b(IS\s*\d|standard|specification|petroleum|product|certif|hallmark|registration)\b",
            re.IGNORECASE,
        )
        relevant_lines: List[str] = []
        for part in re.split(r"[।\.\n]{1,3}", text):
            part = _clean(part)
            if len(part) > 30 and keywords.search(part):
                ascii_ratio = sum(1 for c in part if ord(c) < 128) / max(len(part), 1)
                if ascii_ratio > 0.5:
                    relevant_lines.append(part)

        if not is_codes and not relevant_lines:
            return None

        result_parts: List[str] = [f"BIS Standards search results for '{query}':"]
        if is_codes:
            result_parts.append(f"  IS Codes found: {', '.join(is_codes[:15])}")
        for line in relevant_lines[:6]:
            result_parts.append(f"  • {line[:200]}")

        return "\n".join(result_parts)
    except Exception as exc:
        logger.debug("BIS standards page search failed: %s", exc)

    return None


def _search_with_playwright(query: str) -> Optional[str]:
    """Headless browser fallback for dynamic JavaScript-rendered tables."""
    try:
        import nest_asyncio
        nest_asyncio.apply()
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=HEADERS["User-Agent"],
                extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
            )
            search_url = (
                "https://www.bis.gov.in/index.php/standards/technical-department/national-standards"
                f"?p_p_id=com_liferay_portal_search_web_portlet_SearchPortlet"
                f"&p_p_lifecycle=0"
                f"&_com_liferay_portal_search_web_portlet_SearchPortlet_keywords={quote_plus(query)}"
            )
            page.goto(search_url, timeout=25_000, wait_until="networkidle")
            page.wait_for_timeout(2000)
            content = page.content()
            browser.close()

        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(" ", strip=True)
        is_codes = _extract_is_codes(text)

        results: List[str] = []
        for sel in [".search-result", ".asset-summary", ".portlet-body li", "article"]:
            for item in soup.select(sel)[:6]:
                t = _clean(item.get_text(separator=" "))
                if len(t) > 30:
                    results.append(t[:200])
            if results:
                break

        if not is_codes and not results:
            return None

        parts: List[str] = [f"BIS Portal (dynamic) results for '{query}':"]
        if is_codes:
            parts.append(f"  IS Codes: {', '.join(is_codes[:15])}")
        for r in results[:5]:
            parts.append(f"  • {r}")
        return "\n".join(parts)
    except Exception as exc:
        logger.debug("Playwright search fallback skipped or failed: %s", exc)
        return None


def scrape_bis_portal(search_query: str) -> str:
    """
    Search the BIS portal across all available endpoints.

    Returns:
        Formatted plain-text search results, or empty string on total failure.
    """
    normalized = search_query.strip()
    logger.info("Scraping BIS portal for query: %r", normalized)

    # 1. Official Know Your Standards JSON API
    result = _search_know_your_standards_api(normalized)
    if result:
        return result

    time.sleep(0.2)

    # 2. WordPress Search API
    result = _search_bis_wp_api(normalized)
    if result:
        return result

    time.sleep(0.2)

    # 3. Standards page HTML search
    result = _search_bis_standards_page(normalized)
    if result:
        return result

    time.sleep(0.2)

    # 4. Playwright headless browser fallback
    result = _search_with_playwright(normalized)
    if result:
        return result

    logger.warning("All scraping strategies returned empty results for '%s'", search_query)
    return ""
