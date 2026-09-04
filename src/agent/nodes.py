"""
Graph Node Implementations, Prompt Templates, and Routing Helpers for BIS Agent.
"""
from __future__ import annotations

import concurrent.futures
import functools
import logging
import re
import time
from typing import Callable, Optional, TypeVar

from langchain_core.prompts import ChatPromptTemplate

from src.config import CONFIG
from src.schemas import (
    DOMAIN_COLLECTIONS,
    AgentState,
    BISResponse,
    Intent,
    IntentResult,
    TokenTracker,
)
from src.agent.guardrails import validate_and_sanitize_response
from src.tools.cache import ResponseCache
from src.tools.retriever import hybrid_retrieve
from src.tools.scraper import scrape_bis_portal

logger = logging.getLogger("bis_nodes")

# --------------------------------------------------------------------------- #
# Retry Decorator
# --------------------------------------------------------------------------- #
T = TypeVar("T")


def with_retry(max_retries: int = CONFIG.max_retries, backoff: float = CONFIG.retry_backoff_seconds):
    """Decorator for exponential backoff on rate limits and transient errors."""
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt == max_retries:
                        break
                    err_str = str(exc)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        m = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str, re.IGNORECASE) or re.search(
                            r"retryDelay['\":\s]+(\d+)s", err_str, re.IGNORECASE
                        )
                        wait = float(m.group(1)) + 1.5 if m else max(15.0 * attempt, backoff * (2 ** (attempt - 1)))
                    else:
                        wait = backoff * (2 ** (attempt - 1))
                    logger.warning(
                        "%s failed (attempt %d/%d): %s - retrying in %.1fs",
                        fn.__name__, attempt, max_retries, exc, wait,
                    )
                    time.sleep(wait)
            assert last_exc is not None
            raise last_exc
        return wrapper
    return decorator


# --------------------------------------------------------------------------- #
# Fast Heuristics for Zero-Token Optimization
# --------------------------------------------------------------------------- #
FOLLOWUP_TRIGGERS = {
    "yes", "sure", "ok", "okay", "explain", "more", "tell", "haan", "ha", "theek",
    "batao", "bataiye", "aur", "and", "also", "fees", "fee", "cost", "charge",
    "charges", "document", "documents", "paper", "papers", "this", "that", "it",
    "these", "those", "iska", "iske", "iski", "isme", "unka", "inhe", "kya", "kaise",
    "kitna", "kitni", "next", "aage", "fir", "phir", "help", "madad", "sahayata"
}

COMMON_GREETINGS = {
    "hi", "hello", "hey", "namaste", "namaskar", "namastey", "नमस्ते", "नमस्कार",
    "kaise ho", "kya haal hai", "good morning", "good evening", "good afternoon",
    "thanks", "thank you", "dhanyawaad", "shukriya", "धन्यवाद", "शुक्रिया",
    "who are you", "aap kaun ho", "आप कौन हैं", "help", "madad"
}


def _needs_rewrite(query: str) -> bool:
    """Check if query is dependent on prior conversational context."""
    q = query.strip().lower()
    words = re.findall(r"[\w\u0900-\u097F]+", q)
    if not words:
        return False
    if len(words) <= 3:
        return True
    first_word = words[0]
    if first_word in {"and", "aur", "also", "or", "what", "how", "kya", "kaise", "kitna", "kitni"}:
        return True
    return any(w in FOLLOWUP_TRIGGERS for w in words[:3])


