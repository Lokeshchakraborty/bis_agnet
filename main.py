"""
BIS Agentic RAG Assistant (Voice Enabled)

A LangGraph-based conversational agent for the Bureau of Indian Standards.

Architecture:
  - Cache-first: repeated queries skip the entire graph (0 LLM calls)
  - Domain queries (hallmark/certification/registration/laboratory/manakonline)
    use hybrid BM25 + dense retrieval + cosine reranking from ingested PDFs
  - Catalog/product queries use live BIS portal scraping + local Chroma DB
  - LLM is only called for final answer synthesis — not for retrieval or routing
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Callable, Deque, List, Optional, Tuple, TypedDict, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

from langchain_ollama import OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END
from langchain_mistralai import MistralAIEmbeddings

# --------------------------------------------------------------------------- #
# Path setup
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tools.scrap_details import scrape_bis_portal          # noqa: E402
from tools.retrieval_tools import hybrid_retrieve          # noqa: E402
from tools.response_cache import ResponseCache             # noqa: E402

load_dotenv()
console = Console()


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Config:
    embedding_provider: str = os.getenv("BIS_EMBEDDING_PROVIDER", "MistralAIEmbeddings")
    embedding_model: str = os.getenv("BIS_EMBEDDING_MODEL", "mistral-embed-2312")
    embedding_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_model: str = os.getenv("BIS_LLM_MODEL", "gemini-3.5-flash-lite")
    llm_temperature: float = float(os.getenv("BIS_LLM_TEMPERATURE", "0.2"))
    db_path: str = os.getenv("BIS_CHROMA_PATH", "./data/chroma_db")
    retriever_k: int = int(os.getenv("BIS_RETRIEVER_K", "3"))   # candidates before rerank
    rerank_top_n: int = int(os.getenv("BIS_RERANK_TOP_N", "2")) # kept after rerank
    history_window: int = int(os.getenv("BIS_HISTORY_WINDOW", "3"))
    max_stored_history: int = int(os.getenv("BIS_MAX_STORED_HISTORY", "5"))
    max_retries: int = int(os.getenv("BIS_LLM_MAX_RETRIES", "3"))
    retry_backoff_seconds: float = float(os.getenv("BIS_RETRY_BACKOFF", "1.5"))
    log_level: str = os.getenv("BIS_LOG_LEVEL", "INFO")
    cache_enabled: bool = os.getenv("BIS_CACHE_ENABLED", "true").lower() == "true"


CONFIG = Config()

logging.basicConfig(level=CONFIG.log_level, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("bis_assistant")


def validate_environment() -> None:
    """Fail fast with a clear message rather than a deep stack trace."""
    missing = [key for key in ("GOOGLE_API_KEY",) if not os.getenv(key)]
    if missing:
        console.print(
            f"[bold red]Missing required environment variable(s): {', '.join(missing)}[/bold red]\n"
            "Set them in your .env file before starting the assistant."
        )
        sys.exit(1)

    if not Path(CONFIG.db_path).exists():
        console.print(
            f"[yellow]Warning: Chroma DB path '{CONFIG.db_path}' does not exist yet. "
            "Run 'python src/ingestion/build_vectorDB.py' to populate it.[/yellow]"
        )


# --------------------------------------------------------------------------- #
# Retry helper
# --------------------------------------------------------------------------- #
T = TypeVar("T")


def with_retry(max_retries: int = CONFIG.max_retries, backoff: float = CONFIG.retry_backoff_seconds):
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt == max_retries:
                        break
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
# Schemas
# --------------------------------------------------------------------------- #
class Intent(str, Enum):
    CHAT = "chat"
    HALLMARK = "hallmark"
    REGISTRATION = "registration"
    CERTIFICATION = "certification"
    LABORATORY = "laboratory"
    MANAKONLINE = "manakonline"
    CATALOG_SEARCH = "catalog_search"


DOMAIN_COLLECTIONS = [
    Intent.HALLMARK, Intent.REGISTRATION, Intent.CERTIFICATION,
    Intent.LABORATORY, Intent.MANAKONLINE,
]


class IntentResult(BaseModel):
    intent: Intent = Field(description="The single best-matching category for the query.")


class BISResponse(BaseModel):
    """Unified schema for every intent."""
    core_response: str = Field(description="Complete, self-contained answer or explanation.")
    applicable_standards: List[str] = Field(
        default_factory=list,
        description="Relevant IS Codes with one-line descriptions. Format: 'IS XXXX - description'.",
    )
    source_citation: str = Field(
        default="",
        description="Document name, clause number, or regulatory reference.",
    )
    next_step: str = Field(
        default="",
        description="Actionable next step, portal URL, or application step.",
    )
    follow_up_prompt: str = Field(
        default="",
        description="A natural follow-up question to keep the conversation going.",
    )


# --------------------------------------------------------------------------- #
# Graph state — added cache_key field
# --------------------------------------------------------------------------- #
# Token & Usage Tracking
# --------------------------------------------------------------------------- #
class TokenTracker:
    def __init__(self) -> None:
        self.session_prompt_tokens: int = 0
        self.session_completion_tokens: int = 0
        self.session_saved_tokens: int = 0
        self.session_embedding_tokens: int = 0
        self.turn_prompt_tokens: int = 0
        self.turn_completion_tokens: int = 0
        self.turn_embedding_tokens: int = 0

    def reset_turn(self) -> None:
        self.turn_prompt_tokens = 0
        self.turn_completion_tokens = 0
        self.turn_embedding_tokens = 0

    def add_llm_usage(self, usage: Optional[dict]) -> None:
        if not usage:
            return
        inp = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        out = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        self.turn_prompt_tokens += inp
        self.turn_completion_tokens += out
        self.session_prompt_tokens += inp
        self.session_completion_tokens += out

    def add_embedding_text(self, text: str) -> None:
        if not text:
            return
        # Approx 1 token per 4 characters
        toks = max(1, len(text) // 4)
        self.turn_embedding_tokens += toks
        self.session_embedding_tokens += toks

    def record_cache_hit(self, estimated_saved: int = 750) -> None:
        self.session_saved_tokens += estimated_saved

    def get_turn_summary(self, cache_hit: bool = False) -> dict:
        p_tok = 0 if cache_hit else self.turn_prompt_tokens
        c_tok = 0 if cache_hit else self.turn_completion_tokens
        t_tok = p_tok + c_tok
        return {
            "turn_llm_tokens": t_tok,
            "turn_prompt_tokens": p_tok,
            "turn_completion_tokens": c_tok,
            "turn_embedding_tokens": self.turn_embedding_tokens,
            "session_total_llm_tokens": self.session_prompt_tokens + self.session_completion_tokens,
            "session_total_saved_tokens": self.session_saved_tokens,
            "session_embedding_tokens": self.session_embedding_tokens,
            "embedding_provider": (
                f"{CONFIG.embedding_provider.upper()} (Local ONNX - $0.00 API burn)"
                if CONFIG.embedding_provider == "fastembed"
                else f"{CONFIG.embedding_provider.upper()} API"
            ),
        }


token_tracker = TokenTracker()


# --------------------------------------------------------------------------- #
# Graph state
# --------------------------------------------------------------------------- #
class AgentState(TypedDict):
    query: str
    standalone_query: str
    chat_history: List[Tuple[str, str]]
    intent: str
    domain: str
    retrieved_context: str
    final_output: Optional[BISResponse]
    cache_key: str
    cache_hit: Optional[bool]
    token_usage: Optional[dict]


# --------------------------------------------------------------------------- #
# Component initialization
# --------------------------------------------------------------------------- #
def initialize_components():
    # provider = CONFIG.embedding_provider.lower()
    # if provider == "fastembed":
    #     from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    #     embeddings = FastEmbedEmbeddings(model_name=CONFIG.embedding_model)
    # elif provider == "google":
    #     embeddings = GoogleGenerativeAIEmbeddings(model=CONFIG.embedding_model)
    # else:
    #     embeddings = OllamaEmbeddings(model=CONFIG.embedding_model, base_url=CONFIG.embedding_base_url)
    embeddings = MistralAIEmbeddings(model=CONFIG.embedding_model)
    llm = ChatGoogleGenerativeAI(model=CONFIG.llm_model, temperature=CONFIG.llm_temperature)

    # Catalog retriever (default collection)
    catalog_retriever = Chroma(
        persist_directory=CONFIG.db_path, embedding_function=embeddings
    ).as_retriever(search_kwargs={"k": CONFIG.retriever_k})

    # Domain Chroma DBs (for hybrid retrieval) — stored as raw Chroma objects now
    domain_chromadbs: dict[str, Chroma] = {}
    for domain in DOMAIN_COLLECTIONS:
        domain_chromadbs[domain.value] = Chroma(
            collection_name=domain.value,
            persist_directory=CONFIG.db_path,
            embedding_function=embeddings,
        )

    return llm, embeddings, catalog_retriever, domain_chromadbs


llm, embeddings, catalog_retriever, domain_chromadbs = initialize_components()
structured_response_llm = llm.with_structured_output(BISResponse, include_raw=True)
structured_intent_llm = llm.with_structured_output(IntentResult, include_raw=True)

# Global cache instance
response_cache = ResponseCache()


def _format_history(chat_history: List[Tuple[str, str]]) -> str:
    if not chat_history:
        return "(no prior turns)"
    recent = list(chat_history)[-CONFIG.history_window:]
    return "\n".join(f"User: {u}\nAgent: {a}" for u, a in recent)


# --------------------------------------------------------------------------- #
# Graph nodes
# --------------------------------------------------------------------------- #
@with_retry()
def _rewrite_query(last_agent_msg: str, query: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You convert a user's short reply into a full standalone search query.\n\n"
         "The agent's last message may contain a section tagged '[I asked as follow-up]: ...' "
         "which is the exact follow-up question the agent posed to the user.\n\n"
         "Rules:\n"
         "1. If the user replies with 'yes', 'sure', 'ok', 'explain', 'tell me more', or any "
         "short affirmation — look at the '[I asked as follow-up]' section and turn THAT "
         "question into the standalone query.\n"
         "2. If the user replies with a specific answer or correction to the follow-up, "
         "incorporate that answer into the standalone query.\n"
         "3. If there is no follow-up section, use the full agent answer as context to "
         "understand what the user is referring to.\n"
         "4. Output ONLY the standalone query — no preamble, no explanation."),
        ("human", "Agent's Last Message:\n{last_agent_msg}\n\nUser's Reply: {query}"),
    ])
    msg = prompt.format_messages(last_agent_msg=last_agent_msg, query=query)
    resp = llm.invoke(msg)
    token_tracker.add_llm_usage(getattr(resp, "usage_metadata", None))
    return str(resp.content).strip()


def contextualize_query(state: AgentState) -> dict:
    """Rewrite the latest user turn into a standalone query using chat history."""
    if not state["chat_history"]:
        sq = state["query"]
    else:
        try:
            sq = _rewrite_query(state["chat_history"][-1][1], state["query"])
        except Exception as exc:  # noqa: BLE001
            logger.error("Query rewrite failed, falling back to raw query: %s", exc)
            sq = state["query"]

    return {"standalone_query": sq or state["query"]}


@with_retry()
def _classify(query: str) -> Intent:
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a highly accurate intent classification router for the Bureau of Indian Standards (BIS) AI Assistant.
Classify the user's standalone query into EXACTLY ONE of the following 7 categories:

1. chat - Greetings, thanks, who are you, general acknowledgments (hi, hello, yes, no, ok, help).
2. hallmark - Hallmark, HUID, gold, silver, jewellery, jeweler, carat, purity, AHC, assaying center.
3. registration - CRS, Compulsory Registration Scheme, electronics, IT goods, laptops, mobiles, solar panels, MeitY.
4. certification - ISI mark, FMCS, Scheme-I, QCO, Quality Control Order, factory audit, CML number, AIR, license.
5. laboratory - Laboratory, testing lab, LRS, test report, NABL, LIMS, recognized lab, calibration.
6. manakonline - Manak online, e-BIS, e-CML, portal, login, password, upload document, online application.
7. catalog_search - IS code, IS number, standard, product name (cement, pipes, steel, petroleum, water, toys, etc.).

CRITICAL: Any product name mention defaults to catalog_search."""),
        ("human", "{query}"),
    ])
    msg = prompt.format_messages(query=query)
    raw_res = structured_intent_llm.invoke(msg)
    if isinstance(raw_res, dict) and "raw" in raw_res:
        token_tracker.add_llm_usage(getattr(raw_res["raw"], "usage_metadata", None))
        parsed = raw_res.get("parsed")
        if parsed and hasattr(parsed, "intent"):
            return parsed.intent
    elif hasattr(raw_res, "intent"):
        return raw_res.intent
    return Intent.CATALOG_SEARCH


