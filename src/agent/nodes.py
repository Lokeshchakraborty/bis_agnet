"""
Graph Node Implementations, Prompt Templates, and Routing Helpers for BIS Agent.
"""
from __future__ import annotations

import concurrent.futures
import functools
import logging
import re
import time
from typing import Callable, Optional, TypeVar,Any

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
                        raw_wait = float(m.group(1)) if m else backoff * (2 ** (attempt - 1))
                        # Cap rate limit wait to 2.5s max so we stay within the 15s turn SLA
                        wait = min(raw_wait, 2.5)
                    else:
                        wait = min(backoff * (2 ** (attempt - 1)), 2.0)
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

# Pronouns and demonstratives that indicate a reference to prior context
_CONTEXT_PRONOUNS = {
    "it", "its", "this", "that", "these", "those", "them", "they", "which",
    "above", "same", "said", "mentioned", "previous", "earlier", "last",
    "former", "latter", "such",
    # Hindi / Hinglish
    "iska", "iske", "iski", "isme", "uska", "uske", "uski", "usme",
    "woh", "ye", "yeh", "wo", "unka", "unke", "unki", "inhe", "inki",
    "pehle", "pichla", "pichle", "pichli", "wala", "wale", "wali",
}

# Pre-compiled regex for referential/comparative phrases anywhere in query
_REFERENTIAL_PATTERN = re.compile(
    r"\b(compare\s+(it|this|that|them|these|those)|same\s+(as|standard|product)"
    r"|vs\s+the\s+previous|go\s+back\s+to|you\s+mentioned|we\s+(discussed|talked)"
    r"|refer(ring)?\s+to|about\s+(it|this|that|the\s+same)"
    r"|for\s+(it|this|that|the\s+same)|(is|are)\s+there\s+any\s+.*(amendment|update|change|notification)"
    r"|और\s+(बताओ|बताइये)|इसके\s+बारे|उसके\s+बारे|पहले\s+वाला)\b",
    re.IGNORECASE,
)

COMMON_GREETINGS = {
    "hi", "hello", "hey", "namaste", "namaskar", "namastey", "नमस्ते", "नमस्कार",
    "kaise ho", "kya haal hai", "good morning", "good evening", "good afternoon",
    "thanks", "thank you", "dhanyawaad", "shukriya", "धन्यवाद", "शुक्रिया",
    "who are you", "aap kaun ho", "आप कौन हैं", "help", "madad"
}


def _needs_rewrite(query: str) -> bool:
    """Check if query is dependent on prior conversational context.

    Scans the *entire* query for pronouns, demonstratives, referential phrases,
    and follow-up triggers — not just the first 3 words.
    """
    q = query.strip().lower()
    words = re.findall(r"[\w\u0900-\u097F]+", q)
    if not words:
        return False

    # Very short queries are almost always context-dependent
    if len(words) <= 3:
        return True

    # Check first word for continuation markers
    first_word = words[0]
    if first_word in {"and", "aur", "also", "or", "kya", "kaise", "kitna", "kitni", "but", "lekin", "par"}:
        return True

    # "what" and "how" are only context-dependent when followed by certain words
    if first_word in {"what", "how"} and len(words) >= 2:
        second_word = words[1]
        if second_word in {"about", "else", "more", "next", "then", "regarding", "of"}:
            return True

    # Scan the ENTIRE query for pronouns/demonstratives (Bug 1 & 5 fix)
    if any(w in _CONTEXT_PRONOUNS for w in words):
        return True

    # Check for referential/comparative phrases anywhere in the query
    if _REFERENTIAL_PATTERN.search(q):
        return True

    # Legacy: check first 3 words for follow-up triggers
    return any(w in FOLLOWUP_TRIGGERS for w in words[:3])


