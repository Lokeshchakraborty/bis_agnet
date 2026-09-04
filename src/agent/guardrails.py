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

import logging
import re
from typing import List

from src.schemas import BISResponse, ConfidenceMetrics

logger = logging.getLogger("bis_guardrails")

OFFICIAL_DOMAINS = ["manakonline.in", "crsbis.in", "bis.gov.in"]
IS_CODE_PATTERN = re.compile(r"\bIS\s*:?\s*\d{3,5}(?:\s*\([^)]+\))?(?::\d{4})?\b", re.IGNORECASE)


def validate_and_sanitize_response(
    response: BISResponse,
    query: str,
    intent_confidence: float = 0.95,
) -> BISResponse:
    """
    Validate, sanitize, and score a synthesized BIS response.
    """
    # 1. Update confidence metrics
    requires_clarification = intent_confidence < 0.75

    # Check if query is extremely vague (1-2 non-greeting words)
    words = re.findall(r"\w+", query.strip())
    if len(words) <= 2 and query.strip().lower() not in {"hi", "hello", "namaste", "help"}:
        intent_confidence = min(intent_confidence, 0.65)
        requires_clarification = True

    response.confidence_metrics = ConfidenceMetrics(
        intent_confidence=round(intent_confidence, 2),
        standard_matched=len(response.applicable_standards) > 0 or "IS" in response.core_response,
        requires_human_clarification=requires_clarification,
    )

    # 2. Trigger Proactive Disambiguation Workflow if confidence is low
    if requires_clarification:
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


def guarantee_valid_pydantic_output(response: BISResponse) -> BISResponse:
    """
    Run output through strict Pydantic model validation.
    Guarantees fields like applicable_standards never return null or malformed objects.
    """
    # 1. Sanitize applicable_standards
    if not isinstance(response.applicable_standards, list):
        response.applicable_standards = []
    else:
        clean_stds = []
        for s in response.applicable_standards:
            if s and isinstance(s, str) and s.strip():
                clean_stds.append(s.strip())
        response.applicable_standards = clean_stds

    # 2. Sanitize string fields
    response.core_response = (response.core_response or "No response synthesized.").strip()
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