def intent_classifier(state: AgentState) -> dict:
    """Classify the standalone query into one of 7 intents."""
    try:
        intent = _classify(state["standalone_query"])
    except Exception as exc:  # noqa: BLE001
        logger.error("Intent classification failed, using fallback: %s", exc)
        intent = Intent.CHAT if len(state["standalone_query"].split()) <= 2 else Intent.CATALOG_SEARCH

    return {"intent": intent.value}


def retrieve_domain(domain: Intent):
    """
    Factory: returns a retrieval node for a domain that uses hybrid BM25 + dense + rerank.
    Falls back to dense-only if hybrid_retrieve fails.
    """
    def _node(state: AgentState) -> dict:
        chroma_db = domain_chromadbs[domain.value]
        token_tracker.add_embedding_text(state["standalone_query"])
        try:
            _, context = hybrid_retrieve(
                query=state["standalone_query"],
                chroma_db=chroma_db,
                embeddings=embeddings,
                domain=domain.value,
                dense_k=CONFIG.retriever_k,
                bm25_k=CONFIG.retriever_k,
                rerank_top_n=CONFIG.rerank_top_n,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Hybrid retrieval failed for '%s', falling back: %s", domain.value, exc)
            try:
                docs = chroma_db.as_retriever(search_kwargs={"k": CONFIG.retriever_k}).invoke(
                    state["standalone_query"]
                )
                context = "\n".join(d.page_content for d in docs) if docs else "No relevant documents found."
            except Exception:
                context = "No relevant documents found."

        token_tracker.add_embedding_text(context)
        return {"retrieved_context": context, "domain": domain.value}

    return _node


@with_retry(max_retries=2, backoff=1.0)
def _scrape(query: str) -> str:
    return scrape_bis_portal(query)


def retrieve_catalog(state: AgentState) -> dict:
    """
    IS-code / product lookups: combine live BIS portal scraping (primary)
    with local Chroma DB (supplementary).
    """
    token_tracker.add_embedding_text(state["standalone_query"])
    docs = catalog_retriever.invoke(state["standalone_query"])
    db_context = "\n".join(d.page_content for d in docs) if docs else "No local catalog entries found."

    try:
        scraped = _scrape(state["standalone_query"])
        if not scraped or not scraped.strip():
            scraped = "(scraper returned no content for this query)"
        logger.info("Scraper returned %d chars", len(scraped))
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Warning: BIS portal scrape failed ({exc}). Using local DB only.[/yellow]")
        scraped = "Live portal data unavailable."

    combined = (
        f"[LIVE PORTAL DATA]:\n{scraped}\n\n"
        f"[LOCAL KNOWLEDGE BASE]:\n{db_context}"
    )
    token_tracker.add_embedding_text(combined)
    return {"retrieved_context": combined, "domain": "catalog"}


@with_retry()
def _synthesize(chat_history: str, context: str, query: str, is_chat: bool, domain: str) -> BISResponse:
    if is_chat:
        system_prompt = (
            "You are a helpful BIS (Bureau of Indian Standards) AI Assistant. "
            "Keep the reply conversational and brief. "
            "Leave applicable_standards, source_citation, and next_step empty for greetings.\n"
            "Chat history:\n{chat_history}"
        )
    else:
        system_prompt = (
            "You are an expert BIS (Bureau of Indian Standards) AI Assistant. "
            "Answer based on the provided context first. "
            "If the context contains specific document excerpts, cite them in source_citation.\n\n"
            "RULES:\n"
            "1. applicable_standards: Always list every relevant IS code you know for the topic, "
            "formatted as 'IS XXXX - one-line description'. Never leave empty for product/domain queries.\n"
            "2. source_citation: If context has '[Source N: filename]', cite that file.\n"
            "3. next_step: Give a concrete action (URL, form name, office to contact).\n"
            "4. Be thorough — do not skip steps for procedural queries.\n\n"
            "Chat history:\n{chat_history}\n\nContext:\n{context}"
        )

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{query}")])
    msg = prompt.format_messages(chat_history=chat_history, context=context, query=query)
    raw_res = structured_response_llm.invoke(msg)
    if isinstance(raw_res, dict) and "raw" in raw_res:
        token_tracker.add_llm_usage(getattr(raw_res["raw"], "usage_metadata", None))
        parsed = raw_res.get("parsed")
        if isinstance(parsed, BISResponse):
            return parsed
    elif isinstance(raw_res, BISResponse):
        return raw_res
    return BISResponse(core_response=str(raw_res))


def synthesize_response(state: AgentState) -> dict:
    """Single node that produces the unified JSON schema for every intent."""
    is_chat = state["intent"] == Intent.CHAT.value
    
    # 1. Cache lookup: If query has been synthesized before, return immediately (0 LLM tokens)
    if CONFIG.cache_enabled and not is_chat:
        cache_key = response_cache.make_key(state["intent"], state["standalone_query"])
        cached = response_cache.get(cache_key)
        if cached:
            token_tracker.record_cache_hit(estimated_saved=750)
            result = BISResponse(**{
                k: cached[k]
                for k in BISResponse.model_fields
                if k in cached
            })
            return {
                "final_output": result,
                "cache_hit": True,
                "token_usage": token_tracker.get_turn_summary(cache_hit=True),
            }

    # 2. LLM Synthesis
    try:
        result = _synthesize(
            _format_history(state["chat_history"]),
            state.get("retrieved_context", ""),
            state["standalone_query"],
            is_chat,
            state.get("domain", ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Synthesis failed after retries: %s", exc)
        result = BISResponse(
            core_response=(
                "I wasn't able to reach the language model. Please try again in a moment."
            ),
            follow_up_prompt="Would you like to try rephrasing your question?",
        )

    # Store in cache after successful synthesis (non-chat only),
    # keyed on standalone_query so follow-up answers don't collide.
    if CONFIG.cache_enabled and not is_chat and result:
        try:
            cache_key = response_cache.make_key(state["intent"], state["standalone_query"])
            payload = {"intent": state["intent"], "domain": state.get("domain", ""), **result.model_dump()}
            response_cache.set(cache_key, payload)
        except Exception:
            pass

    return {
        "final_output": result,
        "cache_hit": False,
        "token_usage": token_tracker.get_turn_summary(cache_hit=False),
    }


# --------------------------------------------------------------------------- #
# Build the graph
# --------------------------------------------------------------------------- #
def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("contextualize_query", contextualize_query)
    workflow.add_node("intent_classifier", intent_classifier)
    workflow.add_node("retrieve_catalog", retrieve_catalog)
    workflow.add_node("synthesize_response", synthesize_response)

    for domain in DOMAIN_COLLECTIONS:
        workflow.add_node(domain.value, retrieve_domain(domain))
        workflow.add_edge(domain.value, "synthesize_response")

    workflow.add_edge(START, "contextualize_query")
    workflow.add_edge("contextualize_query", "intent_classifier")

    routes = {domain.value: domain.value for domain in DOMAIN_COLLECTIONS}
    routes[Intent.CATALOG_SEARCH.value] = "retrieve_catalog"
    routes[Intent.CHAT.value] = "synthesize_response"

    workflow.add_conditional_edges("intent_classifier", lambda s: s["intent"], routes)

    workflow.add_edge("retrieve_catalog", "synthesize_response")
    workflow.add_edge("synthesize_response", END)

    return workflow.compile()


app = build_graph()


# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
@dataclass
class Session:
    history: Deque[Tuple[str, str]] = field(
        default_factory=lambda: deque(maxlen=CONFIG.max_stored_history)
    )

    def run_turn(self, user_query: str) -> dict:
        token_tracker.reset_turn()
        # Full graph run — cache check happens INSIDE synthesize_response node
        # using the standalone_query (after contextualization), not the raw input.
        # This prevents short follow-up words like "yes" from incorrectly hitting
        # stale cache entries.
        inputs: AgentState = {
            "query": user_query,
            "standalone_query": "",
            "chat_history": list(self.history),
            "intent": "",
            "domain": "",
            "retrieved_context": "",
            "final_output": None,
            "cache_key": "",   # will be set by synthesize_response after contextualization
            "cache_hit": None,
            "token_usage": None,
        }
        state = app.invoke(inputs)
        output: BISResponse = state["final_output"]
        # Store core_response + follow_up_prompt so that when user answers the
        # follow-up (e.g. "yes"), _rewrite_query can see exactly what was asked.
        agent_stored = output.core_response
        if output.follow_up_prompt:
            agent_stored += f"\n\n[I asked as follow-up]: {output.follow_up_prompt}"
        self.history.append((user_query, agent_stored))
        return state

    @staticmethod
    def to_json(state: dict) -> dict:
        output: BISResponse = state["final_output"]
        return {
            "intent": state.get("intent", ""),
            "domain": state.get("domain", ""),
            "cache_hit": state.get("cache_hit", False),
            **output.model_dump(),
            "token_usage": state.get("token_usage", token_tracker.get_turn_summary(state.get("cache_hit", False))),
        }


# --------------------------------------------------------------------------- #
# CLI / voice execution loop
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BIS Agentic RAG Assistant")
    parser.add_argument(
        "--mode", choices=["auto", "text"], default="auto",
        help="'auto' allows empty-input voice capture; 'text' disables voice.",
    )
    parser.add_argument(
        "--clear-cache", action="store_true",
        help="Clear the response cache before starting.",
    )
    return parser.parse_args()


def main() -> None:
    validate_environment()
    args = parse_args()

    if args.clear_cache:
        response_cache.clear()
        console.print("[yellow]Response cache cleared.[/yellow]")

    console.print(Panel.fit(
        "[bold green]BIS Agentic RAG Assistant[/bold green]\n"
        f"[dim]Cache: {'ON' if CONFIG.cache_enabled else 'OFF'} | "
        f"Retrieval: Hybrid BM25+Dense (rerank top-{CONFIG.rerank_top_n})[/dim]",
        border_style="green",
    ))

    audio_handler = None
    if args.mode == "auto":
        from tools.audio_handler import LocalAudioHandler
        audio_handler = LocalAudioHandler(model_size="base")
    else:
        console.print("[dim]Voice input disabled (--mode text).[/dim]")

    session = Session()

    while True:
        try:
            console.print("\n[bold cyan]YOU : > [/bold cyan]", end="")
            user_input = input().strip()

            if user_input == "":
                if audio_handler is None:
                    console.print("[yellow]Voice input is disabled. Type your question.[/yellow]")
                    continue
                audio_file = audio_handler.record_audio()
                user_query = audio_handler.transcribe(audio_file)
                if not user_query:
                    console.print("[yellow]Could not hear any speech. Try again.[/yellow]")
                    continue
                console.print(f"[bold magenta]Transcribed:[/bold magenta] {user_query}")
            else:
                user_query = user_input

            if user_query.lower() in {"exit", "quit", "q"}:
                break

            with console.status("[cyan]Thinking...[/cyan]", spinner="dots"):
                state = session.run_turn(user_query)

            payload = Session.to_json(state)
            title = f"BIS Assistant ({payload['intent']})"
            if payload.get("cache_hit"):
                title += " [CACHE]"
            console.print(Panel(
                json.dumps(payload, indent=2, ensure_ascii=False),
                title=title,
                border_style="cyan",
            ))

            # Awareness banner for Token Usage & Cost Savings
            tu = payload.get("token_usage", {})
            if tu:
                turn_llm = tu.get("turn_llm_tokens", 0)
                p_tok = tu.get("turn_prompt_tokens", 0)
                c_tok = tu.get("turn_completion_tokens", 0)
                s_llm = tu.get("session_total_llm_tokens", 0)
                e_tok = tu.get("turn_embedding_tokens", 0)
                provider = tu.get("embedding_provider", "")
                saved = tu.get("session_total_saved_tokens", 0)
                cache_badge = " [bold green]🎉 Cache Hit (0 Tokens Burned)![/bold green]" if payload.get("cache_hit") else ""

                console.print(
                    f"⚡ [bold cyan]Tokens:[/bold cyan] "
                    f"Turn: [bold green]{turn_llm}[/bold green] (In: {p_tok}, Out: {c_tok}) | "
                    f"Session Total: [bold magenta]{s_llm}[/bold magenta] | "
                    f"Embedding: [dim]{e_tok} tokens ({provider})[/dim] | "
                    f"Saved: [green]{saved} tokens[/green]{cache_badge}"
                )

        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting...[/yellow]")
            sys.exit(0)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error in main loop")
            console.print(f"[red]Error: {exc}[/red]")


if __name__ == "__main__":
    main()