"""
Conversational Session Management & Cache Bypass for BIS Agent.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Tuple

from src.agent.graph import build_graph
from src.agent.nodes import _fast_classify
from src.config import CONFIG
from src.schemas import DOMAIN_COLLECTIONS, AgentState, BISResponse, Intent, TokenTracker
from src.tools.cache import ResponseCache

logger = logging.getLogger("bis_session")


@dataclass
class Session:
    """Manages multi-turn conversation session, history tracking, and cache execution."""

    response_cache: ResponseCache = field(default_factory=ResponseCache)
    token_tracker: TokenTracker = field(default_factory=TokenTracker)
    history: Deque[Tuple[str, str]] = field(
        default_factory=lambda: deque(maxlen=CONFIG.max_stored_history)
    )

    def __post_init__(self):
        self.app, self.nodes = build_graph(
            token_tracker=self.token_tracker,
            response_cache=self.response_cache,
        )

    def run_turn(self, user_query: str) -> dict:
        """Run a single conversation turn with front-loaded cache bypass."""
        self.token_tracker.reset_turn()

        # 1. Front-Loaded Cache Check: 0 LLM calls, 0 token burn
        if CONFIG.cache_enabled:
            fast_intent = _fast_classify(user_query)
            intents_to_check = (
                [fast_intent.value]
                if fast_intent
                else [d.value for d in DOMAIN_COLLECTIONS] + [Intent.CATALOG_SEARCH.value]
            )
            for intent_str in intents_to_check:
                key = self.response_cache.make_key(intent_str, user_query)
                cached = self.response_cache.get(key)
                if cached:
                    self.token_tracker.record_cache_hit(estimated_saved=750)
                    output = BISResponse(**{k: cached[k] for k in BISResponse.model_fields if k in cached})
                    self.history.append((user_query, output.core_response))
                    return {
                        "query": user_query,
                        "standalone_query": user_query,
                        "chat_history": list(self.history),
                        "intent": cached.get("intent", intent_str),
                        "domain": cached.get("domain", intent_str),
                        "retrieved_context": "",
                        "final_output": output,
                        "cache_key": key,
                        "cache_hit": True,
                        "token_usage": self.token_tracker.get_turn_summary(cache_hit=True),
                    }

        # 2. Graph execution
        inputs: AgentState = {
            "query": user_query,
            "standalone_query": "",
            "chat_history": list(self.history),
            "intent": "",
            "domain": "",
            "retrieved_context": "",
            "final_output": None,
            "cache_key": "",
            "cache_hit": None,
            "token_usage": None,
        }
        state = self.app.invoke(inputs)
        output: BISResponse = state["final_output"]

        # Store context with follow-up prompt tag for accurate multi-turn resolution
        agent_stored = output.core_response
        if output.follow_up_prompt:
            agent_stored += f"\n\n[I asked as follow-up]: {output.follow_up_prompt}"
        self.history.append((user_query, agent_stored))
        return state

    def to_json(self, state: dict) -> Dict:
        """Format state output into user-facing JSON payload."""
        output: BISResponse = state["final_output"]
        return {
            "intent": state.get("intent", ""),
            "domain": state.get("domain", ""),
            "cache_hit": state.get("cache_hit", False),
            **output.model_dump(),
            "token_usage": state.get(
                "token_usage",
                self.token_tracker.get_turn_summary(state.get("cache_hit", False)),
            ),
        }
