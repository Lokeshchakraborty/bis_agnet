"""
BIS Multi-Source Authoritative Web Scraper & Regulatory Intelligence Engine
===========================================================================
Extracts authoritative Indian Standards (IS), Quality Control Orders (QCOs),
Compulsory Registration Scheme (CRS) categories, Conformity Assessment Schemes,
Fee structures, and Gazette Circulars from official Bureau of Indian Standards
and MeitY portals.

Capabilities:
  1. Official 'Know Your Standards' JSON API with multi-token relevance scoring & ranking
  2. Quality Control Orders (QCO) Registry & Gazette Orders (Ministries, enforcement dates, mandates)
  3. Compulsory Registration Scheme (CRS) Electronics Matrix (crsbis.in live products & standards)
  4. Conformity Assessment Schemes (Scheme-I ISI Mark, FMCS AIR rules, Hallmarking HUID, LRS Lab Recognition)
  5. Fee Schedules & MSME Concessions
  6. Gazette Notifications & Circulars with direct PDF links
  7. Typed Pydantic schema output & structured markdown context for RAG
"""
from __future__ import annotations

import concurrent.futures
import html
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote_plus

from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup
from src.config import CONFIG

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

REQUEST_TIMEOUT = getattr(CONFIG, "scraper_timeout", 2.5)  # bounded timeout for live official portal endpoints
IS_CODE_RE = re.compile(r"\bIS[\s:]*\d[\d\-]+(?:\s*\(Part\s*\d+\))?(?:[\s:]+\d{4})?", re.IGNORECASE)

# --------------------------------------------------------------------------- #
# Typed Pydantic Schemas for Structured Regulatory Scraping
# --------------------------------------------------------------------------- #
class StandardRecord(BaseModel):
    """Authoritative Indian Standard (IS) record."""
    standard_number: str = Field(description="Exact IS Code, e.g. 'IS 269:2015'")
    title: str = Field(description="Official standard title")
    title_hindi: str = Field(default="", description="Standard title in Hindi if available")
    status: str = Field(default="Active", description="Current status: Active, Withdrawn, or Under Review")
    published_on: str = Field(default="", description="Original date of publication")
    valid_upto: str = Field(default="", description="Validity expiry date")
    amendments: str = Field(default="", description="Notified amendments or revision details")
    department_id: Optional[int] = Field(default=None, description="BIS Technical Department ID")
    relevance_score: float = Field(default=0.0, description="Computed query relevance score")
    source_url: str = Field(default="https://standards.bis.gov.in/", description="Authoritative portal URL")


class QCORecord(BaseModel):
    """Quality Control Order (QCO) regulatory mandate."""
    ministry: str = Field(description="Issuing Central Ministry or Department (e.g. DPIIT, Ministry of Steel)")
    product: str = Field(description="Product, commodity, or item covered under mandatory order")
    standard_number: str = Field(description="Mandatory Indian Standard(s) required under QCO")
    enforcement_date: str = Field(description="Statutory enforcement or implementation deadline")
    order_title: str = Field(default="", description="Official Gazette Notification order title")
    order_url: str = Field(default="", description="URL or PDF download link to Gazette notification")
    status: str = Field(default="Mandatory / Notified", description="Enforcement status")


class CRSRecord(BaseModel):
    """Compulsory Registration Scheme (CRS) electronics and IT product."""
    product_category: str = Field(description="Product category under CRS")
    standard_number: str = Field(description="Applicable Indian Standard number")
    implementation_date: str = Field(description="Statutory enforcement date under CRS")
    ministry: str = Field(
        default="Ministry of Electronics and Information Technology (MeitY)",
        description="Regulating Ministry (MeitY or MNRE)",
    )
    sdoc_mandate: str = Field(
        default="Self-Declaration of Conformity (SDoC) + NABL/BIS-recognized test report required",
        description="Conformity requirement",
    )
    portal_url: str = Field(default="https://www.crsbis.in", description="CRS official portal")


class SchemeRecord(BaseModel):
    """Conformity Assessment Scheme and procedural rules."""
    scheme_name: str = Field(description="Name of BIS Conformity Assessment Scheme (e.g. Scheme-I, FMCS, Hallmark, LRS)")
    scope: str = Field(description="Target applicants and covered product categories")
    air_required: Optional[bool] = Field(default=None, description="Whether Authorized Indian Representative is mandatory")
    marking_symbol: str = Field(description="Prescribed certification mark (ISI Mark, CRS Mark, HUID, etc.)")
    workflow_summary: List[str] = Field(default_factory=list, description="Ordered application and compliance stages")
    portal_url: str = Field(description="Direct online application portal")
    fee_overview: str = Field(default="", description="Applicable fees and MSME financial concessions")


