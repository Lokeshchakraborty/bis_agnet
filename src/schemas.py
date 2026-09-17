"""
Pydantic Schemas, Enums, State Definitions, and Token Tracker for BIS Agent.
"""
from __future__ import annotations

import uuid
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


class ComplianceMetadata(BaseModel):
    """Granular regulatory and compliance parameters for manufacturers and applicants."""
    foreign_manufacturer_requires_air: Optional[bool] = Field(
        default=None,
        description="Whether an Authorized Indian Representative (AIR) is mandatory for foreign manufacturers.",
    )
    testing_location: Optional[str] = Field(
        default="",
        description="Required testing facility type (e.g., 'BIS-accredited domestic laboratory', 'In-house lab').",
    )
    certificate_validity_years: Optional[int] = Field(
        default=2,
        description="Standard validity period of the BIS license/certificate in years.",
    )
    digital_qr_manual_allowed: Optional[bool] = Field(
        default=None,
        description="Whether digital/QR-code-based manuals are permitted per recent amendments (e.g., IS 16333 Part 3:2022 Amendment No. 1).",
    )
    amendments_applicable: List[str] = Field(
        default_factory=list,
        description="Applicable regulatory amendments (e.g., ['Amendment No. 1 to IS 16333 (Part 3):2022']).",
    )


class ConfidenceMetrics(BaseModel):
    """Confidence scoring and clarification triggers for compliance queries."""
    intent_confidence: float = Field(
        default=0.95,
        description="Confidence score for intent classification and standard matching (0.0 to 1.0).",
    )
    standard_matched: bool = Field(
        default=True,
        description="Whether a specific IS standard or policy domain was accurately matched.",
    )
    requires_human_clarification: bool = Field(
        default=False,
        description="True if query is ambiguous (confidence < 0.75) and requires user clarification.",
    )


class AuditMetadata(BaseModel):
    """Immutable audit trail metadata for compliance defensibility."""
    interaction_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique interaction UUID for legal audit trailing.",
    )
    model_checkpoint: str = Field(
        default="",
        description="Active LLM model checkpoint ID.",
    )
    prompt_sha256: str = Field(
        default="",
        description="SHA-256 hash digest of the input user prompt.",
    )
    timestamp_utc: str = Field(
        default="",
        description="ISO 8601 UTC timestamp of interaction.",
    )
    retrieved_source_count: int = Field(
        default=0,
        description="Number of retrieved citations and knowledge base documents.",
    )


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
        description="Actionable next step, portal URL, or application step matching user script/language.",
    )
    follow_up_prompt: str = Field(
        default="",
        description="A natural follow-up question in user script/language to keep conversation going.",
    )
    intent_localized: str = Field(
        default="",
        description="Localized category name matching user script/language (e.g., 'मानक खोज', 'Hallmark Registration').",
    )
    compliance_metadata: ComplianceMetadata = Field(
        default_factory=ComplianceMetadata,
        description="Granular regulatory, lab, AIR, and amendment compliance metadata.",
    )
    confidence_metrics: ConfidenceMetrics = Field(
        default_factory=ConfidenceMetrics,
        description="Intent confidence scores and clarification triggers.",
    )
    audit_metadata: AuditMetadata = Field(
        default_factory=AuditMetadata,
        description="Immutable audit ledger metadata for regulatory compliance.",
    )


# --------------------------------------------------------------------------- #
# Standardized Error Schemas
# --------------------------------------------------------------------------- #
class APIErrorPayload(BaseModel):
    """Standardized production fallback error payload."""
    status: str = Field(default="error", description="Response status ('error').")
    error_code: str = Field(..., description="Machine-readable error code (e.g. PORTAL_TIMEOUT, RATE_LIMIT_EXCEEDED).")
    message: str = Field(..., description="Human-readable error description.")
    suggested_action: str = Field(default="", description="Recommended action for client or user.")
    session_id: str = Field(default="", description="Active session ID.")
    response_time_ms: float = Field(default=0.0, description="Turn duration before failure in milliseconds.")


# --------------------------------------------------------------------------- #
# Agent State Schema (LangGraph Workflow State)
# --------------------------------------------------------------------------- #
class AgentState(TypedDict, total=False):
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
    llm_provider: Optional[str]
    llm_model: Optional[str]
    llm_api_key: Optional[str]
    llm_base_url: Optional[str]
    is_research: Optional[bool]
    user_id: Optional[str]


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
        llm_prov = (
            "Google Gemini API" if "gemini" in CONFIG.llm_model.lower()
            else "Mistral AI API" if "mistral" in CONFIG.llm_model.lower()
            else "Ollama Local" if "ollama" in CONFIG.llm_model.lower()
            else "LLM API"
        )
        return {
            "llm_provider": llm_prov,
            "llm_model": CONFIG.llm_model,
            "turn_llm_tokens": t_tok,
            "total_tokens": t_tok,
            "turn_prompt_tokens": p_tok,
            "prompt_tokens": p_tok,
            "turn_completion_tokens": c_tok,
            "completion_tokens": c_tok,
            "turn_embedding_tokens": self.turn_embedding_tokens,
            "session_total_llm_tokens": self.session_prompt_tokens + self.session_completion_tokens,
            "session_total_saved_tokens": self.session_saved_tokens,
            "estimated_saved_tokens": self.session_saved_tokens,
            "session_embedding_tokens": self.session_embedding_tokens,
            "embedding_provider": (
                f"{CONFIG.embedding_provider.upper()} (Local ONNX - $0.00 API cost)"
                if CONFIG.embedding_provider.lower() == "fastembed"
                else f"{CONFIG.embedding_provider.upper()} API"
            ),
        }
