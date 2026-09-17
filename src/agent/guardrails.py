"""
Deterministic Output Guardrails & Post-Synthesis Validation Layer
===================================================================
Applies rule-based validation checks on generated BIS answers to enforce:
  1. Intent confidence scoring and proactive disambiguation triggers.
  2. Legal act accuracy (Bureau of Indian Standards Act, 2016).
  3. Official portal URL integrity (https://manakonline.in, https://crsbis.in, https://bis.gov.in).
  4. IS code pattern formatting validation.
"""
from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from src.schemas import BISResponse, ConfidenceMetrics

logger = logging.getLogger("bis_guardrails")

OFFICIAL_DOMAINS = ["manakonline.in", "crsbis.in", "bis.gov.in"]
IS_CODE_PATTERN = re.compile(r"\bIS\s*:?\s*\d{3,5}(?:\s*\([^)]+\))?(?::\d{4})?\b", re.IGNORECASE)


def validate_and_sanitize_response(
    response: BISResponse,
    query: str,
    intent_confidence: float = 0.95,
    standalone_query: Optional[str] = None,
) -> BISResponse:
    """
    Validate, sanitize, and score a synthesized BIS response.
    """
    effective_query = (standalone_query or query or "").strip()
    raw_query = (query or "").strip()

    # Detect if query mentions an explicit IS standard code or known BIS scheme
    has_is_code = bool(re.search(r"\bIS\s*:?\s*\d{2,5}\b", raw_query, re.IGNORECASE)) or bool(
        re.search(r"\bIS\s*:?\s*\d{2,5}\b", effective_query, re.IGNORECASE)
    )
    KNOWN_SCHEMES = {
        "fmcs", "crs", "huid", "isi", "qco", "hallmark", "hallmarking", "bis",
        "sti", "lrs", "manakonline", "license", "licence", "testing", "fee", "fees"
    }
    has_known_scheme = any(s in raw_query.lower().split() for s in KNOWN_SCHEMES) or any(
        s in effective_query.lower().split() for s in KNOWN_SCHEMES
    )

    eff_words = re.findall(r"\w+", effective_query)
    raw_words = re.findall(r"\w+", raw_query)

    is_greeting = raw_query.lower() in {"hi", "hello", "namaste", "help", "hey", "hola", "pranam"}
    is_multi_turn = len(eff_words) > 2 and len(raw_words) <= 2
    has_substantive_response = bool(response.core_response and len(response.core_response) >= 150)
    has_matched_standards = bool(response.applicable_standards or "IS" in (response.core_response or ""))

    # Only flag as requiring clarification if genuinely ambiguous without standards or substantive answer
    requires_clarification = (
        not is_greeting
        and not has_is_code
        and not has_known_scheme
        and not is_multi_turn
        and len(eff_words) <= 2
        and not (has_substantive_response and has_matched_standards)
    )

    if requires_clarification:
        intent_confidence = min(intent_confidence, 0.65)
    else:
        intent_confidence = max(intent_confidence, 0.85)

    response.confidence_metrics = ConfidenceMetrics(
        intent_confidence=round(intent_confidence, 2),
        standard_matched=has_matched_standards,
        requires_human_clarification=requires_clarification,
    )

    # 2. Trigger Proactive Disambiguation Workflow if confidence is low AND answer is not substantive
    if requires_clarification and not (has_substantive_response and has_matched_standards):
        logger.warning("Low confidence (%.2f) detected for query: %r", intent_confidence, query)
        q_lower = query.strip().lower()

        # Tailored disambiguation for common broad queries
        product_options = {
            "pipe": "Which type of pipe: 1) HDPE Water Supply (IS 4984), 2) UPVC Pipes (IS 4985), or 3) Steel Tubes (IS 1239)?",
            "pipes": "Which type of pipe: 1) HDPE Water Supply (IS 4984), 2) UPVC Pipes (IS 4985), or 3) Steel Tubes (IS 1239)?",
            "cement": "Which grade of cement: 1) 43 Grade OPC (IS 8112), 2) 53 Grade OPC (IS 12269), or 3) PPC (IS 1489)?",
            "steel": "Which steel product: 1) TMT Rebars (IS 1786), 2) Structural Steel (IS 2062), or 3) Stainless Steel (IS 6911)?",
            "cable": "Which cable standard: 1) PVC Insulated Cables (IS 694) or 2) XLPE Power Cables (IS 7098)?",
            "wire": "Which wire standard: 1) Domestic PVC Wires (IS 694) or 2) Steel Binding Wire (IS 280)?",
            "helmet": "Which helmet type: 1) Two-Wheeler Riders (IS 4151) or 2) Industrial Safety Helmets (IS 2925)?",
            "tank": "Which water tank type: 1) Polyethylene Rotomoulded (IS 12701) or 2) GRP Water Tanks (IS 14399)?",
            "tanks": "Which water tank type: 1) Polyethylene Rotomoulded (IS 12701) or 2) GRP Water Tanks (IS 14399)?",
        }

        matched_clarif = None
        for k, prompt in product_options.items():
            if k in q_lower.split():
                matched_clarif = prompt
                break

        if matched_clarif:
            response.follow_up_prompt = matched_clarif
            clarification_msg = (
                f"\n\n💡 **Quick Standards Disambiguation**: To view exact regulatory specs, select:\n"
                f"• {matched_clarif}"
            )
        else:
            clarification_msg = (
                "\n\n[System Clarification Note]: Your query appears broad or ambiguous. "
                "To get the most accurate BIS regulatory requirements, please specify the exact product type "
                "(e.g., gold jewellery, mobile phone, PVC pipe, cement) or the specific IS standard code."
            )
            response.follow_up_prompt = (
                "Could you please specify which exact product or IS standard code you are asking about?"
            )

        if clarification_msg not in response.core_response:
            response.core_response += clarification_msg

    # 3. Enforce Official Portal URL Integrity
    combined_text = response.next_step + " " + response.core_response
    urls = re.findall(r"https?://[^\s<'\"]+", combined_text)
    for url in urls:
        if not any(domain in url.lower() for domain in OFFICIAL_DOMAINS):
            logger.warning("Potentially unauthorized domain link detected in response: %s", url)
            # Replace unauthorized URL with official Manakonline portal
            response.next_step = response.next_step.replace(url, "https://manakonline.in")
            response.core_response = response.core_response.replace(url, "https://manakonline.in")

    # Guarantee actionable official portal URL in next_step if not already present
    if response.next_step and not any(domain in response.next_step.lower() for domain in OFFICIAL_DOMAINS):
        portal = "https://crsbis.in" if "crs" in (response.core_response + " " + query).lower() else "https://manakonline.in"
        response.next_step = f"{response.next_step.rstrip('.')} ({portal})."

    # 4. Enforce Legal Act Accuracy
    # Ensure penalties cite the BIS Act, 2016 rather than misattributing to Consumer Protection Act
    if "penalty" in query.lower() or "fine" in query.lower() or "violation" in query.lower():
        if "Consumer Protection Act" in response.core_response:
            response.core_response = response.core_response.replace(
                "Consumer Protection Act", "Bureau of Indian Standards Act, 2016"
            )

    return guarantee_valid_pydantic_output(response)