class CircularRecord(BaseModel):
    """Regulatory circular, guideline, or policy update."""
    title: str = Field(description="Headline or subject of circular")
    date: str = Field(default="", description="Issuance date")
    authority: str = Field(default="Bureau of Indian Standards", description="Issuing authority")
    url: str = Field(default="", description="URL to notice or document")
    summary: str = Field(default="", description="Key highlights or compliance directives")


class StructuredScrapeResult(BaseModel):
    """Unified container for all scraped standards and non-IS regulatory items."""
    query: str = Field(description="Original search query")
    standards: List[StandardRecord] = Field(default_factory=list, description="Matched and ranked Indian Standards")
    qcos: List[QCORecord] = Field(default_factory=list, description="Matched Quality Control Orders")
    crs_products: List[CRSRecord] = Field(default_factory=list, description="Matched CRS electronics products")
    schemes: List[SchemeRecord] = Field(default_factory=list, description="Matched Conformity Schemes & procedures")
    circulars: List[CircularRecord] = Field(default_factory=list, description="Matched Gazette circulars & notices")

    def has_results(self) -> bool:
        return bool(self.standards or self.qcos or self.crs_products or self.schemes or self.circulars)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def to_context_text(self, is_research: bool = False) -> str:
        """Format all scraped regulatory data into clean, structured Markdown for LLM context."""
        if not self.has_results():
            return ""

        sections: List[str] = []

        # 1. Regulatory Position Summary
        reg_lines = ["### [REGULATORY POSITION & STATUTORY MANDATE]"]
        if self.qcos:
            reg_lines.append(
                "• Statutory Mandate: MANDATORY COMPLIANCE under Bureau of Indian Standards Act, 2016 (Section 16 & Section 29).\n"
                "  Central Ministries have notified Quality Control Orders (QCOs) for these products.\n"
                "  No person shall manufacture, import, distribute, sell, or store for sale any notified product without a valid BIS Licence (ISI Mark / CRS Mark).\n"
                "  Penalties under Section 29 of the BIS Act, 2016: Imprisonment up to 2 years, or fine of ₹2,00,000 up to ₹5,00,000 (or up to 10x product value).\n"
                "  Foreign Manufacturers: Must obtain BIS certification under Foreign Manufacturers Certification Scheme (FMCS, Scheme-I) with an Authorized Indian Representative (AIR) and USD $10,000 PBG prior to dispatching goods to Indian customs."
            )
        else:
            reg_lines.append(
                "• Statutory Mandate: BIS certification in India is voluntary by default, unless the product is notified under a Quality Control Order (QCO) by the relevant Central Administrative Ministry or covered under MeitY Compulsory Registration Scheme (CRS)."
            )
        sections.append("\n".join(reg_lines))

        # 2. Official Standards
        if self.standards:
            std_limit = 12 if is_research else 6
            lines = ["### [OFFICIAL BIS INDIAN STANDARDS (IS)]"]
            for std in self.standards[:std_limit]:
                entry = f"• **{std.standard_number}**: {std.title}"
                details = []
                if std.status:
                    details.append(f"Status: {std.status}")
                if std.amendments:
                    details.append(f"Amendments: {std.amendments}")
                if std.published_on:
                    details.append(f"Published: {std.published_on}")
                if std.valid_upto:
                    details.append(f"Valid Upto: {std.valid_upto}")
                if details:
                    entry += f" ({', '.join(details)})"
                if std.source_url:
                    entry += f"\n  Portal URL: {std.source_url}"
                lines.append(entry)
            sections.append("\n".join(lines))

        # 3. Quality Control Orders (QCOs)
        if self.qcos:
            qco_limit = 8 if is_research else 5
            lines = ["### [QUALITY CONTROL ORDERS (QCO) & STATUTORY MANDATES]"]
            lines.append("Mandatory compliance under Bureau of Indian Standards Act, 2016 (Section 29 penalties apply for non-compliance):")
            for qco in self.qcos[:qco_limit]:
                entry = f"• **Product**: {qco.product}\n  - Ministry/Dept: {qco.ministry}\n  - Applicable Standard: {qco.standard_number}\n  - Enforcement Deadline: {qco.enforcement_date}"
                if qco.order_title:
                    entry += f"\n  - Order: {qco.order_title}"
                if qco.order_url:
                    entry += f"\n  - Gazette URL: {qco.order_url}"
                lines.append(entry)
            sections.append("\n".join(lines))

        # 4. Amendment & Enforcement Watchlist
        watchlist: List[str] = []
        for std in self.standards:
            if std.amendments:
                watchlist.append(f"• Standard **{std.standard_number}**: Notified amendments: {std.amendments}. Active Status: {std.status}. Verify compliance with latest revision.")
        for q in self.qcos:
            if q.enforcement_date:
                watchlist.append(f"• QCO for **{q.product}** ({q.standard_number}): Ministry: {q.ministry} | Enforcement Date: {q.enforcement_date} | Order: {q.order_title or 'Statutory Order'}")
        if watchlist:
            watch_limit = 10 if is_research else 5
            watch_lines = ["### [AMENDMENT & ENFORCEMENT WATCHLIST]"]
            watch_lines.extend(watchlist[:watch_limit])
            sections.append("\n".join(watch_lines))

        # 5. CRS Products & Electronics
        if self.crs_products:
            crs_limit = 6 if is_research else 4
            lines = ["### [COMPULSORY REGISTRATION SCHEME (CRS) PRODUCTS & ELECTRONICS]"]
            for crs in self.crs_products[:crs_limit]:
                entry = f"• **Category**: {crs.product_category}\n  - Required Standard: {crs.standard_number}\n  - Enforced Since: {crs.implementation_date}\n  - Mandate: {crs.sdoc_mandate}\n  - Portal: {crs.portal_url}"
                lines.append(entry)
            sections.append("\n".join(lines))

        # 6. Conformity Schemes & Procedural Frameworks
        if self.schemes:
            lines = ["### [CONFORMITY ASSESSMENT SCHEMES & PROCEDURAL REQUIREMENTS]"]
            for s in self.schemes:
                entry = f"• **Scheme**: {s.scheme_name}\n  - Scope: {s.scope}\n  - Marking: {s.marking_symbol}\n  - Portal: {s.portal_url}"
                if s.air_required is not None:
                    entry += f"\n  - AIR Requirement: {'Mandatory Authorized Indian Representative (AIR) under Form V' if s.air_required else 'Not Required for Domestic Manufacturers'}"
                if s.workflow_summary:
                    entry += "\n  - Workflow Stages:\n" + "\n".join(f"    {i}. {step}" for i, step in enumerate(s.workflow_summary, 1))
                if s.fee_overview:
                    entry += f"\n  - Fee Structure & Concessions: {s.fee_overview}"
                lines.append(entry)
            sections.append("\n".join(lines))

        # 7. Circulars & Notifications
        if self.circulars:
            circ_limit = 5 if is_research else 3
            lines = ["### [GAZETTE CIRCULARS & NOTIFICATIONS]"]
            for c in self.circulars[:circ_limit]:
                entry = f"• {c.title}"
                if c.date:
                    entry += f" (Dated: {c.date})"
                if c.url:
                    entry += f"\n  URL: {c.url}"
                if c.summary:
                    entry += f"\n  Details: {c.summary[:200]}"
                lines.append(entry)
            sections.append("\n".join(lines))

        # 8. Official Portal Citations
        citations = [
            "### [OFFICIAL BIS PORTALS & VERIFICATION CITATIONS]",
            "• Manakonline (e-BIS, ISI Mark & Hallmarking): https://manakonline.in",
            "• CRS Portal (Electronics SDoC Registration): https://www.crsbis.in",
            "• Standards Portal (Know Your Standards): https://standards.bis.gov.in",
            "• BIS Care Mobile App: Available on Android & iOS for ISI Mark (CM/L) and Gold HUID verification",
        ]
        sections.append("\n".join(citations))

        return "\n\n".join(sections)