FAST_INTENT_PATTERNS = [
    (Intent.HALLMARK, re.compile(
        r"\b(hallmark|hallmarking|huid|ahc|assaying|assay|gold|silver|sona|chandi|carat|karat|"
        r"jewel|jewelry|jewellery|aabhooshan|ornament|purity|fineness|caratmeter|xrf|"
        r"hallmark\s*centre|hallmark\s*center|recognized\s*assaying|"
        r"हॉलमार्क|हॉलमार्किंग|सोना|चांदी|आभूषण|शुद्धता)\b", re.I)),
    (Intent.REGISTRATION, re.compile(
        r"\b(crs|compulsory registration|meity|electronics registration|"
        r"laptop|mobile|charger|adapter|led|power bank|solar panel|smart watch|"
        r"it\s*goods|electronic\s*product|bis\s*registration|self.?declaration|"
        r"r\-number|registration\s*number|crsbis|inclusion\s*order)\b", re.I)),
    (Intent.CERTIFICATION, re.compile(
        r"\b(isi\s*mark|fmcs|qco|quality\s*control\s*order|cml\s*number|cml|"
        r"foreign\s*manufacturer|scheme.?i|scheme.?1|scheme.?iv|scheme.?4|"
        r"factory\s*audit|air\s*appointment|product\s*certification|"
        r"licence|license|licensee|isi\s*certification|mandatory\s*certification|"
        r"bis\s*licence|bis\s*license|renewal|mark\s*fee|marking\s*fee)\b", re.I)),
    (Intent.LABORATORY, re.compile(
        r"\b(laboratory|testing\s*lab|lrs|lims|nabl|calibration|test\s*report|"
        r"recognized\s*lab|accredited|lab\s*recognition|lab\s*fee|"
        r"prayogshala|प्रयोगशाला|परीक्षण|lab\s*registration)\b", re.I)),
    (Intent.MANAKONLINE, re.compile(
        r"\b(manakonline|manak\s*online|e.?bis|e.?cml|portal\s*login|portal\s*registration|"
        r"online\s*application|upload\s*document|manak\s*portal|bis\s*portal|"
        r"portal\s*password|track\s*application|application\s*status)\b", re.I)),
    (Intent.CATALOG_SEARCH, re.compile(
        r"\b(pipe|pipes|cement|steel|tank|tanks|cable|cables|battery|batteries|"
        r"helmet|helmets|toy|toys|wire|wires|plywood|fertilizer|fertiliser|glass|"
        r"cooker|tyre|tire|water\s*purifier|ro\s*purifier|packaged\s*drinking|"
        r"mineral\s*water|paani|pani|khilona|food\s*grade|stainless|iron|"
        r"petroleum|lpg|cylinder|gas\s*stove|gas\s*burner|cloth|textile|fabric|"
        r"footwear|shoes|sandal|bolt|nut|fastener|bearing|valve|pump|"
        r"paint|varnish|plaster|brick|aggregate|rod|bar|sheet|plate|"
        r"standard\s*for|specification\s*for|indian\s*standard)\b", re.I)),
]

# Pre-compiled chat patterns for broader coverage
_CHAT_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|namaste|namaskar|good\s*(morning|evening|afternoon|night)|"
    r"thanks|thank\s*you|dhanyawaad|shukriya|who\s*are\s*you|what\s*can\s*you\s*do|"
    r"aap\s*kaun|kaise\s*ho|kya\s*haal|help\s*me|introduce|about\s*yourself|"
    r"tum\s*kaun|aap\s*kya|kya\s*kar\s*sakte|tell\s*me\s*about\s*yourself|"
    r"नमस्ते|नमस्कार|धन्यवाद|शुक्रिया|आप\s*कौन|मदद)\s*[?!.]*\s*$", re.I)


def _fast_classify(query: str) -> Optional[Intent]:
    """Zero-token instant classification for IS codes, greetings, and domain keywords.
    
    Expanded to cover ~90% of real queries without any LLM call.
    """
    q_norm = query.strip().lower()
    # 1. Exact IS code pattern (e.g. "IS 1417", "IS:269", "IS 12701")
    if re.search(r"\bIS\s*:?\s*\d{3,5}\b", query, re.IGNORECASE) or re.match(r"^\s*IS\s*\d+", query, re.IGNORECASE):
        return Intent.CATALOG_SEARCH

    # 2. Chat/greetings — both short and pattern-based
    words = re.findall(r"[\w\u0900-\u097F]+", q_norm)
    if not words:
        return Intent.CHAT
    if 1 <= len(words) <= 3:
        phrase = " ".join(words)
        if phrase in COMMON_GREETINGS or words[0] in COMMON_GREETINGS:
            return Intent.CHAT
    if _CHAT_PATTERNS.match(q_norm):
        return Intent.CHAT

    # 3. High-confidence domain keywords (expanded)
    for intent, pattern in FAST_INTENT_PATTERNS:
        if pattern.search(q_norm):
            return intent

    return None


def _clean_agent_for_history(text: str) -> str:
    """Strip internal follow-up prompt tag so synthesis LLM does not mention or echo it."""
    return re.sub(r'\n*\[?i asked (?:the |as )?follow[- ]?up(?: question)?\]?:?.*$', '', text, flags=re.IGNORECASE | re.DOTALL).strip()


def _format_history(chat_history: list[tuple[str, str]], condensed: bool = False) -> str:
    """Format chat history for LLM prompts.

    Args:
        chat_history: List of (user_query, agent_response) tuples.
        condensed: If True, summarize earlier turns to a single line each,
                   keeping only the most recent turn in full. This reduces
                   token usage while preserving context signal for the LLM.
    """
    if not chat_history:
        return "(no prior turns)"
    raw_recent = list(chat_history)[-CONFIG.history_window:]
    recent = [(u, _clean_agent_for_history(a)) for u, a in raw_recent]

    if not condensed or len(recent) <= 1:
        return "\n".join(f"User: {u}\nAgent: {a}" for u, a in recent)

    # Condensed mode: earlier turns get a 1-line topic summary,
    # only the latest turn is shown in full.
    lines = []
    for i, (u, a) in enumerate(recent):
        if i < len(recent) - 1:
            # Truncate agent response to first sentence or 120 chars
            summary = a.split("\n")[0][:120]
            if len(a) > 120:
                summary += "..."
            lines.append(f"[Turn {i+1}] User: {u} | Agent (summary): {summary}")
        else:
            # Most recent turn in full
            lines.append(f"User: {u}\nAgent: {a}")
    return "\n".join(lines)


