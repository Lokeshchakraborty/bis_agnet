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

        try:
            self.structured_response_llm = llm.with_structured_output(BISResponse, include_raw=True)
            self.structured_intent_llm = llm.with_structured_output(IntentResult, include_raw=True)
        except Exception as exc:
            logger.info("Default LLM structured output setup notice: %s", exc)
            self.structured_response_llm = None
            self.structured_intent_llm = None

    def _get_llm_for_state(self, state: Optional[AgentState] = None):
        if not state:
            return self.llm
        provider = state.get("llm_provider")
        model = state.get("llm_model")
        api_key = state.get("llm_api_key")
        base_url = state.get("llm_base_url")
        if provider:
            from src.agent.llm_factory import create_llm_model
            try:
                return create_llm_model(
                    provider=provider,
                    model_name=model,
                    api_key=api_key,
                    base_url=base_url,
                )
            except Exception as exc:
                logger.warning("Failed to create dynamic LLM for provider '%s': %s. Falling back to default.", provider, exc)
        return self.llm

    @with_retry()
    def _rewrite_query(self, last_agent_msg: str, query: str, state: Optional[AgentState] = None) -> str:
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
        llm = self._get_llm_for_state(state)
        resp = llm.invoke(msg)
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
                sq = self._rewrite_query(state["chat_history"][-1][1], state["query"], state=state)
            except Exception as exc:
                logger.error("Query rewrite failed, using raw query: %s", exc)
                sq = state["query"]

        return {"standalone_query": sq or state["query"]}

    @with_retry()
    def _classify(self, query: str, state: Optional[AgentState] = None) -> Intent:
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
        llm = self._get_llm_for_state(state)

        # 1. Try structured intent classification
        try:
            structured_intent_llm = llm.with_structured_output(IntentResult, include_raw=True)
            raw_res = structured_intent_llm.invoke(msg)
            if isinstance(raw_res, dict) and "raw" in raw_res:
                self.token_tracker.add_llm_usage(getattr(raw_res["raw"], "usage_metadata", None))
                parsed = raw_res.get("parsed")
                if parsed and hasattr(parsed, "intent"):
                    return parsed.intent
            elif hasattr(raw_res, "intent"):
                return raw_res.intent
        except Exception as exc:
            logger.info("Structured intent output unavailable or failed (%s). Falling back to direct text matching.", exc)

        # 2. Fallback for Ollama or models without tool/function calling
        resp = llm.invoke(msg)
        self.token_tracker.add_llm_usage(getattr(resp, "usage_metadata", None))
        text = str(resp.content).lower()
        for cat in [Intent.HALLMARK, Intent.REGISTRATION, Intent.CERTIFICATION, Intent.LABORATORY, Intent.MANAKONLINE, Intent.CHAT, Intent.CATALOG_SEARCH]:
            if cat.value in text:
                return cat
        return Intent.CATALOG_SEARCH

    def intent_classifier(self, state: AgentState) -> dict:
        """Classify the query into one of 7 intents."""
        fast_intent = _fast_classify(state["standalone_query"])
        if fast_intent:
            logger.info("Fast 0-token classification: '%s' -> %s", state["standalone_query"], fast_intent.value)
            return {"intent": fast_intent.value}
        try:
            intent = self._classify(state["standalone_query"], state=state)
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

            max_chars = getattr(CONFIG, "context_max_chars", 1400) * CONFIG.rerank_top_n
            if len(context) > max_chars:
                context = context[:max_chars] + "\n...(context bounded)"

            self.token_tracker.add_embedding_text(context)
            return {"retrieved_context": context, "domain": domain.value}

        return _node

    def retrieve_catalog(self, state: AgentState) -> dict:
        """Concurrent live BIS portal scraping + local Chroma DB retrieval."""
        sq = state["standalone_query"]
        self.token_tracker.add_embedding_text(sq)

        max_c = getattr(CONFIG, "context_max_chars", 1400)

        def _get_db_docs():
            try:
                docs = self.catalog_retriever.invoke(sq)
                return "\n".join(d.page_content[:max_c] for d in docs) if docs else "No local catalog entries found."
            except Exception as exc:
                logger.warning("Local catalog retrieval error: %s", exc)
                return "No local catalog entries found."

        def _get_scraped_data():
            try:
                scraped = scrape_bis_portal(sq)
                if len(scraped) > max_c * 2:
                    scraped = scraped[:max_c * 2] + "\n...(portal data bounded)"
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

    def _build_system_prompt(self, is_chat: bool) -> str:
        if is_chat:
            return (
                "You are a helpful BIS (Bureau of Indian Standards) AI Assistant.\n"
                "Keep the reply conversational and brief.\n"
                "Leave applicable_standards, source_citation, and next_step empty for greetings.\n"
                "Set intent_localized to match the user's greeting language ('सामान्य बातचीत' for Hindi, 'General Chat' for Hinglish/English).\n\n"
                "LANGUAGE MATCHING RULES:\n"
                "- If the user greets in Hindi (Devanagari, e.g. 'नमस्ते'), reply in polite Hindi.\n"
                "- If the user greets in Hinglish (Roman script, e.g. 'Namaste'), reply in natural Hinglish.\n"
                "- If the user greets in English, reply in English.\n\n"
                "Chat history:\n{chat_history}"
            )
        return (
            "You are an expert BIS (Bureau of Indian Standards) AI Assistant.\n"
            "Answer authoritatively based on official BIS regulations, Indian Standards (IS), and provided context.\n\n"
            "KEY DIRECTIVES:\n"
            "1. REGULATORY FIDELITY & STANDARDS:\n"
            "   - Always identify exact Indian Standards (e.g. 'IS 1417', 'IS 12701', 'IS 13252 (Part 1):2010', 'IS 269').\n"
            "   - Always cite statutory laws as 'Bureau of Indian Standards Act, 2016 (BIS Act, 2016)'.\n"
            "   - In 'applicable_standards', list all relevant standards formatted as 'IS XXXX - Title'.\n\n"
            "2. MANDATORY QUANTITATIVE & PARAMETER EXTRACTION:\n"
            "   - Extract exact numbers, capacities, tolerances, test limits, migration thresholds (e.g. 60 mg/l for IS 12701), and karat fineness (e.g. 24K/999, 22K/916, 18K/750).\n"
            "   - Use clean Markdown tables when presenting or comparing technical parameters, grades, or test limits.\n\n"
            "3. STRICT LANGUAGE & SCRIPT MATCHING:\n"
            "   - HINDI (Devanagari): Answer in natural Hindi; set intent_localized in Hindi (e.g. 'हॉलमार्क पंजीकरण').\n"
            "   - HINGLISH: Answer in natural conversational Hinglish using Roman script.\n"
            "   - ENGLISH: Professional, clear technical English.\n\n"
            "4. MANDATORY DUAL STRUCTURE (PARAGRAPH + STRUCTURED BULLETS & SUB-BULLETS):\n"
            "   - EVERY compliance, regulatory, IS standard, laboratory, testing, or certification query MUST follow this exact two-tier format:\n"
            "     1. Comprehensive Overview Paragraph: 2-3 direct sentences answering the query immediately with statutory basis under the Bureau of Indian Standards Act, 2016 (BIS Act, 2016). Never use filler headers like 'Compliance Overview'.\n"
            "     2. Detailed Compliance Breakdown: Present using MAIN BULLET POINTS ('• ') with INDENTED NUMBERED SUB-ITEMS ('  1. ', '  2. ') under each main category:\n"
            "        • **Applicable Indian Standards & Scope**:\n"
            "          1. **Primary Standard**: Exact IS code and title (e.g. **IS 1417:2019**, **IS 567:2024**, **IS 876:1992**)\n"
            "          2. **Scope & Grades**: Specific grades, classes, types, or product coverage\n"
            "        • **Certification Requirements & Scheme**:\n"
            "          1. **Marking Requirements**: Mandatory ISI Mark / CRS Mark / HUID 6-digit alphanumeric code\n"
            "          2. **Relevant Scheme**: Scheme-I (Product Certification), Scheme-IV, CRS, FMCS, Hallmarking, or Laboratory Recognition Scheme (LRS)\n"
            "          3. **AIR Obligation**: Authorized Indian Representative rules for foreign manufacturers (if applicable)\n"
            "        • **Testing Procedures & Laboratory Network**:\n"
            "          1. **Accredited Testing**: Mandatory NABL/BIS-recognized laboratory test reports\n"
            "          2. **Test Parameters**: Specific physical, chemical, mechanical, or safety test parameters\n"
            "          3. **Portal Workflow**: Application filing on Manakonline (https://manakonline.in) or CRS (https://crsbis.in)\n"
            "        • **Technical Parameters & Limits**:\n"
            "          1. **Quantitative Thresholds**: State exact numeric limits, capacities, tolerances, and test values\n"
            "          2. **Dedicated Amendment Status**: State 'Dedicated Amendment Available: Amendment No. X' OR 'No Dedicated Amendment Released'\n"
            "   - Only pure conversational greetings (e.g. 'hello', 'hi') should be plain text without bullets.\n\n"
            "5. ACTIONABLE ROUTING (next_step):\n"
            "   - Always provide the direct official portal in next_step: Manakonline (https://manakonline.in), CRS (https://crsbis.in), or BIS Care App.\n"
            "   - If the user explicitly requested 'pdf', 'dossier', or 'full research', state in next_step: 'Your official BIS Compliance Research Dossier (PDF) has been compiled. Click \"📄 Download Research PDF\" below to save the official document.'\n"
            "     Otherwise, do not mention PDF download.\n\n"
            "Chat history:\n{chat_history}\n\nContext:\n{context}"
        )

    def _parse_fallback_response(self, text_content: str, query: str) -> BISResponse:
        """Parse raw text output into structured BISResponse."""
        if text_content.startswith("{") or "```json" in text_content or "```" in text_content:
            try:
                json_str = text_content
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()
                import json
                parsed_json = json.loads(json_str)
                if isinstance(parsed_json, dict) and "core_response" in parsed_json:
                    return BISResponse(**{k: parsed_json[k] for k in BISResponse.model_fields if k in parsed_json})
            except Exception:
                pass

        is_codes = re.findall(r"\bIS\s*:?\s*\d{3,5}(?:\s*\([^)]+\))?(?::\d{4})?\b", text_content, re.IGNORECASE)
        unique_standards = list(dict.fromkeys(is_codes))

        return BISResponse(
            core_response=text_content,
            applicable_standards=unique_standards,
            source_citation="BIS Official Documentation / Local Knowledge Base",
            next_step="Visit official Manakonline portal (https://manakonline.in) for online registration.",
            follow_up_prompt="Would you like details on testing parameters or fee structures?",
            intent_localized="सामान्य परामर्श" if any("\u0900" <= c <= "\u097F" for c in query) else "General Consultation"
        )

    def stream_synthesize(
        self,
        chat_history: str,
        context: str,
        query: str,
        is_chat: bool,
        state: Optional[AgentState] = None,
    ):
        """
        Stream LLM synthesis tokens progressively as they are generated.
        Yields:
          {"type": "token", "token": str}
        and finishes with:
          {"type": "final_output", "output": BISResponse}
        """
        system_prompt = self._build_system_prompt(is_chat)
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{query}")])
        msg = prompt.format_messages(chat_history=chat_history, context=context, query=query)
        llm = self._get_llm_for_state(state)

        final_output = None
        prev_text = ""

        # 1. Try structured streaming
        try:
            structured_llm = llm.with_structured_output(BISResponse)
            for chunk in structured_llm.stream(msg):
                if isinstance(chunk, BISResponse):
                    curr_text = chunk.core_response or ""
                    delta = curr_text[len(prev_text):]
                    if delta:
                        yield {"type": "token", "token": delta}
                        prev_text = curr_text
                    final_output = chunk
                elif isinstance(chunk, dict):
                    curr_text = chunk.get("core_response", "") or ""
                    delta = curr_text[len(prev_text):]
                    if delta:
                        yield {"type": "token", "token": delta}
                        prev_text = curr_text
        except Exception as exc:
            logger.info("Structured streaming fallback to text stream: %s", exc)
            final_output = None

        if final_output is not None:
            if not prev_text and final_output.core_response:
                yield {"type": "token", "token": final_output.core_response}
            self.token_tracker.add_llm_usage({
                "prompt_tokens": len(str(msg)) // 4,
                "completion_tokens": len(final_output.core_response) // 4,
                "total_tokens": (len(str(msg)) + len(final_output.core_response)) // 4,
            })
            yield {"type": "final_output", "output": final_output}
            return

        # 2. Fallback: text streaming
        full_text = ""
        try:
            for chunk in llm.stream(msg):
                delta = ""
                if isinstance(chunk.content, str):
                    delta = chunk.content
                elif isinstance(chunk.content, list):
                    for block in chunk.content:
                        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                            delta += block["text"]
                if delta:
                    full_text += delta
                    yield {"type": "token", "token": delta}
        except Exception as exc:
            logger.error("Text stream error: %s", exc)

        parsed_res = self._parse_fallback_response(full_text, query)
        self.token_tracker.add_llm_usage({
            "prompt_tokens": len(str(msg)) // 4,
            "completion_tokens": len(full_text) // 4,
            "total_tokens": (len(str(msg)) + len(full_text)) // 4,
        })
        yield {"type": "final_output", "output": parsed_res}

    @with_retry()
    def _synthesize(self, chat_history: str, context: str, query: str, is_chat: bool, state: Optional[AgentState] = None) -> BISResponse:
        system_prompt = self._build_system_prompt(is_chat)
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{query}")])
        msg = prompt.format_messages(chat_history=chat_history, context=context, query=query)
        llm = self._get_llm_for_state(state)

        # 1. Try structured output if supported by model
        try:
            structured_llm = llm.with_structured_output(BISResponse, include_raw=True)
            raw_res = structured_llm.invoke(msg)
            if isinstance(raw_res, dict) and "raw" in raw_res:
                self.token_tracker.add_llm_usage(getattr(raw_res["raw"], "usage_metadata", None))
                parsed = raw_res.get("parsed")
                if isinstance(parsed, BISResponse):
                    return parsed
            elif isinstance(raw_res, BISResponse):
                return raw_res
        except Exception as exc:
            logger.info("Structured response output unavailable (%s). Using raw text invocation fallback.", exc)

        # 2. Fallback: Direct invocation for local Ollama / models without structured output
        resp = llm.invoke(msg)
        self.token_tracker.add_llm_usage(getattr(resp, "usage_metadata", None))
        text_content = str(resp.content).strip()
        return self._parse_fallback_response(text_content, query)

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
                state=state,
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