# --------------------------------------------------------------------------- #
# In-Memory Cache with TTL for Performance and Zero Redundant Network Calls
# --------------------------------------------------------------------------- #
MAX_SCRAPER_CACHE_ENTRIES = 256
_scraper_cache: Dict[str, Tuple[float, str]] = {}
_structured_cache: Dict[str, Tuple[float, StructuredScrapeResult]] = {}
_cached_qco_registry: List[QCORecord] = []
_qco_registry_timestamp: float = 0.0
_cached_crs_products: List[CRSRecord] = []
_crs_products_timestamp: float = 0.0

CACHE_TTL_SECONDS = 3600.0  # 1 hour TTL for regulatory tables


def _clean(text: str) -> str:
    """Collapse consecutive whitespace, unescape HTML entities, and trim."""
    if not text:
        return ""
    text = html.unescape(text)
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


def _format_amendments(item: dict) -> str:
    """Format single or multiple amendments from live BIS portal item dictionary."""
    raw_list = (
        item.get("amendments")
        or item.get("amendmentList")
        or item.get("amendmentDetails")
        or item.get("amendmentsList")
    )
    if isinstance(raw_list, list) and raw_list:
        formatted = []
        for a in raw_list:
            if isinstance(a, dict):
                no = a.get("amendmentNo") or a.get("amendmentNumber") or a.get("number") or a.get("title") or ""
                dt = a.get("publishedOn") or a.get("date") or ""
                txt = f"Amd {no}" if no else str(a)
                if dt:
                    txt += f" ({dt})"
                formatted.append(txt)
            elif a:
                formatted.append(f"Amd {a}")
        if formatted:
            return ", ".join(formatted)

    amd_no = str(item.get("amendmentNumber") or item.get("amendmentNo") or "").strip()
    no_of_amds = str(item.get("noOfAmendments") or item.get("totalAmendments") or "").strip()

    if amd_no and no_of_amds and amd_no != no_of_amds:
        return f"Amd {amd_no} (Total: {no_of_amds})"
    elif amd_no:
        return f"Amd {amd_no}"
    elif no_of_amds:
        return f"{no_of_amds} Amendment(s)"

    return ""