FAST_INTENT_PATTERNS = [
    (Intent.HALLMARK, re.compile(r"\b(hallmark|hallmarking|huid|ahc|assaying|gold|silver|sona|chandi|carat|karat|हॉलमार्क|हॉलमार्किंग|सोना|चांदी)\b", re.I)),
    (Intent.REGISTRATION, re.compile(r"\b(crs|compulsory registration|meity|electronics registration)\b", re.I)),
    (Intent.CERTIFICATION, re.compile(r"\b(isi mark|fmcs|qco|quality control order|cml number|foreign manufacturer)\b", re.I)),
    (Intent.LABORATORY, re.compile(r"\b(laboratory|testing lab|lrs|lims|prayogshala|प्रयोगशाला|परीक्षण)\b", re.I)),
    (Intent.MANAKONLINE, re.compile(r"\b(manakonline|manak online|e-bis|e-cml)\b", re.I)),
    (Intent.CATALOG_SEARCH, re.compile(r"\b(pipe|pipes|cement|steel|tank|tanks|cable|cables|battery|batteries|helmet|helmets|toy|toys|wire|wires|plywood|fertilizer|glass|cooker)\b", re.I)),
]


def _fast_classify(query: str) -> Optional[Intent]:
    """Zero-token instant classification for IS codes, short greetings, and clear domain keywords."""
    q_norm = query.strip().lower()
    # 1. Exact IS code pattern
    if re.search(r"\bIS\s*:?\s*\d{3,5}\b", query, re.IGNORECASE) or re.match(r"^\s*IS\s*\d+", query, re.IGNORECASE):
        return Intent.CATALOG_SEARCH

    # 2. Short greetings (1-3 words)
    words = re.findall(r"[\w\u0900-\u097F]+", q_norm)
    if 1 <= len(words) <= 3:
        phrase = " ".join(words)
        if phrase in COMMON_GREETINGS or words[0] in COMMON_GREETINGS:
            return Intent.CHAT

    # 3. High-confidence domain keywords
    for intent, pattern in FAST_INTENT_PATTERNS:
        if pattern.search(q_norm):
            return intent

    return None


def _format_history(chat_history: list[tuple[str, str]]) -> str:
    if not chat_history:
        return "(no prior turns)"
    recent = list(chat_history)[-CONFIG.history_window:]
    return "\n".join(f"User: {u}\nAgent: {a}" for u, a in recent)


# --------------------------------------------------------------------------- #
# Node Functions Container
# --------------------------------------------------------------------------- #
class AgentNodes:
    """Encapsulates graph node methods and initialized LLM/retriever dependencies."""

    def __init__(
        self,
        llm,
        embeddings,
        catalog_retriever,
        domain_chromadbs: dict,
        response_cache: ResponseCache,
        token_tracker: TokenTracker,
    ) -> None:
        self.llm = llm
        self.embeddings = embeddings
        self.catalog_retriever = catalog_retriever
        self.domain_chromadbs = domain_chromadbs
        self.response_cache = response_cache
        self.token_tracker = token_tracker

        self.structured_response_llm = llm.with_structured_output(BISResponse, include_raw=True)
        self.structured_intent_llm = llm.with_structured_output(IntentResult, include_raw=True)

    @with_retry()
    def _rewrite_query(self, last_agent_msg: str, query: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You convert a user's short reply into a full standalone search query.\n\n"
             "The agent's last message may contain a section tagged '[I asked as follow-up]: ...' "
             "which is the exact follow-up question the agent posed to the user.\n\n"
             "Rules:\n"
             "1. If the user replies with 'yes', 'sure', 'ok', 'explain', 'tell me more', 'haan', 'ha', "
             "'batao', 'bataiye', 'theek hai', or any short affirmation — look at the '[I asked as follow-up]' "
             "section and turn THAT question into the standalone query.\n"
             "2. Preserve the user's language style (English, Hindi, or Hinglish).\n"
             "3. If the user replies with a specific answer or correction to the follow-up, "
             "incorporate that answer into the standalone query.\n"
             "4. If there is no follow-up section, use the full agent answer as context to "
             "understand what the user is referring to.\n"
             "5. Output ONLY the standalone query — no preamble, no explanation."),
            ("human", "Agent's Last Message:\n{last_agent_msg}\n\nUser's Reply: {query}"),
        ])
        msg = prompt.format_messages(last_agent_msg=last_agent_msg, query=query)
        resp = self.llm.invoke(msg)
        self.token_tracker.add_llm_usage(getattr(resp, "usage_metadata", None))

        content = resp.content
        if isinstance(content, list):
            text_parts = [
                part["text"] if isinstance(part, dict) and "text" in part else str(part)
                for part in content
            ]
            return " ".join(text_parts).strip()
        return str(content).strip()

    def contextualize_query(self, state: AgentState) -> dict:
        """Rewrite query using chat history only when dependent, saving tokens."""
        if not state["chat_history"]:
            sq = state["query"]
        elif not _needs_rewrite(state["query"]):
            logger.info("Self-contained query detected — skipping rewrite")
            sq = state["query"]
        else:
            try:
                sq = self._rewrite_query(state["chat_history"][-1][1], state["query"])
            except Exception as exc:
                logger.error("Query rewrite failed, using raw query: %s", exc)
                sq = state["query"]

        return {"standalone_query": sq or state["query"]}

    @with_retry()
    def _classify(self, query: str) -> Intent:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a highly accurate intent classification router for the Bureau of Indian Standards (BIS) AI Assistant.