RESEARCH_QUERY_RE = re.compile(
    r"\b(compliance\s*report|research\s*report|research|dossier|full\s*analysis|"
    r"detailed\s*report|compliance\s*guide|complete\s*analysis|in-depth|exhaustive|"
    r"qco\s*analysis|regulatory\s*report|standards\s*report|testing\s*research|"
    r"generate\s*report|make\s*report|detailed\s*compliance|comprehensive\s*report|"
    r"anusamdhan|report\s*banao|detailed\s*guide|full\s*report|application\s*standards|"
    r"certification\s*&\s*testing|quality\s*control\s*order\s*\(qco\))\b",
    re.IGNORECASE,
)


def _is_research_query(query: str) -> bool:
    """Detect if the user is requesting a comprehensive compliance research report/dossier."""
    if not query:
        return False
    return bool(RESEARCH_QUERY_RE.search(query))


DIFFERENCE_QUERY_RE = re.compile(
    r"\b(difference|differences|diff|differ|differs|differentiates?|differentiating|"
    r"versus|vs\.?|compare|compares|comparing|comparison|comparative|"
    r"distinguish|distinguishes|distinguishing|distinction|contrast|contrasting|"
    r"विपरीत|अंतर|तुलना)\b"
    r"|\b(isi\s+or\s+crs|scheme\s*i\s+or\s+scheme\s*ii|huid\s+or\s+hallmark)\b",
    re.IGNORECASE,
)