# --------------------------------------------------------------------------- #
# Query Preprocessing & Candidate Generation
# --------------------------------------------------------------------------- #
STOP_WORDS = {
    "what", "is", "are", "tell", "me", "about", "details", "specification",
    "specifications", "standards", "standard", "for", "of", "the", "a", "an",
    "kya", "hai", "hain", "batao", "bataiye", "ke", "liye", "mein", "rules",
    "procedure", "process", "list", "search", "information", "please", "want",
    "need", "can", "you", "how", "to", "apply", "get", "do", "does", "kaise",
    "kare", "karen", "tarika", "vidhi", "guidelines", "order", "orders"
}


def _extract_search_candidates(query: str) -> Tuple[List[str], Optional[str]]:
    """
    Extract exact IS code if present and produce cleaned product/subject candidates.
    Returns:
        (candidate_queries_list, exact_is_code_or_None)
    """
    candidates: List[str] = []
    is_match = re.search(r"\bIS\s*:?\s*\d+[\d\-]*(?:\s*\(Part\s*\d+\))?(?:[\s:]+\d{4})?", query, re.IGNORECASE)
    exact_is: Optional[str] = None
    if is_match:
        exact_is = re.sub(r"\s+", " ", is_match.group(0).replace(":", " ")).strip()
        candidates.append(exact_is)

    # Clean conversational filler
    tokens = re.findall(r"[\w\-]+", query.lower())
    meaningful = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]
    if meaningful:
        candidate_phrase = " ".join(meaningful)
        if candidate_phrase not in candidates:
            candidates.append(candidate_phrase)

    raw_clean = _clean(query)
    if raw_clean and raw_clean not in candidates:
        candidates.append(raw_clean)

    return candidates, exact_is


# --------------------------------------------------------------------------- #
# 1. Standards Search with Relevance Scoring & Ranking
# --------------------------------------------------------------------------- #
def _score_standard(item: dict, query_tokens: Set[str], exact_is: Optional[str]) -> float:
    """Compute relevance score for a standard item against query terms."""
    score = 0.0
    num = (item.get("standardNumber") or "").lower()
    name = (item.get("standardName") or "").lower()

    # Exact standard number match gets highest boost
    if exact_is:
        clean_exact = re.sub(r"[^\w]", "", exact_is.lower())
        clean_num = re.sub(r"[^\w]", "", num)
        if clean_exact in clean_num:
            score += 50.0

    # Token overlap scoring
    for t in query_tokens:
        if len(t) < 3:
            continue
        if t in num:
            score += 15.0
        if t in name:
            score += 8.0

    # Active status preference
    status_str = (item.get("status") or item.get("standardStatus") or "").lower()
    if "withdrawn" in status_str:
        score -= 10.0

    return score


