"""
Pydantic Schemas, Enums, State Definitions, and Token Tracker for BIS Agent.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple, TypedDict

from pydantic import BaseModel, Field

from src.config import CONFIG


# --------------------------------------------------------------------------- #
# Intents
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
    Intent.HALLMARK,
    Intent.REGISTRATION,
    Intent.CERTIFICATION,
    Intent.LABORATORY,
    Intent.MANAKONLINE,
]


# --------------------------------------------------------------------------- #
# Pydantic Schemas
# --------------------------------------------------------------------------- #
class IntentResult(BaseModel):
    intent: Intent = Field(description="The single best-matching category for the query.")


class BISResponse(BaseModel):
    """Unified schema for every intent response."""
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
# Agent State
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
# Token & Usage Tracking
# --------------------------------------------------------------------------- #
class TokenTracker:
    """Tracks token usage across conversation turns and estimates savings from caching."""

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
        # Rough estimation: 1 token per 4 chars
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
                f"{CONFIG.embedding_provider.upper()} (Local ONNX - $0.00 API cost)"
                if CONFIG.embedding_provider.lower() == "fastembed"
                else f"{CONFIG.embedding_provider.upper()} API"
            ),
        }