def _is_difference_query(query: str) -> bool:
    """Detect if the user is asking to compare or find differences between standards, schemes, or products."""
    if not query:
        return False
    return bool(DIFFERENCE_QUERY_RE.search(query))



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

    def _get_llm_for_state(self, state: Optional[AgentState] = None, is_research: bool = False):
        max_tokens = 8192 if is_research else CONFIG.max_completion_tokens
        provider = state.get("llm_provider") if state else None
        model = state.get("llm_model") if state else None
        api_key = state.get("llm_api_key") if state else None
        base_url = state.get("llm_base_url") if state else None

        if provider or is_research:
            from src.agent.llm_factory import create_llm_model
            try:
                return create_llm_model(
                    provider=provider,
                    model_name=model,
                    api_key=api_key,
                    base_url=base_url,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                logger.warning("Failed to create dynamic LLM for provider '%s': %s. Falling back to default.", provider, exc)
        return self.llm

    @with_retry()
    def _rewrite_query(self, history_window: list[tuple[str, str]], query: str, state: Optional[AgentState] = None) -> str:
        """Rewrite a context-dependent query into a standalone query.

        Args:
            history_window: Recent (user, agent) turn tuples (last N turns).
            query: The user's latest raw query.
            state: Current agent state for dynamic LLM selection.
        """
        # Format the conversation window for the rewriter
        history_text = "\n".join(
            f"--- Turn {i+1} ---\nUser: {u}\nAgent: {a}"
            for i, (u, a) in enumerate(history_window)
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You convert a user's reply into a full standalone search query by resolving "
             "references from the conversation history.\n\n"
             "You are given the RECENT CONVERSATION HISTORY (multiple turns) and the user's latest reply.\n\n"
             "The agent's messages may contain a section tagged '[I asked as follow-up]: ...' "
             "which is the exact follow-up question the agent posed to the user.\n\n"
             "Rules:\n"
             "1. If the user replies with 'yes', 'sure', 'ok', 'explain', 'tell me more', 'haan', 'ha', "
             "'batao', 'bataiye', 'theek hai', or any short affirmation — look at the MOST RECENT "
             "'[I asked as follow-up]' section and turn THAT question into the standalone query.\n"
             "2. Preserve the user's language style (English, Hindi, or Hinglish).\n"
             "3. If the user replies with a specific answer or correction to the follow-up, "
             "incorporate that answer into the standalone query.\n"
             "4. If the user references something from an EARLIER turn (e.g. 'the cement standard "
             "you mentioned before', 'go back to...', 'the previous one'), scan ALL provided turns "
             "to identify the correct subject and incorporate it.\n"
             "5. Resolve ALL pronouns (it, this, that, these, those, them) and demonstratives "
             "(iska, uska, woh, ye, pehle wala) to their concrete referent from the history.\n"
             "6. If there is no follow-up section, use the agent's answers as context to "
             "understand what the user is referring to.\n"
             "7. Output ONLY the standalone query — no preamble, no explanation."),
            ("human", "Recent Conversation History:\n{history_text}\n\nUser's Latest Reply: {query}"),
        ])
        msg = prompt.format_messages(history_text=history_text, query=query)
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
        incoming_sq = state.get("standalone_query")
        if incoming_sq and "(Product Context:" in incoming_sq:
            return {"standalone_query": incoming_sq}

        query_text = state.get("query", "")
        if not state.get("chat_history"):
            sq = incoming_sq or query_text
        elif not _needs_rewrite(query_text):
            logger.info("Self-contained query detected — skipping rewrite")
            sq = incoming_sq or query_text
        else:
            try:
                # Pass the full recent history window, not just the last turn (Bug 2 fix)
                history_window = list(state["chat_history"])[-CONFIG.history_window:]
                sq = self._rewrite_query(history_window, query_text, state=state)
            except Exception as exc:
                logger.error("Query rewrite failed, using raw query: %s", exc)
                sq = incoming_sq or query_text

        return {"standalone_query": sq or query_text}

    # Lean, compact prompt for LLM intent classification — minimizes token count
    _INTENT_PROMPT = ChatPromptTemplate.from_messages([
        ("system",
         "Classify the query into ONE category. Reply with ONLY the category name.\n"
         "Categories: chat, hallmark, registration, certification, laboratory, manakonline, catalog_search\n"
         "Product names → catalog_search. Greetings → chat."),
        ("human", "{query}"),
    ])

    @with_retry()
    def _classify(self, query: str, state: Optional[AgentState] = None) -> Intent:
        msg = self._INTENT_PROMPT.format_messages(query=query)
        llm = self._get_llm_for_state(state)

        # 1. Try structured intent classification (reuse cached wrapper when using default LLM)
        try:
            if state and state.get("llm_provider"):
                structured_intent_llm = llm.with_structured_output(IntentResult, include_raw=True)
            elif self.structured_intent_llm:
                structured_intent_llm = self.structured_intent_llm
            else:
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

        # 2. Lightweight text fallback
        resp = llm.invoke(msg)
        self.token_tracker.add_llm_usage(getattr(resp, "usage_metadata", None))
        text = str(resp.content).strip().lower()
        # Direct match on first word/token of response for speed
        for cat in Intent:
            if cat.value == text or text.startswith(cat.value):
                return cat
        # Substring fallback
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

            is_res = bool(state.get("is_research")) or _is_research_query(state.get("query", "")) or _is_research_query(state["standalone_query"])
            max_chars = (getattr(CONFIG, "context_max_chars", 1400) * CONFIG.rerank_top_n * 2) if is_res else (getattr(CONFIG, "context_max_chars", 1400) * CONFIG.rerank_top_n)
            if len(context) > max_chars:
                context = context[:max_chars] + "\n...(context bounded)"

            # Augment with live structured scraping if query targets QCOs, orders, circulars, specific standards, or research mode
            sq_lower = state["standalone_query"].lower()
            needs_live = is_res or any(k in sq_lower for k in ["qco", "order", "circular", "notification", "amendment", "deadline", "latest", "mandat", "fee", "standard"]) or bool(re.search(r"\bis\s*:?\s*\d", sq_lower))
            if needs_live:
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                try:
                    fut = executor.submit(scrape_bis_portal, state["standalone_query"], is_research=bool(is_res))
                    scraped = fut.result(timeout=getattr(CONFIG, "retrieval_timeout", 3.0))
                    if scraped.strip():
                        scrape_bound = 4000 if is_res else 1800
                        context = f"[LOCAL KNOWLEDGE BASE]:\n{context}\n\n[LIVE PORTAL DATA]:\n{scraped[:scrape_bound]}"
                except Exception as exc:
                    logger.debug("Live scraper augmentation skipped for domain %s: %s", domain.value, exc)
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)

            self.token_tracker.add_embedding_text(context)
            return {"retrieved_context": context, "domain": domain.value}

        return _node

    def retrieve_catalog(self, state: AgentState) -> dict:
        """Concurrent live BIS portal scraping + local Chroma DB retrieval."""
        sq = state["standalone_query"]
        self.token_tracker.add_embedding_text(sq)

        is_res = bool(state.get("is_research")) or _is_research_query(state.get("query", "")) or _is_research_query(sq)
        max_c = getattr(CONFIG, "context_max_chars", 1400) * (3 if is_res else 1)

        def _get_db_docs():
            try:
                docs = self.catalog_retriever.invoke(sq)
                return "\n".join(d.page_content[:max_c] for d in docs) if docs else "No local catalog entries found."
            except Exception as exc:
                logger.warning("Local catalog retrieval error: %s", exc)
                return "No local catalog entries found."

        def _get_scraped_data():
            try:
                scraped = scrape_bis_portal(sq, is_research=bool(is_res))
                bound = max_c * 3 if is_res else max_c * 2
                if len(scraped) > bound:
                    scraped = scraped[:bound] + "\n...(portal data bounded)"
                return scraped if scraped.strip() else "(scraper returned no content for this query)"
            except Exception as exc:
                logger.warning("BIS portal scrape error (%s). Using local DB only.", exc)
                return "Live portal data unavailable."

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        try:
            future_db = executor.submit(_get_db_docs)
            future_scrape = executor.submit(_get_scraped_data)
            db_context = future_db.result()
            try:
                scraped = future_scrape.result(timeout=getattr(CONFIG, "retrieval_timeout", 3.0))
            except Exception as exc:
                logger.debug("Live scraper in retrieve_catalog timed out (%s). Using local knowledge base.", exc)
                scraped = "(Live portal query timed out - relying on local knowledge base)"
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        combined = f"[LIVE PORTAL DATA]:\n{scraped}\n\n[LOCAL KNOWLEDGE BASE]:\n{db_context}"
        self.token_tracker.add_embedding_text(combined)
        return {"retrieved_context": combined, "domain": "catalog"}

    _RESEARCH_SYSTEM_PROMPT = (
        "You are an authoritative Senior Regulatory & Standards Research Specialist at the Bureau of Indian Standards (BIS) and Ministry Regulatory Advisory.\n"
        "You produce exhaustive, publication-grade Technical Compliance & Standards Research Dossiers for ANY product category (e.g., Steel & Steel Products, Cement, Electronics & IT Goods, Toys, Chemicals & Petrochemicals, Food & Packaged Water, Batteries, Solar PV, Footwear, Fasteners, Pipes, Edible Oils, etc.).\n\n"
        "RESEARCH DOSSIER DIRECTIVES:\n"
        "1. COMPREHENSIVENESS & RIGOR: Provide thorough, in-depth technical analysis. Never truncate or emit superficial summaries. Draw from both the provided official context and authoritative statutory BIS frameworks.\n"
        "2. QUANTITATIVE PRECISION: Extract and document exact parameters, chemical limits, mechanical tolerances, dimensions, test thresholds, and fee schedules.\n"
        "3. EXCELLENT MARKDOWN FORMATTING:\n"
        "   - Use clean Markdown headers (## for sections, ### for subsections).\n"
        "   - Use Markdown tables ONLY for matrices/data (Sections 4, 6.1, 6.2, 9, 12). Every table MUST have a header row, a delimiter row (| :--- | :--- |), and each row MUST be on its own line.\n"
        "   - For narrative and legal sections (Sections 1, 2, 3, 5, 7, 8, 10, 11, 13), use bold callouts, numbered steps, and bulleted lists instead of tables.\n"
        "4. COMPLETE 13-SECTION COVERAGE: You MUST generate ALL 13 numbered sections below from start to finish.\n"
        "5. STRICT OUTPUT PURITY: Output ONLY the complete Markdown document. Do NOT emit raw JSON metadata, system integration schemas, 'OUTPUT FIELDS', or closing signature lines like 'Prepared by:' or '*End of Dossier.*'.\n\n"
        "MANDATORY 13-SECTION STRUCTURE:\n"
        "   ## 1. Executive Summary\n"
        "   - Statutory basis under the Bureau of Indian Standards Act, 2016 (BIS Act, 2016).\n"
        "   - State whether certification is voluntary or mandatory under a Quality Control Order (QCO) issued by the relevant Central Administrative Ministry.\n"
        "   - Core statutory mandate: Prohibition of manufacture, import, distribution, sale, or storage for sale without a valid BIS Licence (Standard Mark / ISI Mark / CRS Mark).\n"
        "   - Summary of key standards and Section 29 statutory penalties for non-compliance.\n\n"
        "   ## 2. Current Regulatory Position (QCO & Legal Framework)\n"
        "   - Official QCO / Gazette Order name, notification number, and issuing Ministry (e.g. MoFPI, Ministry of Steel, DPIIT, MeitY, etc.).\n"
        "   - Enforcement status & implementation timelines (active mandates and transition dates).\n"
        "   - Exemptions or concessions: MSME grace periods, R&D/prototyping sample quotas, or export-only manufacturing provisions.\n"
        "   - Statutory liabilities under Section 29 of BIS Act, 2016 (imprisonment up to 2 years, fine of ₹2 Lakhs up to ₹5 Lakhs, or up to 10x value of goods).\n\n"
        "   ## 3. What is an “Application Standard”?\n"
        "   - Clarify the statutory definition of an Application Standard / Product Standard under BIS.\n"
        "   - Explain why general grade standards differ from end-use application standards.\n"
        "   - The critical role of product-specific standards in structural safety, industrial reliability, and consumer protection.\n\n"
        "   ## 4. High-Use Application Standards Matrix\n"
        "   - Provide an exhaustive Markdown Table covering all major product forms, grades, and applications:\n"
        "     | Application / Product Form | Primary Indian Standard (IS) | Common Alternative / Linked Standards | Standard Title, Scope & Key Coverage |\n"
        "     | :--- | :--- | :--- | :--- |\n"
        "     (Include all relevant IS standards identified in context or standard industry practice).\n\n"
        "   ## 5. BIS Certification Workflow (Step-by-Step)\n"
        "   - Detail the full 8-step compliance roadmap with numbered bold steps (1. to 8.):\n"
        "     1. Standard & STI Identification (Scheme of Testing and Inspection)\n"
        "     2. In-house Factory Testing Laboratory & Competent Personnel Setup\n"
        "     3. Online Application Filing on Manakonline (https://manakonline.in)\n"
        "     4. Scrutiny & Preliminary Review by BIS Technical Officers\n"
        "     5. Factory Audit & Verification of Quality Management System (QMS)\n"
        "     6. Independent Sample Drawing & Testing at BIS-Recognized / NABL Labs\n"
        "     7. Grant of Licence (CM/L Number) with initial 1-2 year validity\n"
        "     8. Post-Licence Surveillance, Market Sampling & Periodic Audits\n\n"
        "   ## 6. Testing & Quality Control Requirements\n"
        "   - 6.1 In-house laboratory equipment checklist (Markdown table: Equipment, Minimum Specification, Calibration Frequency).\n"
        "   - 6.2 Critical test parameters and acceptance thresholds (Markdown table: Parameter, Test Method IS, Acceptable Limit, Frequency).\n"
        "   - 6.3 Mandatory testing frequencies, batch sampling, and record-keeping protocols.\n\n"
        "   ## 7. Documentation Required for Application\n"
        "   - Legal proof of premises, plant layout, machinery list, in-house lab equipment list with NABL certificates, QC personnel details, raw material MTCs, SOPs.\n\n"
        "   ## 8. Special Compliance Requirements for Imports & Foreign Manufacturers\n"
        "   - Foreign Manufacturers Certification Scheme (FMCS, Scheme-I) regulations.\n"
        "   - Mandatory appointment of Authorized Indian Representative (AIR) residing in India (Form V undertaking).\n"
        "   - Performance Bank Guarantee (PBG) of USD $10,000 from an RBI-approved bank.\n"
        "   - Indian Customs clearance requirements (Bill of Entry CM/L marking verification, clearance blocks).\n\n"
        "   ## 9. Amendment & Enforcement Watchlist\n"
        "   - Detailed table of recent amendments, revisions, gazette extensions, and future transition dates:\n"
        "     | Amendment / Gazette Notification | Effective Date | Regulatory & Technical Changes |\n"
        "     | :--- | :--- | :--- |\n\n"
        "   ## 10. Recommended Compliance Checklist for Manufacturers & Buyers\n"
        "   - Phase 1: Pre-application readiness checklist with [ ] checkboxes\n"
        "   - Phase 2: Application submission & factory audit checklist\n"
        "   - Phase 3: Post-licence maintenance & surveillance returns\n"
        "   - Buyer & Importer Verification checklist (verifying CM/L on BIS Care App and Manakonline).\n\n"
        "   ## 11. Selected Standards Reference List\n"
        "   - Numbered list of all identified Indian Standards with complete title and active status.\n\n"
        "   ## 12. Source-Based Findings & Technical Highlights\n"
        "   - Markdown table: | Finding / Critical Parameter | Technical Insight & Failure Mode | Industry Best Practice |\n\n"
        "   ## 13. Official Sources & Verification Links\n"
        "   - Manakonline: https://manakonline.in\n"
        "   - CRS Portal: https://crsbis.in\n"
        "   - Know Your Standards: https://standards.bis.gov.in\n"
        "   - BIS Care Mobile App: For real-time CM/L and HUID verification\n\n"
        "Chat history:\n{chat_history}\n\nContext:\n{context}"
    )

    def _build_system_prompt(self, is_chat: bool, is_research: bool = False, is_difference: bool = False) -> str:
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
        if is_research:
            return self._RESEARCH_SYSTEM_PROMPT

        diff_clause = ""
        if is_difference:
            diff_clause = (
                "🚨 MANDATORY COMPARISON TABLE DIRECTIVE (DIFFERENCE / VERSUS QUERY DETECTED):\n"
                "- The user is specifically asking for a DIFFERENCE, COMPARISON, or VERSUS breakdown.\n"
                "- You MUST structure your answer around an exhaustive, multi-column Markdown Comparison Table!\n"
                "- Every table row MUST begin and end with a vertical pipe '|' (e.g. '| Key Parameter | Option A | Option B |').\n"
                "- Format:\n"
                "  1. Overview Paragraph (2-3 sentences) defining the core distinction.\n"
                "  2. Comprehensive Markdown Comparison Table:\n"
                "     | Key Parameter / Feature | Option A / Scheme A | Option B / Scheme B |\n"
                "     | :--- | :--- | :--- |\n"
                "     (Include at least 6-8 comprehensive comparison rows: Legal Basis, Product Scope, Compliance Model, Factory Audit, Testing, Mark/Logo, Portal, Validity, AIR Rules).\n"
                "  3. Key Takeaways & Guidance: Follow the table with structured bullet points ('• ') detailing critical procedural nuances, penalty implications under Section 29 of BIS Act 2016, and actionable recommendations.\n\n"
            )

        return (
            f"{diff_clause}"
            "You are an expert BIS (Bureau of Indian Standards) AI Assistant.\n"
            "Answer authoritatively based on official BIS regulations, Indian Standards (IS), and provided context.\n\n"
            "KEY DIRECTIVES:\n"
            "1. REGULATORY FIDELITY & STANDARDS:\n"
            "   - Always identify exact Indian Standards (e.g. 'IS 1417', 'IS 12701', 'IS 13252 (Part 1):2010', 'IS 269').\n"
            "   - Always cite statutory laws as 'Bureau of Indian Standards Act, 2016 (BIS Act, 2016)'.\n"
            "   - In 'applicable_standards', list all relevant standards formatted as 'IS XXXX - Title'.\n\n"
            "2. MANDATORY COMPARISON TABLES FOR DIFFERENCE & VERSUS QUERIES:\n"
            "   - Whenever the user asks about DIFFERENCES, COMPARISONS, DISTINCTIONS, or VERSUS (e.g. 'difference between ISI and CRS', 'Scheme I vs Scheme II', 'Hallmarking vs ISI', 'IS 4984 vs IS 12701', 'compare X and Y'):\n"
            "     * You MUST ALWAYS provide a comprehensive, beautifully formatted Markdown comparison table (| Comparison Feature | [Subject A] | [Subject B] |).\n"
            "     * Compare key dimensions: Statutory Scheme, Product Scope, Conformity Model (SDoC vs 3rd-party inspection), Testing Requirements, Factory Audit Requirements, Standard Mark / Logo, Application Portal, License Validity, and Foreign Manufacturer / AIR rules.\n"
            "     * Include an overview paragraph before the table and bulleted takeaways after the table.\n\n"
            "3. MANDATORY QUANTITATIVE & PARAMETER EXTRACTION:\n"
            "   - Extract exact numbers, capacities, tolerances, test limits, migration thresholds (e.g. 60 mg/l for IS 12701), and karat fineness (e.g. 24K/999, 22K/916, 18K/750).\n"
            "   - Use clean Markdown tables when presenting or comparing technical parameters, grades, or test limits.\n\n"
            "4. STRICT LANGUAGE & SCRIPT MATCHING:\n"
            "   - HINDI (Devanagari): Answer in natural Hindi; set intent_localized in Hindi (e.g. 'हॉलमार्क पंजीकरण').\n"
            "   - HINGLISH: Answer in natural conversational Hinglish using Roman script.\n"
            "   - ENGLISH: Professional, clear technical English.\n\n"
            "5. MANDATORY DUAL STRUCTURE (FOR STANDARD COMPLIANCE QUERIES):\n"
            "   - For standard compliance or product-specific inquiries (when not a pure difference query), follow this two-tier format:\n"
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
            "6. ACTIONABLE ROUTING (next_step):\n"
            "   - Always provide the direct official portal in next_step: Manakonline (https://manakonline.in), CRS (https://crsbis.in), or BIS Care App.\n"
            "   - If the user explicitly requested 'pdf', 'dossier', or 'full research', state in next_step: 'Your official BIS Compliance Research Dossier (PDF) has been compiled. Click \"📄 Download Research PDF\" below to save the official document.'\n"
            "     Otherwise, do not mention PDF download.\n\n"
            "Chat history:\n{chat_history}\n\nContext:\n{context}"
        )

    def _parse_fallback_response(self, text_content: Any, query: str) -> BISResponse:
        """Parse raw text/list/dict output into structured BISResponse."""
        if isinstance(text_content, list):
            clean_text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in text_content
            ).strip()
        elif isinstance(text_content, dict):
            if "core_response" in text_content:
                return BISResponse(**{k: text_content[k] for k in BISResponse.model_fields if k in text_content})
            clean_text = str(text_content.get("text", text_content))
        else:
            clean_text = str(text_content or "").strip()
            # If it was a stringified Python representation of a list of text dicts
            if clean_text.startswith("[{'type':") or clean_text.startswith('[{"type":'):
                try:
                    import ast
                    parsed_list = ast.literal_eval(clean_text)
                    if isinstance(parsed_list, list):
                        clean_text = "".join(
                            p.get("text", "") if isinstance(p, dict) else str(p)
                            for p in parsed_list
                        ).strip()
                except Exception:
                    texts = re.findall(r"['\"]text['\"]\s*:\s*['\"](.*?)['\"](?:\s*,\s*['\"]index['\"]|\s*})", clean_text, re.DOTALL)
                    if texts:
                        clean_text = "".join(texts).replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'").strip()

        if clean_text.startswith("{") or "```json" in clean_text:
            try:
                json_str = clean_text
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif clean_text.startswith("{") and clean_text.endswith("}"):
                    json_str = clean_text.strip()
                import json
                parsed_json = json.loads(json_str)
                if isinstance(parsed_json, dict) and "core_response" in parsed_json:
                    return BISResponse(**{k: parsed_json[k] for k in BISResponse.model_fields if k in parsed_json})
            except Exception:
                pass

        if not clean_text:
            clean_text = "I encountered an issue synthesizing the response. Please verify your query or model connection."

        from src.agent.guardrails import clean_leaked_system_blocks
        clean_text, leaked_stds = clean_leaked_system_blocks(clean_text)

        is_codes = re.findall(r"\bIS\s*:?\s*\d{3,5}(?:\s*\([^)]+\))?(?::\d{4})?\b", clean_text, re.IGNORECASE)
        combined_stds = list(dict.fromkeys(is_codes + leaked_stds))

        is_res = _is_research_query(query) or "1. Executive Summary" in clean_text or "Executive Summary" in clean_text
        next_step = (
            "Your official BIS Compliance & Standards Research Dossier (PDF) has been compiled. Click \"📄 Download Research PDF\" below to save the complete official document."
            if is_res
            else "Visit official Manakonline portal (https://manakonline.in) for online registration."
        )

        return BISResponse(
            core_response=clean_text,
            applicable_standards=combined_stds,
            source_citation="BIS Official Documentation / Ministry Gazette Orders / BIS Act, 2016",
            next_step=next_step,
            follow_up_prompt="Would you like details on testing parameters, STI requirements, or fee structures?",
            intent_localized="मानक अनुसंधान एवं अनुपालन" if any("\u0900" <= c <= "\u097F" for c in query) else ("Standards & Compliance Research" if is_res else "General Consultation"),
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
        is_research = bool(state.get("is_research")) if state else False
        if not is_research:
            is_research = _is_research_query(query) or (bool(state and _is_research_query(state.get("query", ""))))
        is_difference = (
            _is_difference_query(query)
            or (bool(state and _is_difference_query(state.get("query", ""))))
            or (bool(state and _is_difference_query(state.get("standalone_query", ""))))
        )

        system_prompt = self._build_system_prompt(is_chat, is_research=is_research, is_difference=is_difference)
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{query}")])
        msg = prompt.format_messages(chat_history=chat_history, context=context, query=query)
        llm = self._get_llm_for_state(state, is_research=is_research)

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
                        elif isinstance(block, str):
                            delta += block
                elif hasattr(chunk, "text") and chunk.text:
                    delta = chunk.text

                if delta:
                    full_text += delta
                    yield {"type": "token", "token": delta}
        except Exception as exc:
            logger.error("LLM stream error: %s", exc)
            if not full_text:
                try:
                    resp = llm.invoke(msg)
                    if isinstance(resp.content, str):
                        full_text = resp.content
                    elif isinstance(resp.content, list):
                        full_text = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in resp.content)
                    if full_text:
                        yield {"type": "token", "token": full_text}
                except Exception as invoke_exc:
                    logger.error("Direct invoke fallback error: %s", invoke_exc)
                    full_text = "I encountered an issue reaching the AI model. Please verify your model connection in settings."

        parsed_res = self._parse_fallback_response(full_text, query)
        self.token_tracker.add_llm_usage({
            "prompt_tokens": len(str(msg)) // 4,
            "completion_tokens": len(full_text) // 4,
            "total_tokens": (len(str(msg)) + len(full_text)) // 4,
        })
        yield {"type": "final_output", "output": parsed_res}

    @with_retry()
    def _synthesize(self, chat_history: str, context: str, query: str, is_chat: bool, state: Optional[AgentState] = None) -> BISResponse:
        is_research = bool(state.get("is_research")) if state else False
        if not is_research:
            is_research = _is_research_query(query) or (bool(state and _is_research_query(state.get("query", ""))))
        is_difference = (
            _is_difference_query(query)
            or (bool(state and _is_difference_query(state.get("query", ""))))
            or (bool(state and _is_difference_query(state.get("standalone_query", ""))))
        )

        system_prompt = self._build_system_prompt(is_chat, is_research=is_research, is_difference=is_difference)
        prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{query}")])
        msg = prompt.format_messages(chat_history=chat_history, context=context, query=query)
        llm = self._get_llm_for_state(state, is_research=is_research)

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
        return self._parse_fallback_response(resp.content, query)

    def synthesize_response(self, state: AgentState) -> dict:
        """Produce unified JSON response with multi-key caching."""
        is_chat = state["intent"] == Intent.CHAT.value
        is_research = bool(state.get("is_research")) or _is_research_query(state.get("query", "")) or _is_research_query(state.get("standalone_query", ""))
        state["is_research"] = is_research

        # 1. Cache lookup (bypass for research mode to ensure freshly updated comprehensive dossier)
        if CONFIG.cache_enabled and not is_chat and not is_research:
            uid = state.get("user_id", "default_user")
            key_raw = self.response_cache.make_key(state["intent"], state.get("query", ""), user_id=uid)
            key_standalone = self.response_cache.make_key(state["intent"], state["standalone_query"], user_id=uid)
            cached = self.response_cache.get(key_raw) or self.response_cache.get(key_standalone)
            is_diff = _is_difference_query(state.get("query", "")) or _is_difference_query(state.get("standalone_query", ""))
            if cached and is_diff and ("|" not in (cached.get("core_response") or "")):
                cached = None
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
                _format_history(state["chat_history"], condensed=True),
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
            result = validate_and_sanitize_response(
                result,
                state["query"],
                intent_confidence=raw_conf,
                standalone_query=state.get("standalone_query"),
            )
        except Exception as exc:
            logger.warning("Guardrail validation error: %s", exc)

        # 3. Store in cache
        if CONFIG.cache_enabled and not is_chat and result:
            try:
                payload = {"intent": state["intent"], "domain": state.get("domain", ""), "is_research": is_research, **result.model_dump()}
                uid = state.get("user_id", "default_user")
                key_standalone = self.response_cache.make_key(state["intent"], state["standalone_query"], user_id=uid)
                self.response_cache.set(key_standalone, payload)
                raw_q = state.get("query", "").strip()
                if raw_q and len(raw_q.split()) >= 3:
                    key_raw = self.response_cache.make_key(state["intent"], raw_q, user_id=uid)
                    self.response_cache.set(key_raw, payload)
            except Exception:
                pass

        return {
            "final_output": result,
            "cache_hit": False,
            "token_usage": self.token_tracker.get_turn_summary(cache_hit=False),
        }