def _search_know_your_standards_api(query: str) -> List[StandardRecord]:
    """Query official BIS 'Know Your Standards' JSON API with relevance ranking."""
    candidates, exact_is = _extract_search_candidates(query)
    query_tokens = set(re.findall(r"[\w]+", query.lower())) - STOP_WORDS

    url = "https://standardsadmin.bis.gov.in/review-service/searchKnowStandards"
    headers = {
        **HEADERS,
        "Referer": "https://standards.bis.gov.in/",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }

    seen_numbers: set[str] = set()
    collected: List[StandardRecord] = []

    for term in candidates[:3]:
        try:
            payload = {
                "searchText": term,
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

            for it in items:
                std_num = _clean(it.get("standardNumber") or it.get("matched_standard") or "")
                std_name = _clean(it.get("standardName") or "")
                if not std_num or std_num in seen_numbers:
                    continue
                seen_numbers.add(std_num)

                score = _score_standard(it, query_tokens, exact_is)
                # Filter out completely irrelevant items unless query was very broad
                if query_tokens and score <= 0 and len(query_tokens) > 1:
                    continue

                status_txt = _clean(it.get("status") or it.get("standardStatus") or "Active")
                if it.get("withdrawStatus") == 1 or it.get("withdrawOn"):
                    status_txt = "Withdrawn"

                record = StandardRecord(
                    standard_number=std_num,
                    title=std_name,
                    title_hindi=_clean(it.get("standardNameInHindi") or ""),
                    status=status_txt,
                    published_on=_clean(it.get("publishedOn") or ""),
                    valid_upto=_clean(it.get("validUpto") or ""),
                    amendments=_format_amendments(it),
                    department_id=it.get("departmentId"),
                    relevance_score=score,
                    source_url="https://standards.bis.gov.in/",
                )
                collected.append(record)

            if collected:
                break
        except Exception as exc:
            logger.debug("Know Your Standards API search failed for candidate '%s': %s", term, exc)

    # Sort descending by relevance score
    collected.sort(key=lambda r: r.relevance_score, reverse=True)
    return collected[:15]


# --------------------------------------------------------------------------- #
# 2. Quality Control Orders (QCO) Registry Scraper (Upcoming & Active)
# --------------------------------------------------------------------------- #
def _fetch_live_qco_registry() -> List[QCORecord]:
    """Scrape the official BIS upcoming and notified Quality Control Orders table."""
    global _cached_qco_registry, _qco_registry_timestamp
    now = time.time()
    if _cached_qco_registry and (now - _qco_registry_timestamp) < CACHE_TTL_SECONDS:
        return _cached_qco_registry

    qco_url = "https://www.bis.gov.in/upcoming-qcos-notified-and-due-for-implementation/?lang=en"
    records: List[QCORecord] = []

    try:
        resp = requests.get(qco_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")
                for r in rows[1:]:
                    cells = [_clean(c.get_text()) for c in r.find_all(["th", "td"])]
                    if len(cells) >= 5:
                        # cells: [Sr. No., Ministry/ Department, Product, Indian Standard, Enforcement date]
                        ministry = cells[1]
                        product = cells[2]
                        std_num = cells[3]
                        enf_date = cells[4]
                        if product and (std_num or ministry):
                            records.append(
                                QCORecord(
                                    ministry=ministry,
                                    product=product,
                                    standard_number=std_num,
                                    enforcement_date=enf_date,
                                    order_title=f"{product} Quality Control Order",
                                    order_url=qco_url,
                                    status="Notified / In Force or Upcoming",
                                )
                            )
            if records:
                _cached_qco_registry = records
                _qco_registry_timestamp = now
                logger.info("Scraped %d authoritative QCO entries from BIS registry.", len(records))
                return records
    except Exception as exc:
        logger.warning("Failed to fetch live QCO registry: %s", exc)

    return _cached_qco_registry


def _search_qcos(query: str) -> List[QCORecord]:
    """Match query against Quality Control Orders by product, standard, or ministry."""
    registry = _fetch_live_qco_registry()
    if not registry:
        return []

    tokens = set(re.findall(r"[\w]+", query.lower())) - STOP_WORDS
    matched: List[Tuple[float, QCORecord]] = []

    for qco in registry:
        p_lower = qco.product.lower()
        m_lower = qco.ministry.lower()
        s_lower = qco.standard_number.lower()

        score = 0.0
        for t in tokens:
            if len(t) < 3:
                continue
            if t in p_lower:
                score += 10.0
            if t in s_lower:
                score += 15.0
            if t in m_lower:
                score += 5.0

        if score > 0:
            matched.append((score, qco))

    matched.sort(key=lambda x: x[0], reverse=True)
    return [qco for _, qco in matched[:12]]


# --------------------------------------------------------------------------- #
# 3. Compulsory Registration Scheme (CRS) Electronics Scraper (crsbis.in)
# --------------------------------------------------------------------------- #
def _fetch_live_crs_products() -> List[CRSRecord]:
    """Scrape official Compulsory Registration Scheme products from crsbis.in."""
    global _cached_crs_products, _crs_products_timestamp
    now = time.time()
    if _cached_crs_products and (now - _crs_products_timestamp) < CACHE_TTL_SECONDS:
        return _cached_crs_products

    crs_url = "https://www.crsbis.in/BIS/products.do"
    records: List[CRSRecord] = []

    try:
        resp = requests.get(crs_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if table:
                for r in table.find_all("tr")[1:]:
                    cells = [_clean(c.get_text()) for c in r.find_all(["th", "td"])]
                    if len(cells) >= 4:
                        # cells: [Sl. No., Product, Indian Standard number, Date of Implementation]
                        prod = cells[1]
                        std_num = cells[2]
                        impl_date = cells[3]
                        if prod:
                            records.append(
                                CRSRecord(
                                    product_category=prod,
                                    standard_number=std_num,
                                    implementation_date=impl_date,
                                    ministry="Ministry of Electronics and Information Technology (MeitY) / MNRE",
                                    sdoc_mandate="Mandatory Self-Declaration of Conformity + NABL/BIS Lab Test Report",
                                    portal_url=crs_url,
                                )
                            )
            if records:
                _cached_crs_products = records
                _crs_products_timestamp = now
                logger.info("Scraped %d live CRS electronics products from crsbis.in.", len(records))
                return records
    except Exception as exc:
        logger.warning("Failed to fetch live CRS products table: %s", exc)

    return _cached_crs_products


def _search_crs_products(query: str) -> List[CRSRecord]:
    """Match query against electronics/IT goods under CRS."""
    products = _fetch_live_crs_products()
    if not products:
        return []

    tokens = set(re.findall(r"[\w]+", query.lower())) - STOP_WORDS
    matched: List[Tuple[float, CRSRecord]] = []

    for crs in products:
        cat_lower = crs.product_category.lower()
        std_lower = crs.standard_number.lower()

        score = 0.0
        for t in tokens:
            if len(t) < 3:
                continue
            if t in cat_lower:
                score += 10.0
            if t in std_lower:
                score += 15.0

        if score > 0:
            matched.append((score, crs))

    matched.sort(key=lambda x: x[0], reverse=True)
    return [crs for _, crs in matched[:5]]


# --------------------------------------------------------------------------- #
# 4. Conformity Assessment Schemes, Rules & Fee Schedules (Non-IS Knowledge)
# --------------------------------------------------------------------------- #
AUTHORITATIVE_SCHEMES: List[SchemeRecord] = [
    SchemeRecord(
        scheme_name="Scheme-I (Standard Product Certification — ISI Mark)",
        scope="Domestic manufacturers across engineering, chemical, electrical, civil, food, and consumer goods covered by mandatory QCOs or voluntary standards.",
        air_required=False,
        marking_symbol="BIS Standard Mark (ISI Mark triangle/circle logo with License No. CM/L-XXXXXXX)",
        workflow_summary=[
            "Identification of applicable Indian Standard (IS Code) and Scheme of Testing and Inspection (STI).",
            "Online submission of application on Manakonline (https://manakonline.in).",
            "Initial factory audit and sample drawing by BIS Technical Officers.",
            "Independent sample testing at BIS-recognized/NABL accredited laboratory.",
            "Grant of Licence (CML Number) valid initially for 1 or 2 years, renewable up to 5 years.",
        ],
        portal_url="https://manakonline.in",
        fee_overview="Application fee: ₹1,000. Annual licence fee: ₹1,000. Minimum marking fee varies by product. Concession: 50% for Micro enterprises, 20% for Small enterprises and Women entrepreneurs.",
    ),
    SchemeRecord(
        scheme_name="Foreign Manufacturers Certification Scheme (FMCS)",
        scope="Overseas manufacturers exporting products to India covered under mandatory BIS QCOs.",
        air_required=True,
        marking_symbol="ISI Mark with CML Number and designated country of origin",
        workflow_summary=[
            "Nomination of an Authorized Indian Representative (AIR) residing in India via Form V undertaking.",
            "Online submission of application via FMCS portal on Manakonline with technical infrastructure details.",
            "Payment of application fee ($1,000 USD approx.) and factory inspection charges.",
            "Physical inspection and factory audit of the foreign plant by BIS inspecting officers.",
            "Drawing and testing of samples at BIS-recognized laboratories in India.",
            "Submission of Performance Bank Guarantee (PBG) of USD $10,000 from an RBI-approved bank before grant of licence.",
        ],
        portal_url="https://manakonline.in/MANAK/fmcsPortal",
        fee_overview="Application fee: USD $1,000. Factory inspection per diem & travel costs borne by applicant. PBG of USD $10,000 mandatory.",
    ),
    SchemeRecord(
        scheme_name="Compulsory Registration Scheme (CRS)",
        scope="Electronic products, IT goods, LED lighting, and Solar PV modules notified by MeitY and MNRE.",
        air_required=True,
        marking_symbol="Standard BIS CRS Mark containing the assigned Registration Number (R-XXXXXXXX) and applicable IS Standard",
        workflow_summary=[
            "Sample testing of the electronic product at a BIS-recognized testing laboratory in India.",
            "Obtaining test report within 90 days of issuance.",
            "Online application submission on CRS portal (https://crsbis.in) with Self-Declaration of Conformity (SDoC).",
            "Appointment of Authorized Indian Representative (AIR) for foreign applicants.",
            "Scrutiny by BIS and grant of R-Number (Registration Number). Valid for 2 years, renewable up to 5 years.",
        ],
        portal_url="https://crsbis.in",
        fee_overview="Application fee: ₹1,000 per model series. Processing fee: ₹50,000. No marking fee.",
    ),
    SchemeRecord(
        scheme_name="Hallmarking Scheme (Gold & Silver Jewellery)",
        scope="Gold and silver jewellery and artefacts sold by jewellers in notified mandatory hallmarking districts across India.",
        air_required=False,
        marking_symbol="Three Mandatory Marks: 1. BIS Triangle Logo, 2. Purity/Fineness (e.g. 22K916, 18K750, 14K585), 3. 6-digit alphanumeric HUID (Hallmark Unique Identification)",
        workflow_summary=[
            "Online Jeweller Registration on Manakonline Hallmarking portal.",
            "Submission of PAN, GST registration, and business address proof.",
            "Instant generation of Jeweller Certificate of Registration (valid for 5 years).",
            "Submission of jewellery lots to authorized Assaying and Hallmarking Centres (AHC).",
            "XRF testing, fire assaying, and laser engraving of 6-digit HUID per individual jewellery piece.",
            "Consumer verification of HUID authenticity via BIS Care Mobile App.",
        ],
        portal_url="https://manakonline.in",
        fee_overview="Registration fee: ₹0 (Free for micro enterprises with turnover < ₹5 Crore), ₹2,500 to ₹8,000 based on turnover slabs. Hallmarking fee at AHC: ₹45 per gold jewellery piece.",
    ),
    SchemeRecord(
        scheme_name="Laboratory Recognition Scheme (LRS)",
        scope="Third-party, commercial, and government testing laboratories testing industrial and consumer products against Indian Standards.",
        air_required=False,
        marking_symbol="BIS Recognized Laboratory Accreditation Mark",
        workflow_summary=[
            "Laboratory must hold active NABL accreditation as per ISO/IEC 17025 for specific IS test methods.",
            "Submission of application via LIMS portal on Manakonline with scope of testing and equipment calibration records.",
            "Assessment by BIS Technical Audit Team.",
            "Participation in proficiency testing and inter-laboratory comparison.",
            "Grant of recognition for an initial period of 3 years.",
        ],
        portal_url="https://manakonline.in",
        fee_overview="Application fee: ₹20,000. Annual recognition fee: ₹50,000. Audit expenses borne by lab.",
    ),
]


def _match_schemes_and_procedures(query: str) -> List[SchemeRecord]:
    """Match query against relevant BIS Conformity Assessment schemes and guidelines."""
    q_lower = query.lower()
    matched: List[SchemeRecord] = []

    # Scheme-1 (ISI Mark)
    if any(k in q_lower for k in ["scheme 1", "scheme-1", "scheme-i", "scheme i", "isi mark", "cml", "product certification", "sti", "marking fee", "factory audit"]):
        matched.append(AUTHORITATIVE_SCHEMES[0])

    # FMCS (Foreign Manufacturers & AIR)
    if any(k in q_lower for k in ["fmcs", "foreign manufacturer", "air", "authorized indian representative", "pbg", "bank guarantee", "form v", "import to india"]):
        matched.append(AUTHORITATIVE_SCHEMES[1])

    # CRS (Electronics & IT SDoC)
    if any(k in q_lower for k in ["crs", "compulsory registration", "electronics", "meity", "sdoc", "r-number", "r number", "it goods", "adapter", "mobile", "crsbis"]):
        matched.append(AUTHORITATIVE_SCHEMES[2])

    # Hallmarking (HUID, Gold, Silver)
    if any(k in q_lower for k in ["hallmark", "hallmarking", "huid", "gold", "silver", "jeweller", "jewellery", "ahc", "22k", "18k", "24k", "916", "bis care app"]):
        matched.append(AUTHORITATIVE_SCHEMES[3])

    # LRS (Lab Recognition)
    if any(k in q_lower for k in ["laboratory", "lab", "lrs", "nabl", "iso 17025", "iso/iec 17025", "testing lab", "lims", "lab recognition"]):
        matched.append(AUTHORITATIVE_SCHEMES[4])

    # If asking about fees generally, include Scheme-1 and Hallmarking fees
    if "fee" in q_lower or "fees" in q_lower or "cost" in q_lower or "charge" in q_lower:
        if AUTHORITATIVE_SCHEMES[0] not in matched:
            matched.append(AUTHORITATIVE_SCHEMES[0])

    return matched


# --------------------------------------------------------------------------- #
# 5. Live Circulars, Gazette Orders & Media Attachments (WordPress API)
# --------------------------------------------------------------------------- #
def _search_bis_circulars_and_media(query: str) -> List[CircularRecord]:
    """Search WordPress API for Gazette orders, circulars, and media attachment PDFs."""
    circulars: List[CircularRecord] = []
    candidates, _ = _extract_search_candidates(query)
    search_term = candidates[0] if candidates else query

    # 1. CRS Portal Circulars
    try:
        crs_circ_url = "https://www.crsbis.in/BIS/biscirculars.do"
        r = requests.get(crs_circ_url, headers=HEADERS, timeout=4)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for row in soup.find_all("tr")[1:6]:
                cells = [_clean(c.get_text()) for c in row.find_all(["th", "td"])]
                if len(cells) >= 2:
                    subj = cells[1]
                    if any(t in subj.lower() for t in re.findall(r"\w+", query.lower()) if len(t) > 3) or "guideline" in query.lower():
                        circulars.append(
                            CircularRecord(
                                title=subj,
                                authority="BIS / MeitY CRS Portal",
                                url=crs_circ_url,
                                summary="Official guideline circular issued under Compulsory Registration Scheme.",
                            )
                        )
    except Exception as exc:
        logger.debug("CRS circulars fetch skipped: %s", exc)

    # 2. BIS WordPress Media & Gazette Notifications
    try:
        wp_url = f"https://www.bis.gov.in/wp-json/wp/v2/search?search={quote_plus(search_term)}&per_page=5&type=post"
        resp = requests.get(wp_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            for item in resp.json()[:4]:
                title = _clean(item.get("title", ""))
                url = item.get("url", "")
                sub = item.get("subtype", "")

                if title:
                    circulars.append(
                        CircularRecord(
                            title=title,
                            authority="Bureau of Indian Standards",
                            url=url,
                            summary=f"Official regulatory order/circular ({sub}) published on bis.gov.in.",
                        )
                    )
    except Exception as exc:
        logger.debug("WordPress circular search failed for '%s': %s", search_term, exc)

    return circulars[:5]


# --------------------------------------------------------------------------- #
# High-Level Unified Scraping APIs
# --------------------------------------------------------------------------- #
def scrape_structured(search_query: str) -> StructuredScrapeResult:
    """
    Search across BIS standards, Quality Control Orders (QCOs), CRS electronics,
    Conformity Assessment Schemes, and Gazette circulars.

    Returns:
        StructuredScrapeResult containing typed, verified records.
    """
    normalized = search_query.strip().lower()
    if not normalized:
        return StructuredScrapeResult(query=search_query)

    now = time.time()
    if normalized in _structured_cache:
        cached_time, cached_res = _structured_cache[normalized]
        if (now - cached_time) < CACHE_TTL_SECONDS:
            logger.info("Scraper structured cache HIT for query: %r", normalized)
            return cached_res
        else:
            del _structured_cache[normalized]

    logger.info("Executing structured multi-source regulatory scrape for: %r", normalized)

    # Parallelize multi-source regulatory scrape across 5 sources with strict timeout budgets
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    try:
        f_std = executor.submit(_search_know_your_standards_api, normalized)
        f_qco = executor.submit(_search_qcos, normalized)
        f_crs = executor.submit(_search_crs_products, normalized)
        f_sch = executor.submit(_match_schemes_and_procedures, normalized)
        f_circ = executor.submit(_search_bis_circulars_and_media, normalized)

        def _safe_get(fut, default, timeout=2.5):
            try:
                return fut.result(timeout=timeout)
            except Exception as exc:
                logger.debug("Scraper sub-task timed out or failed (%s)", exc)
                return default

        standards = _safe_get(f_std, [], timeout=2.5)
        qcos = _safe_get(f_qco, [], timeout=2.5)
        crs_prods = _safe_get(f_crs, [], timeout=2.5)
        schemes = _safe_get(f_sch, [], timeout=1.0)
        circulars = _safe_get(f_circ, [], timeout=2.0)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    result = StructuredScrapeResult(
        query=search_query,
        standards=standards,
        qcos=qcos,
        crs_products=crs_prods,
        schemes=schemes,
        circulars=circulars,
    )

    if result.has_results():
        if len(_structured_cache) >= MAX_SCRAPER_CACHE_ENTRIES:
            oldest_key = min(_structured_cache, key=lambda k: _structured_cache[k][0])
            _structured_cache.pop(oldest_key, None)
        _structured_cache[normalized] = (now, result)

    return result


def scrape_bis_portal(search_query: str, is_research: bool = False) -> str:
    """
    Main interface for Agent Nodes and RAG pipelines.
    Returns rich, structured plain-text / Markdown context for LLM synthesis.
    """
    normalized = search_query.strip().lower()
    if not normalized:
        return ""

    cache_key = f"{normalized}:research={is_research}"
    now = time.time()
    if cache_key in _scraper_cache:
        cached_time, cached_text = _scraper_cache[cache_key]
        if (now - cached_time) < CACHE_TTL_SECONDS:
            return cached_text
        else:
            del _scraper_cache[cache_key]

    structured = scrape_structured(search_query)
    context_text = structured.to_context_text(is_research=is_research)

    if structured.has_results() and context_text.strip():
        if len(_scraper_cache) >= MAX_SCRAPER_CACHE_ENTRIES:
            oldest_key = min(_scraper_cache, key=lambda k: _scraper_cache[k][0])
            _scraper_cache.pop(oldest_key, None)
        _scraper_cache[cache_key] = (now, context_text)

    return context_text