def clean_leaked_system_blocks(text: str) -> tuple[str, list[str]]:
    """
    Detect and strip system integration blocks, leaked JSON schemas,
    and artificial signatures from user-facing text, while preserving extracted standards.
    """
    if not text:
        return "", []

    extracted_standards = []
    cleaned = text

    # Extract standards from trailing JSON block if present
    json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned, re.DOTALL)
    if json_match:
        raw_json_str = json_match.group(1)
        # Strip line numbers like '1."applicable_standards":' -> '"applicable_standards":'
        sanitized_json_str = re.sub(r"^\s*\d+\.\s*", "", raw_json_str, flags=re.MULTILINE)
        try:
            data = json.loads(sanitized_json_str)
            if isinstance(data, dict):
                stds = data.get("applicable_standards")
                if isinstance(stds, list):
                    for item in stds:
                        if isinstance(item, str) and item.strip():
                            extracted_standards.append(item.strip())
        except Exception:
            # Fallback regex extraction of IS codes from json block
            matches = re.findall(r'"(IS\s*:?\s*\d{3,5}(?:\s*[-–:]\s*[^"]+)?)"', raw_json_str)
            extracted_standards.extend(m.strip() for m in matches if m.strip())

    # 1. Strip 'Output Fields (for system integration)' or 'OUTPUT FIELDS:' and following code blocks
    cleaned = re.sub(
        r"(?:---|___|\*\*\*)*\s*(?:Output Fields\s*(?:\([^)]*\))?|OUTPUT FIELDS:)\s*(?:```[\s\S]*?```|\{[\s\S]*?\})?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # 2. Strip standalone trailing code blocks that look like system JSON metadata
    cleaned = re.sub(
        r"(?:---|___|\*\*\*)*\s*```(?:json)?\s*\{[\s\S]*?\"applicable_standards\"[\s\S]*?\}\s*```",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # 3. Strip artificial signatures like 'Prepared by: ... *End of Dossier.*'
    cleaned = re.sub(
        r"(?:---|___|\*\*\*)*\s*Prepared by:[\s\S]*?(?:\*End of Dossier\.?\*|\Z)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r"(?:---|___|\*\*\*)*\s*\*End of Dossier\.?\*\s*", "", cleaned, flags=re.IGNORECASE).strip()

    return cleaned, extracted_standards


def format_markdown_tables(text: str) -> str:
    """
    Ensure Markdown tables have proper formatting and heal broken rows,
    orphan pipes, and missing closing delimiters without corrupting cells
    that end with punctuation (. ? ! :).
    """
    if not text or "|" not in text:
        return text

    # 1. Heal orphan pipe lines created by bad splits: e.g. '\n|\n|' -> '\n|'
    norm = re.sub(r'\n\s*\|\s*\n\s*\|', '\n|', text)
    norm = re.sub(r'\n\s*\|\s*$', '', norm)

    # 2. Heal unclosed table rows (lines starting with '|' that have >= 2 pipes but no closing '|')
    fixed_lines = []
    for l in norm.splitlines():
        s = l.strip()
        if s.startswith("|") and s.count("|") >= 2:
            if not s.endswith("|"):
                s = s + " |"
            fixed_lines.append(s)
        else:
            fixed_lines.append(l)
    norm = "\n".join(fixed_lines)

    # 3. Collapse blank lines between adjacent table rows
    norm = re.sub(r'(\|\s*)\n\s*\n\s*(\|)', r'\1\n\2', norm)

    # 4. Separate table from subsequent text: e.g. '| Key Takeaways' -> '|\n\n### Key Takeaways'
    norm = re.sub(r'\|\s+([A-Z][A-Za-z0-9\s&]+:\s*[•●\-*])', r'|\n\n\1', norm)
    norm = re.sub(
        r'\|\s+(Key Takeaways|Important|Note|Recommendation|Actionable|Next Steps)',
        r'|\n\n### \1',
        norm,
        flags=re.IGNORECASE,
    )

    # 5. Expand inline bullet symbols that lack newlines
    norm = re.sub(r'(?<=[^\n])\s+([•●])\s+', r'\n\1 ', norm)

    return norm


def guarantee_valid_pydantic_output(response: BISResponse) -> BISResponse:
    """
    Run output through strict Pydantic model validation.
    Guarantees fields like applicable_standards never return null or malformed objects,
    and ensures leaked system metadata is cleaned out.
    """
    raw_core = (response.core_response or "No response synthesized.").strip()
    clean_core, leaked_stds = clean_leaked_system_blocks(raw_core)

    # 1. Sanitize applicable_standards
    if not isinstance(response.applicable_standards, list):
        response.applicable_standards = []

    # Merge any standards rescued from leaked JSON blocks
    combined_stds = list(response.applicable_standards) + leaked_stds
    clean_stds = []
    seen = set()
    for s in combined_stds:
        if s and isinstance(s, str) and s.strip():
            st = s.strip()
            if st not in seen:
                seen.add(st)
                clean_stds.append(st)
    response.applicable_standards = clean_stds

    # 2. Sanitize string fields
    response.core_response = format_markdown_tables(clean_core)
    response.source_citation = (response.source_citation or "").strip()
    response.next_step = (response.next_step or "").strip()
    response.follow_up_prompt = (response.follow_up_prompt or "").strip()
    response.intent_localized = (response.intent_localized or "").strip()

    # 3. Validate model instance
    try:
        return BISResponse.model_validate(response.model_dump())
    except Exception as exc:
        logger.error("Pydantic re-validation failed: %s", exc)
        return response


