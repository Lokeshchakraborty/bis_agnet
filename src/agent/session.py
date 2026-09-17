"""
Conversational Session Management & Cache Bypass for BIS Agent.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Tuple,Optional

from src.agent.graph import build_graph
from src.agent.nodes import _fast_classify, _format_history, _is_research_query
from src.config import CONFIG
from src.schemas import DOMAIN_COLLECTIONS, AgentState, BISResponse, Intent, TokenTracker
from src.tools.cache import ResponseCache

from src.tools.audit import get_audit_logger

logger = logging.getLogger("bis_session")


MAX_SESSION_TURNS = 50
MAX_SESSION_TOKENS = 50000


class SessionRateLimitException(Exception):
    """Raised when a session exceeds maximum turn or token consumption caps."""
    def __init__(self, message: str, error_code: str = "RATE_LIMIT_EXCEEDED"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


@dataclass
class Session:
    """Manages multi-turn conversation session, history tracking, product context, and audit execution."""

    response_cache: ResponseCache = field(default_factory=ResponseCache)
    token_tracker: TokenTracker = field(default_factory=TokenTracker)
    active_product_context: str = ""
    turn_count: int = 0
    history: Deque[Tuple[str, str]] = field(
        default_factory=lambda: deque(maxlen=CONFIG.max_stored_history)
    )

    def __post_init__(self):
        self.app, self.nodes = build_graph(
            token_tracker=self.token_tracker,
            response_cache=self.response_cache,
        )

    def run_turn(
        self,
        user_query: str,
        session_id: str = "default",
        user_id: str = "default_user",
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None,
    ) -> dict:
        """Run a single conversation turn with front-loaded cache bypass, rate limiting, and Supabase sync."""
        import time
        start_t = time.perf_counter()
        self.token_tracker.reset_turn()

        # Enforce hard rate limiting & token cost telemetry caps per session
        self.turn_count += 1
        if self.turn_count > MAX_SESSION_TURNS:
            raise SessionRateLimitException(
                f"Session turn cap exceeded (limit: {MAX_SESSION_TURNS} turns). Please initialize a new session.",
                error_code="SESSION_TURN_CAP_EXCEEDED"
            )

        total_tokens = self.token_tracker.session_prompt_tokens + self.token_tracker.session_completion_tokens
        if total_tokens > MAX_SESSION_TOKENS:
            raise SessionRateLimitException(
                f"Session token cost cap exceeded (limit: {MAX_SESSION_TOKENS} tokens). Please initialize a new session.",
                error_code="SESSION_TOKEN_CAP_EXCEEDED"
            )

        # Context Memory: pre-append active product context for short follow-ups
        effective_query = user_query
        if self.active_product_context and len(user_query.split()) <= 4:
            effective_query = f"{user_query} (Product Context: {self.active_product_context})"

        # Helper to sync session state to Supabase
        def _sync_to_supabase():
            try:
                import asyncio
                from backend.db.supabase_client import save_session_to_supabase
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        save_session_to_supabase(
                            session_id=session_id,
                            user_id=user_id,
                            active_product_context=self.active_product_context,
                            turn_count=self.turn_count,
                            history=list(self.history),
                        )
                    )
                except RuntimeError:
                    pass
            except Exception as exc:
                logger.debug("Failed to schedule Supabase session save: %s", exc)


        is_research = _is_research_query(user_query) or _is_research_query(effective_query)

        # 1. Front-Loaded Cache Check: 0 LLM calls, 0 token burn (bypassed for deep research mode)
        if CONFIG.cache_enabled and not is_research:
            fast_intent = _fast_classify(user_query)
            intents_to_check = (
                [fast_intent.value]
                if fast_intent
                else [d.value for d in DOMAIN_COLLECTIONS] + [Intent.CATALOG_SEARCH.value]
            )
            for intent_str in intents_to_check:
                key = self.response_cache.make_key(intent_str, user_query, user_id=user_id)
                cached = self.response_cache.get(key)

                if cached:
                    self.token_tracker.record_cache_hit(estimated_saved=750)
                    output = BISResponse(**{k: cached[k] for k in BISResponse.model_fields if k in cached})
                    self.history.append((user_query, output.core_response))
                    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
                    elapsed_sec = round(time.perf_counter() - start_t, 3)
                    tu = self.token_tracker.get_turn_summary(cache_hit=True)
                    tu["response_time_ms"] = elapsed_ms
                    tu["response_time_seconds"] = elapsed_sec
                    res_state = {
                        "query": user_query,
                        "standalone_query": effective_query,
                        "chat_history": list(self.history),
                        "intent": cached.get("intent", intent_str),
                        "domain": cached.get("domain", intent_str),
                        "retrieved_context": "",
                        "final_output": output,
                        "cache_key": key,
                        "cache_hit": True,
                        "response_time_ms": elapsed_ms,
                        "response_time_seconds": elapsed_sec,
                        "token_usage": tu,
                        "llm_provider": llm_provider,
                        "llm_model": llm_model,
                        "llm_api_key": llm_api_key,
                        "llm_base_url": llm_base_url,
                        "is_research": is_research,
                    }
                    get_audit_logger().log_interaction(
                        session_id=session_id,
                        user_query=user_query,
                        standalone_query=effective_query,
                        intent=res_state["intent"],
                        intent_localized=output.intent_localized,
                        payload_dict=self.to_json(res_state),
                        token_usage=tu,
                        response_time_ms=elapsed_ms,
                        user_id=user_id,
                    )
                    _sync_to_supabase()
                    return res_state

        # 2. Graph execution
        inputs: AgentState = {
            "query": effective_query,
            "standalone_query": effective_query,
            "chat_history": list(self.history),
            "intent": "",
            "domain": "",
            "retrieved_context": "",
            "final_output": None,
            "cache_key": "",
            "cache_hit": None,
            "token_usage": None,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key": llm_api_key,
            "llm_base_url": llm_base_url,
            "is_research": is_research,
            "user_id": user_id,
        }
        state = self.app.invoke(inputs)
        output: BISResponse = state["final_output"]
        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
        elapsed_sec = round(time.perf_counter() - start_t, 3)
        state["response_time_ms"] = elapsed_ms
        state["response_time_seconds"] = elapsed_sec
        if state.get("token_usage"):
            state["token_usage"]["response_time_ms"] = elapsed_ms
            state["token_usage"]["response_time_seconds"] = elapsed_sec

        # Update product context memory if applicable standards were cited
        if output.applicable_standards:
            self.active_product_context = output.applicable_standards[0]

        # Store context with follow-up prompt tag for accurate multi-turn resolution
        agent_stored = output.core_response
        if output.follow_up_prompt:
            agent_stored += f"\n\n[I asked as follow-up]: {output.follow_up_prompt}"
        self.history.append((user_query, agent_stored))

        # Log interaction to immutable audit ledger
        get_audit_logger().log_interaction(
            session_id=session_id,
            user_query=user_query,
            standalone_query=state.get("standalone_query", effective_query),
            intent=state.get("intent", ""),
            intent_localized=output.intent_localized,
            payload_dict=self.to_json(state),
            token_usage=state.get("token_usage"),
            response_time_ms=elapsed_ms,
            user_id=user_id,
        )


        _sync_to_supabase()
        return state

    async def run_turn_stream(
        self,
        user_query: str,
        session_id: str = "default",
        user_id: str = "default_user",
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None,
    ):
        """Stream real-time state updates directly from Python backend execution steps to client."""
        import asyncio
        import time
        start_t = time.perf_counter()
        self.token_tracker.reset_turn()

        self.turn_count += 1
        if self.turn_count > MAX_SESSION_TURNS:
            yield {"type": "error", "message": "Session turn cap exceeded."}
            return

        effective_query = user_query
        if self.active_product_context and len(user_query.split()) <= 4:
            effective_query = f"{user_query} (Product Context: {self.active_product_context})"

        is_research = _is_research_query(user_query) or _is_research_query(effective_query)

        if is_research:
            yield {"type": "status", "message": "Initiating deep regulatory compliance & standards research..."}
        else:
            yield {"type": "status", "message": "Classifying intent & IS standard codes..."}

        # 1. Front-Loaded Cache Check (bypassed for deep research queries)
        if CONFIG.cache_enabled and not is_research:
            yield {"type": "status", "message": "Checking 0-Token instant response cache..."}
            fast_intent = _fast_classify(user_query)
            intents_to_check = (
                [fast_intent.value]
                if fast_intent
                else [d.value for d in DOMAIN_COLLECTIONS] + [Intent.CATALOG_SEARCH.value]
            )
            for intent_str in intents_to_check:
                key = self.response_cache.make_key(intent_str, user_query, user_id=user_id)
                cached = self.response_cache.get(key)

                if cached:
                    yield {"type": "status", "message": "Instant 0-Token cache hit!"}
                    self.token_tracker.record_cache_hit(estimated_saved=750)
                    output = BISResponse(**{k: cached[k] for k in BISResponse.model_fields if k in cached})
                    self.history.append((user_query, output.core_response))
                    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
                    elapsed_sec = round(time.perf_counter() - start_t, 3)
                    tu = self.token_tracker.get_turn_summary(cache_hit=True)
                    tu["response_time_ms"] = elapsed_ms
                    tu["response_time_seconds"] = elapsed_sec
                    res_state = {
                        "query": user_query,
                        "standalone_query": effective_query,
                        "chat_history": list(self.history),
                        "intent": cached.get("intent", intent_str),
                        "domain": cached.get("domain", intent_str),
                        "retrieved_context": "",
                        "final_output": output,
                        "cache_key": key,
                        "cache_hit": True,
                        "response_time_ms": elapsed_ms,
                        "response_time_seconds": elapsed_sec,
                        "token_usage": tu,
                        "llm_provider": llm_provider,
                        "llm_model": llm_model,
                        "llm_api_key": llm_api_key,
                        "llm_base_url": llm_base_url,
                        "is_research": is_research,
                    }
                    get_audit_logger().log_interaction(
                        session_id=session_id,
                        user_query=user_query,
                        standalone_query=effective_query,
                        intent=res_state["intent"],
                        intent_localized=output.intent_localized,
                        payload_dict=self.to_json(res_state),
                        token_usage=tu,
                        response_time_ms=elapsed_ms,
                        user_id=user_id,
                    )
                    from backend.db.supabase_client import save_session_to_supabase
                    await save_session_to_supabase(
                        session_id=session_id,
                        user_id=user_id,
                        active_product_context=self.active_product_context,
                        turn_count=self.turn_count,
                        history=list(self.history),
                    )
                    yield {"type": "result", "payload": self.to_json(res_state)}
                    return

        # 2. Contextualize Query
        yield {"type": "status", "message": "Contextualizing query with active session..."}
        inputs: AgentState = {
            "query": effective_query,
            "standalone_query": effective_query,
            "chat_history": list(self.history),
            "intent": "",
            "domain": "",
            "retrieved_context": "",
            "final_output": None,
            "cache_key": "",
            "cache_hit": None,
            "token_usage": None,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key": llm_api_key,
            "llm_base_url": llm_base_url,
            "is_research": is_research,
            "user_id": user_id,
        }
        state = dict(inputs)
        state.update(self.nodes.contextualize_query(state))

        # 3. Intent Classification
        yield {"type": "status", "message": "Classifying compliance intent & IS categories..."}
        intent_res = self.nodes.intent_classifier(state)
        state.update(intent_res)

        # 4. Dense & BM25 Knowledge Retrieval
        intent_val = state.get("intent", "general")
        yield {"type": "status", "message": f"Retrieving Indian Standards & clauses for {intent_val}..."}
        if intent_val == Intent.CATALOG_SEARCH.value:
            ret_res = self.nodes.retrieve_catalog(state)
        elif intent_val in [d.value for d in DOMAIN_COLLECTIONS]:
            domain_obj = [d for d in DOMAIN_COLLECTIONS if d.value == intent_val][0]
            ret_fn = self.nodes.retrieve_domain(domain_obj)
            ret_res = ret_fn(state)
        else:
            ret_res = {"retrieved_context": "", "domain": "chat"}
        state.update(ret_res)

        # 5. LLM Synthesis with Real-Time Token Streaming
        if is_research:
            yield {"type": "status", "message": "Synthesizing 13-section technical compliance research dossier..."}
        else:
            yield {"type": "status", "message": "Synthesizing compliance report with IS standards..."}
        is_chat = state["intent"] == Intent.CHAT.value
        final_output = None
        for evt in self.nodes.stream_synthesize(
            chat_history=_format_history(state["chat_history"], condensed=True),
            context=state.get("retrieved_context", ""),
            query=state["standalone_query"],
            is_chat=is_chat,
            state=state,
        ):
            if evt["type"] == "token":
                yield evt
            elif evt["type"] == "final_output":
                final_output = evt["output"]

        if final_output is None:
            final_output = BISResponse(
                core_response="I encountered an issue synthesizing the response. Please try again.",
                follow_up_prompt="Would you like to rephrase your query?",
            )

        # 6. Apply Guardrails & Sanitize
        try:
            from src.agent.guardrails import validate_and_sanitize_response
            raw_conf = 0.95 if is_chat or len(state.get("retrieved_context", "")) > 50 else 0.65
            final_output = validate_and_sanitize_response(
                final_output,
                state["query"],
                intent_confidence=raw_conf,
                standalone_query=state.get("standalone_query"),
            )
        except Exception as exc:
            logger.warning("Guardrails warning during stream: %s", exc)

        state["final_output"] = final_output
        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
        elapsed_sec = round(time.perf_counter() - start_t, 3)
        state["response_time_ms"] = elapsed_ms
        state["response_time_seconds"] = elapsed_sec
        tu = self.token_tracker.get_turn_summary(cache_hit=False)
        tu["response_time_ms"] = elapsed_ms
        tu["response_time_seconds"] = elapsed_sec
        state["token_usage"] = tu

        # 7. Store in Cache if appropriate
        if CONFIG.cache_enabled and not is_chat and final_output:
            try:
                payload = {"intent": state["intent"], "domain": state.get("domain", ""), **final_output.model_dump()}
                uid = user_id or "default_user"
                key_standalone = self.response_cache.make_key(state["intent"], state["standalone_query"], user_id=uid)
                self.response_cache.set(key_standalone, payload)
                raw_q = state.get("query", "").strip()
                if raw_q and len(raw_q.split()) >= 3:
                    key_raw = self.response_cache.make_key(state["intent"], raw_q, user_id=uid)
                    self.response_cache.set(key_raw, payload)
            except Exception:
                pass

        if final_output.applicable_standards:
            self.active_product_context = final_output.applicable_standards[0]

        agent_stored = final_output.core_response
        if final_output.follow_up_prompt:
            agent_stored += f"\n\n[I asked as follow-up]: {final_output.follow_up_prompt}"
        self.history.append((user_query, agent_stored))

        get_audit_logger().log_interaction(
            session_id=session_id,
            user_query=user_query,
            standalone_query=state.get("standalone_query", effective_query),
            intent=state.get("intent", ""),
            intent_localized=final_output.intent_localized,
            payload_dict=self.to_json(state),
            token_usage=state.get("token_usage"),
            response_time_ms=elapsed_ms,
            user_id=user_id,
        )

        from backend.db.supabase_client import save_session_to_supabase, record_token_burn_for_user_in_supabase
        burned = (tu.get("turn_prompt_tokens", 0) + tu.get("turn_completion_tokens", 0)) or tu.get("total_tokens", 0) or tu.get("session_total_llm_tokens", 0)
        if burned > 0 and user_id and user_id != "default_user":
            await record_token_burn_for_user_in_supabase(user_id, burned)

        await save_session_to_supabase(
            session_id=session_id,
            user_id=user_id,
            active_product_context=self.active_product_context,
            turn_count=self.turn_count,
            history=list(self.history),
        )

        yield {"type": "result", "payload": self.to_json(state)}




    def to_json(self, state: dict) -> Dict:
        """Format state output into user-facing JSON payload."""
        output: BISResponse = state["final_output"]
        llm_prov = (
            "Google Gemini API" if "gemini" in CONFIG.llm_model.lower()
            else "Mistral AI API" if "mistral" in CONFIG.llm_model.lower()
            else "Ollama Local" if "ollama" in CONFIG.llm_model.lower()
            else "LLM API"
        )
        tu = state.get(
            "token_usage",
            self.token_tracker.get_turn_summary(state.get("cache_hit", False)),
        )
        if "response_time_ms" not in tu and "response_time_ms" in state:
            tu["response_time_ms"] = state["response_time_ms"]
            tu["response_time_seconds"] = state.get("response_time_seconds", 0.0)

        return {
            "intent": state.get("intent", ""),
            "domain": state.get("domain", ""),
            "llm_provider": llm_prov,
            "llm_model": CONFIG.llm_model,
            "response_time_ms": state.get("response_time_ms", 0.0),
            "response_time_seconds": state.get("response_time_seconds", 0.0),
            "cache_hit": state.get("cache_hit", False),
            "active_product_context": self.active_product_context,
            **output.model_dump(),
            "token_usage": tu,
        }