The user query may be in English, Hinglish (Romanized Hindi/English mix), or pure Hindi (Devanagari).
Classify the user's standalone query into EXACTLY ONE of the following 7 categories:

1. chat - Greetings, pleasantries, identity/capability questions, asking for help generally without specifying a domain (e.g. hi, hello, namaste, kaise ho, aap kaun ho, kya kar sakte ho, नमस्ते, आप कौन हैं, help, thanks).
2. hallmark - Hallmark, HUID, gold, silver, jewellery, sona, chandi, aabhooshan, carat, purity, AHC, assaying center.
3. registration - CRS, Compulsory Registration Scheme, electronics, IT goods, laptops, mobiles, solar panels, MeitY.
4. certification - ISI mark, FMCS, Scheme-I, QCO, Quality Control Order, factory audit, CML number, AIR, license.
5. laboratory - Laboratory, testing lab, LRS, test report, NABL, LIMS, recognized lab, calibration, prayogshala.
6. manakonline - Manak online, e-BIS, e-CML, portal, login, password, upload document, online application, portal registration.
7. catalog_search - IS code, IS number, standard, product name (cement, pipes, steel, petroleum, water, toys, khilona, paani, etc.).

CRITICAL: Any product name mention defaults to catalog_search."""),
            ("human", "{query}"),
        ])
        msg = prompt.format_messages(query=query)
        raw_res = self.structured_intent_llm.invoke(msg)
        if isinstance(raw_res, dict) and "raw" in raw_res:
            self.token_tracker.add_llm_usage(getattr(raw_res["raw"], "usage_metadata", None))
            parsed = raw_res.get("parsed")
            if parsed and hasattr(parsed, "intent"):
                return parsed.intent
        elif hasattr(raw_res, "intent"):
            return raw_res.intent
        return Intent.CATALOG_SEARCH

    def intent_classifier(self, state: AgentState) -> dict:
        """Classify the query into one of 7 intents."""
        fast_intent = _fast_classify(state["standalone_query"])
        if fast_intent:
            logger.info("Fast 0-token classification: '%s' -> %s", state["standalone_query"], fast_intent.value)
            return {"intent": fast_intent.value}
        try:
            intent = self._classify(state["standalone_query"])
        except Exception as exc:
            logger.error("Intent classification fallback triggered: %s", exc)
            intent = Intent.CHAT if len(state["standalone_query"].split()) <= 2 else Intent.CATALOG_SEARCH

        return {"intent": intent.value}

    def retrieve_domain(self, domain: Intent):
        """Factory: returns a retrieval node for domain PDFs using hybrid BM25 + dense retrieval."""
        def _node(state: AgentState) -> dict:
            vector_db = self.domain_chromadbs.get(domain.value)
            self.token_tracker.add_embedding_text(state["standalone_query"])
            if vector_db is None:
                return {"retrieved_context": "No database collection found.", "domain": domain.value}

            try:
                _, context = hybrid_retrieve(
                    query=state["standalone_query"],
                    vector_store=vector_db,
                    embeddings=self.embeddings,
                    domain=domain.value,
                    dense_k=CONFIG.retriever_k,
                    bm25_k=CONFIG.retriever_k,
                    rerank_top_n=CONFIG.rerank_top_n,
                )
            except Exception as exc:
                logger.warning("Hybrid retrieval failed for '%s', using fallback: %s", domain.value, exc)
                try:
                    docs = vector_db.as_retriever(search_kwargs={"k": CONFIG.retriever_k}).invoke(
                        state["standalone_query"]
                    )
                    context = "\n".join(d.page_content for d in docs) if docs else "No relevant documents found."
                except Exception:
                    context = "No relevant documents found."

            self.token_tracker.add_embedding_text(context)
            return {"retrieved_context": context, "domain": domain.value}

        return _node

    def retrieve_catalog(self, state: AgentState) -> dict:
        """Concurrent live BIS portal scraping + local Chroma DB retrieval."""
        sq = state["standalone_query"]
        self.token_tracker.add_embedding_text(sq)

        def _get_db_docs():
            try:
                docs = self.catalog_retriever.invoke(sq)
                return "\n".join(d.page_content for d in docs) if docs else "No local catalog entries found."
            except Exception as exc:
                logger.warning("Local catalog retrieval error: %s", exc)
                return "No local catalog entries found."

        def _get_scraped_data():
            try:
                scraped = scrape_bis_portal(sq)
                return scraped if scraped.strip() else "(scraper returned no content for this query)"
            except Exception as exc:
                logger.warning("BIS portal scrape error (%s). Using local DB only.", exc)
                return "Live portal data unavailable."

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_db = executor.submit(_get_db_docs)
            future_scrape = executor.submit(_get_scraped_data)
            db_context = future_db.result()
            scraped = future_scrape.result()

        combined = f"[LIVE PORTAL DATA]:\n{scraped}\n\n[LOCAL KNOWLEDGE BASE]:\n{db_context}"
        self.token_tracker.add_embedding_text(combined)
        return {"retrieved_context": combined, "domain": "catalog"}

    @with_retry()
    def _synthesize(self, chat_history: str, context: str, query: str, is_chat: bool) -> BISResponse:
        if is_chat:
            system_prompt = (
                "You are a helpful BIS (Bureau of Indian Standards) AI Assistant.\n"
                "Keep the reply conversational and brief.\n"
                "Leave applicable_standards, source_citation, and next_step empty for greetings.\n"
                "Set intent_localized to match the user's greeting language ('सामान्य बातचीत' for Hindi, 'General Chat' for Hinglish/English).\n\n"
                "LANGUAGE MATCHING RULES:\n"
                "- If the user greets or chats in Hindi (Devanagari, e.g. 'नमस्ते', 'आप कौन हैं?'), reply in polite Hindi.\n"
                "- If the user greets or chats in Hinglish (Roman script, e.g. 'Namaste', 'Aap kaun ho?', 'Kya haal hai?'), reply in natural Hinglish.\n"
                "- If the user greets in English ('Hello', 'Hi'), reply in English.\n\n"
                "Chat history:\n{chat_history}"
            )
        else:
            system_prompt = (
                "You are an expert BIS (Bureau of Indian Standards) AI Assistant.\n"
                "Answer based on the provided context first.\n"
                "If the context contains specific document excerpts, cite them in source_citation.\n\n"
                "1. REGULATORY AMENDMENTS & DIGITAL MANUAL INTEGRATION (CRITICAL):\n"
                "   - Account for recent BIS standard amendments in your core_response and compliance_metadata:\n"
                "     * For mobile phones, IT equipment, and electronics (e.g. IS 16333 Part 3:2022 Amendment No. 1), digital/QR-code-based user manuals and instruction booklets ARE PERMITTED on product packaging provided clear access instructions are printed on the outer packaging.\n"
                "     * Specify applicable amendments (e.g., 'Amendment No. 1 to IS 16333 (Part 3):2022') in compliance_metadata.amendments_applicable.\n"
                "     * Set compliance_metadata.digital_qr_manual_allowed to true when applicable.\n"
                "     * Set compliance_metadata.foreign_manufacturer_requires_air to true if foreign manufacturers require an Authorized Indian Representative (AIR) under FMCS or CRS.\n"
                "     * Set compliance_metadata.testing_location (e.g., 'BIS-accredited domestic laboratory').\n"
                "     * Set compliance_metadata.certificate_validity_years (default 2 years unless specified otherwise).\n\n"
                "2. STRICT SCRIPT AND LANGUAGE MATCHING & ACTIONABLE MANAKONLINE ROUTING:\n"
                "   - Match the user's exact script and language across ALL synthesized fields:\n"
                "     * HINDI (Devanagari script, e.g. 'हॉलमार्किंग के लिए कैसे आवेदन करें?'):\n"
                "       Write core_response, next_step, follow_up_prompt, AND intent_localized in pure, natural Hindi (Devanagari script).\n"
                "       MUST include official Manakonline portal URL in next_step.\n"
                "       Example next_step: 'आधिकारिक Manakonline पोर्टल (https://manakonline.in) पर जाएं और ऑनलाइन आवेदन (फॉर्म H-1) जमा करें।'\n"
                "       Example follow_up_prompt: 'क्या आप एएचसी (AHC) केंद्रों की सूची या शुल्क संरचना के बारे में अधिक जानकारी चाहते हैं?'\n"
                "       Example intent_localized: 'हॉलमार्क पंजीकरण'\n"
                "     * HINGLISH (Romanized Hindi, e.g. 'Hallmarking ke liye apply kaise karein?'):\n"
                "       Write core_response, next_step, follow_up_prompt, AND intent_localized in natural Hinglish using Roman script.\n"
                "       Example next_step: 'Official Manakonline portal (https://manakonline.in) par jaakar online application (Form H-1) submit karein.'\n"
                "       Example follow_up_prompt: 'Kya aap HUID fees ya test lab list ke baare mein aur jaan-kaari chahte hain?'\n"
                "     * ENGLISH:\n"
                "       Write core_response, next_step, follow_up_prompt, AND intent_localized in clear, professional English.\n"
                "       Example next_step: 'Navigate to the official Manakonline portal (https://manakonline.in) to register and submit the online application form.'\n"
                "       Example follow_up_prompt: 'Would you like information regarding HUID fee structures or testing lab locations?'\n\n"
                "3. TECHNICAL PRECISION & UNTOUCHED REGULATORY CODES:\n"
                "   - Keep all official IS codes, standard numbers, form numbers, and portal URLs exact and uncorrupted:\n"
                "     * Standards (e.g. 'IS 1417', 'IS 16333 (Part 3):2022', 'IS 2112', 'IS/ISO 9001')\n"
                "     * Legal Acts: Always cite the exact statutory act as 'Bureau of Indian Standards Act, 2016 (BIS Act, 2016)'\n"
                "     * Gold Hallmarking Purity: When discussing purity grades under IS 1417, explicitly mention both karat notation and fineness (e.g. 24K / 999, 23K / 958, 22K / 916, 20K / 833, 18K / 750, 14K / 585)\n"
                "     * Portal names & URLs (e.g. 'Manakonline portal', 'https://manakonline.in', 'e-BIS')\n"
                "     * Technical abbreviations (e.g. 'HUID', 'AHC', 'CRS', 'FMCS', 'CML', 'QCO', 'AIR')\n"
                "   - applicable_standards: List every relevant IS standard code formatted as 'IS XXXX - Description'.\n"
                "   - source_citation: If context has '[Source N: filename]', cite the exact file name(s).\n\n"
                "4. STANDARDIZED COMPLIANCE RESPONSE FORMATTING:\n"
                "   - DO NOT include the heading or text 'Compliance Overview' at the top of core_response.\n"
                "   - GENERAL / CONCEPTUAL QUERIES (when NO specific product or IS standard code is mentioned, e.g. 'what is certification?', 'what is hallmarking?', 'what is CRS registration?'):\n"
                "     * Provide a clear, comprehensive, and well-structured paragraph (or 2-3 paragraphs) answering the question directly in plain language.\n"
                "     * DO NOT generate the 7-bullet compliance breakdown (Applicable Indian Standards, Certification requirements, etc.) for general concept queries where no specific product or IS code is specified.\n"
                "     * Use follow_up_prompt to ask the user if they would like technical compliance details for a specific product category or IS standard code.\n"
                "   - PRODUCT-SPECIFIC & IS CODE QUERIES (when a specific product, e.g. 'watering cans', 'mustard oil', 'cement', or specific IS code, e.g. 'IS 4065', 'IS 12701', is mentioned):\n"
                "     * ALWAYS start directly with a clear, informative 2-3 sentence overview paragraph answering the user's question.\n"
                "     * AFTER the explanation paragraph, present the compliance breakdown using MAIN BULLET POINTS ('• ') for each category, and ALWAYS INCLUDE INDENTED NUMBERED SUB-ITEMS ('  1. ', '  2. ') under each main category to provide detailed technical points and specifics.\n"
                "     * Required Main Categories & Numbered Sub-Items Structure:\n"
                "       • **Applicable Indian Standards for products**:\n"
                "         1. **Primary Standard**: Exact IS code and title (e.g. **IS 1417:2019**)\n"
                "         2. **Scope & Purity**: Specific grades, classes, or product scope\n"
                "       • **Certification requirements**:\n"
                "         1. **Marking Requirements**: Mandatory ISI Mark / CRS Mark / HUID 6-digit alphanumeric code\n"
                "         2. **AIR Obligation**: Authorized Indian Representative rules for foreign manufacturers\n"
                "       • **Relevant BIS schemes**:\n"
                "         1. **Scheme Name**: Scheme-I (Product Certification), Scheme-IV, CRS, FMCS, Hallmarking Scheme, LRS\n"
                "       • **Licensing procedures**:\n"
                "         1. **Portal Application**: Manakonline portal filing (Form H-1 / Form CML)\n"
                "         2. **Inspection & Audit**: Factory audit and preliminary sample testing rules\n"
                "       • **Testing requirements**:\n"
                "         1. **Accredited Testing**: Mandatory NABL/BIS-accredited lab test reports\n"
                "         2. **Test Parameters**: Specific physical, chemical, mechanical, or safety test parameters\n"
                "       • **Related standards & Dedicated Amendments**:\n"
                "         1. **Related IS Codes**: Complementary standards\n"
                "         2. **Dedicated Amendment Status**: Explicitly state 'Dedicated Amendment Available: Amendment No. X' OR 'No Dedicated Amendment Released'\n"
                "       • **Answers to technical queries**:\n"
                "         1. **Quantitative Limits**: State exact numeric thresholds, capacities, tolerances, and test limits\n\n"




                "5. INDIAN STANDARDS (IS CODE) IDENTIFICATION:\n"
                "   - When queried about a specific IS code (e.g. 'IS 567', 'IS 12269', 'IS 4984', 'IS 12701'), use your authoritative BIS knowledge to identify the official standard title, product subject, and scope if scrape results are partial. Clearly guide the user on how to access the official standard on Manakonline.\n\n"
                "6. MANDATORY QUANTITATIVE & PARAMETER EXTRACTION (CRITICAL):\n"
                "   - If the user asks for specific technical parameters, maximum/minimum limits, capacities, dimensions, tolerances, or chemical/physical test thresholds (e.g., maximum capacity limit of 10,000 Litres and overall chemical migration limit of 60 mg/l max for IS 12701 polyethylene water storage tanks), YOU MUST EXTRACT AND STATE THE EXACT NUMBERS, VALUES, AND UNITS IN YOUR core_response.\n"
                "   - FORMATTING WITH MARKDOWN TABLES: Whenever comparing multiple grades, karats, sizes, or technical thresholds, format them as clean Markdown tables (| Grade / Parameter | Purity / Limit | Standard |).\n"
                "   - DO NOT play it too safe or dodge by telling the user to 'refer to the portal' or stating that 'tests exist' without giving the numbers. Always state the exact quantitative numbers, limits, and technical values first in core_response, and provide the portal URL in next_step as an actionable follow-up.\n\n"
                "7. PDF & COMPREHENSIVE RESEARCH DOSSIER GENERATION:\n"
                "   - When the user explicitly asks for a 'pdf', 'dossier', 'full compliance', or 'full research' (e.g. 'give me a pdf', 'download as pdf', 'give full compliance', 'full research'):\n"
                "     * Deliver the complete, comprehensive research breakdown covering all relevant IS standards, technical parameters, and licensing procedures in core_response.\n"
                "     * In next_step, clearly state: 'Your official BIS Compliance Research Dossier (PDF) has been compiled. Click the \"📄 Download Research PDF\" button below to save the official document.'\n"
                "     * Ensure all applicable IS standards and quantitative limits are listed completely.\n"
                "   - For normal queries where the user did NOT ask for a PDF, full compliance, or full research, DO NOT mention or offer PDF download in next_step.\n\n"
                "Chat history:\n{chat_history}\n\nContext:\n{context}"
            )

        prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{query}")])
        msg = prompt.format_messages(chat_history=chat_history, context=context, query=query)
        raw_res = self.structured_response_llm.invoke(msg)
        if isinstance(raw_res, dict) and "raw" in raw_res:
            self.token_tracker.add_llm_usage(getattr(raw_res["raw"], "usage_metadata", None))
            parsed = raw_res.get("parsed")
            if isinstance(parsed, BISResponse):
                return parsed
        elif isinstance(raw_res, BISResponse):
            return raw_res
        return BISResponse(core_response=str(raw_res))

    def synthesize_response(self, state: AgentState) -> dict:
        """Produce unified JSON response with multi-key caching."""
        is_chat = state["intent"] == Intent.CHAT.value

        # 1. Cache lookup
        if CONFIG.cache_enabled and not is_chat:
            key_raw = self.response_cache.make_key(state["intent"], state.get("query", ""))
            key_standalone = self.response_cache.make_key(state["intent"], state["standalone_query"])
            cached = self.response_cache.get(key_raw) or self.response_cache.get(key_standalone)
            if cached:
                self.token_tracker.record_cache_hit(estimated_saved=750)
                result = BISResponse(**{k: cached[k] for k in BISResponse.model_fields if k in cached})
                return {
                    "final_output": result,
                    "cache_hit": True,
                    "token_usage": self.token_tracker.get_turn_summary(cache_hit=True),
                }

        # 2. LLM Synthesis
        try:
            result = self._synthesize(
                _format_history(state["chat_history"]),
                state.get("retrieved_context", ""),
                state["standalone_query"],
                is_chat,
            )
        except Exception as exc:
            logger.error("Synthesis error: %s", exc)
            result = BISResponse(
                core_response="I encountered an issue reaching the language model. Please try again.",
                follow_up_prompt="Would you like to try rephrasing your question?",
            )

        # 2b. Apply Guardrails & Validation
        try:
            raw_conf = 0.95 if is_chat or len(state.get("retrieved_context", "")) > 50 else 0.65
            result = validate_and_sanitize_response(result, state["query"], intent_confidence=raw_conf)
        except Exception as exc:
            logger.warning("Guardrail validation error: %s", exc)

        # 3. Store in cache
        if CONFIG.cache_enabled and not is_chat and result:
            try:
                payload = {"intent": state["intent"], "domain": state.get("domain", ""), **result.model_dump()}
                key_standalone = self.response_cache.make_key(state["intent"], state["standalone_query"])
                self.response_cache.set(key_standalone, payload)
                raw_q = state.get("query", "").strip()
                if raw_q and len(raw_q.split()) >= 3:
                    key_raw = self.response_cache.make_key(state["intent"], raw_q)
                    self.response_cache.set(key_raw, payload)
            except Exception:
                pass

        return {
            "final_output": result,
            "cache_hit": False,
            "token_usage": self.token_tracker.get_turn_summary(cache_hit=False),
        }
