"""
BIS Agentic RAG Assistant - FastAPI REST API
==============================================
Exposes high-performance REST endpoints for text queries, voice audio processing,
session management, and response cache control.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Path as APIPath, UploadFile, Form, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from fastapi.responses import JSONResponse
from src.agent.session import Session, SessionRateLimitException
from src.config import CONFIG, validate_environment
from src.schemas import BISResponse, ComplianceMetadata, ConfidenceMetrics, AuditMetadata, APIErrorPayload
from src.tools.cache import ResponseCache

logger = logging.getLogger("bis_api")

# --------------------------------------------------------------------------- #
# In-Memory Session Manager
# --------------------------------------------------------------------------- #
class SessionManager:
    """Manages active conversation sessions mapped by session ID."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def get_session(self, session_id: str) -> Session:
        """Retrieve existing session or create a new one."""
        if session_id not in self._sessions:
            logger.info("Initializing new session: %s", session_id)
            self._sessions[session_id] = Session()
        return self._sessions[session_id]

    def list_sessions(self) -> List[Dict]:
        """Summarize active session states."""
        summaries = []
        for sid, sess in self._sessions.items():
            summaries.append({
                "session_id": sid,
                "history_turns": len(sess.history),
                "last_query": sess.history[-1][0] if sess.history else None,
            })
        return summaries

    def delete_session(self, session_id: str) -> bool:
        """Remove a session from memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Deleted session: %s", session_id)
            return True
        return False

    def clear_all(self) -> None:
        """Clear all active sessions."""
        self._sessions.clear()


session_manager = SessionManager()
_audio_handler = None


def get_audio_handler():
    """Lazy initialization of LocalAudioHandler for voice endpoint."""
    global _audio_handler
    if _audio_handler is None:
        from src.audio.handler import LocalAudioHandler
        _audio_handler = LocalAudioHandler(model_size="base")
    return _audio_handler


# --------------------------------------------------------------------------- #
# Pydantic Schemas for API Requests & Responses
# --------------------------------------------------------------------------- #
from pydantic import BaseModel, Field, model_validator
from typing import Any, Dict, List, Optional

class QueryRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="User question or prompt for the BIS Agent.")
    prompt: Optional[str] = Field(default=None, description="Alternative key for user query.")
    text: Optional[str] = Field(default=None, description="Alternative key for user text.")
    question: Optional[str] = Field(default=None, description="Alternative key for question.")
    session_id: str = Field(default="default", description="Unique conversation session identifier.")

    @model_validator(mode="before")
    @classmethod
    def check_query_or_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            q = data.get("query") or data.get("prompt") or data.get("text") or data.get("question") or ""
            if not str(q).strip():
                raise ValueError("Query text must not be empty. Pass 'query' or 'prompt' field.")
            data["query"] = str(q).strip()
        return data

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "What is the procedure for getting a Gold Hallmarking license under BIS?",
                "session_id": "user-123"
            }
        }
    }


class TokenUsageSummary(BaseModel):
    llm_provider: str = Field(default="", description="Name of LLM provider.")
    llm_model: str = Field(default="", description="LLM model identifier.")
    response_time_ms: float = Field(default=0.0, description="Response latency in milliseconds.")
    response_time_seconds: float = Field(default=0.0, description="Response latency in seconds.")
    turn_llm_tokens: int = 0
    turn_prompt_tokens: int = 0
    turn_completion_tokens: int = 0
    turn_embedding_tokens: int = 0
    session_total_llm_tokens: int = 0
    session_total_saved_tokens: int = 0
    session_embedding_tokens: int = 0
    embedding_provider: str = ""


class QueryResponse(BaseModel):
    session_id: str = Field(..., description="Active session ID.")
    query: str = Field(..., description="The processed user query.")
    intent: str = Field(..., description="Detected intent category.")
    domain: str = Field(..., description="Identified domain category.")
    intent_localized: str = Field(default="", description="Localized category name matching user script/language.")
    llm_provider: str = Field(default="", description="The LLM model provider name.")
    llm_model: str = Field(default="", description="The LLM model identifier.")
    response_time_ms: float = Field(default=0.0, description="Turn execution time in milliseconds.")
    response_time_seconds: float = Field(default=0.0, description="Turn execution time in seconds.")
    core_response: str = Field(..., description="Detailed answer from BIS Assistant.")
    applicable_standards: List[str] = Field(default_factory=list, description="Relevant IS codes.")
    source_citation: str = Field(default="", description="Citation source / document reference.")
    next_step: str = Field(default="", description="Actionable next steps.")
    follow_up_prompt: str = Field(default="", description="Suggested follow-up query.")
    cache_hit: bool = Field(default=False, description="Whether response was served from cache.")
    compliance_metadata: ComplianceMetadata = Field(default_factory=ComplianceMetadata, description="Regulatory, AIR, lab, and amendment compliance parameters.")
    confidence_metrics: ConfidenceMetrics = Field(default_factory=ConfidenceMetrics, description="Intent confidence scoring and clarification triggers.")
    audit_metadata: AuditMetadata = Field(default_factory=AuditMetadata, description="Immutable legal audit trail metadata.")
    token_usage: TokenUsageSummary = Field(..., description="Token consumption breakdown.")


class VoiceQueryResponse(BaseModel):
    transcription: str = Field(..., description="Speech-to-text transcript of uploaded audio.")
    result: QueryResponse = Field(..., description="Structured RAG response.")


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "BIS Agentic RAG Assistant REST API"
    llm_model: str
    embedding_provider: str
    cache_enabled: bool
    chroma_db_exists: bool
    active_sessions_count: int


class SessionInfoResponse(BaseModel):
    sessions: List[Dict]
    total_active: int


class CacheClearResponse(BaseModel):
    status: str = "success"
    message: str


class SimpleStatusResponse(BaseModel):
    status: str
    message: str


# --------------------------------------------------------------------------- #
# FastAPI App Initialization & Lifespan
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Initializing BIS Agent REST API server...")
    try:
        validate_environment()
    except SystemExit:
        logger.warning("Environment validation warning during startup.")
    yield
    logger.info("Shutting down BIS Agent REST API server...")


app = FastAPI(
    title="BIS Agentic RAG Assistant REST API",
    description=(
        "Production REST API for Bureau of Indian Standards (BIS) conversational AI assistant. "
        "Supports multi-turn dialogs, hybrid vector search, instant cache retrieval, and voice processing."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# API Endpoints
# --------------------------------------------------------------------------- #
@app.get("/", response_model=HealthResponse, tags=["Diagnostics"])
@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health_check() -> HealthResponse:
    """Check API health, active configuration, and vector DB status."""
    chroma_exists = os.path.exists(CONFIG.db_path)
    return HealthResponse(
        status="ok",
        service="BIS Agentic RAG Assistant REST API",
        llm_model=CONFIG.llm_model,
        embedding_provider=CONFIG.embedding_provider,
        cache_enabled=CONFIG.cache_enabled,
        chroma_db_exists=chroma_exists,
        active_sessions_count=len(session_manager._sessions),
    )


@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Conversational Agent"],
    summary="Process a user text query",
)
async def process_query(payload: QueryRequest) -> QueryResponse:
    """
    Execute a turn of conversation with the BIS Agent.
    - Uses session history for context-aware multi-turn dialogs.
    - Performs front-loaded cache lookup for instant 0-token response.
    - Falls back to LangGraph RAG workflow with BM25 + dense retrieval.
    """
    try:
        session = session_manager.get_session(payload.session_id)
        state = session.run_turn(payload.query)
        payload_dict = session.to_json(state)

        return QueryResponse(
            session_id=payload.session_id,
            query=payload.query,
            intent=payload_dict.get("intent", ""),
            domain=payload_dict.get("domain", ""),
            intent_localized=payload_dict.get("intent_localized", ""),
            llm_provider=payload_dict.get("llm_provider", ""),
            llm_model=payload_dict.get("llm_model", ""),
            response_time_ms=payload_dict.get("response_time_ms", 0.0),
            response_time_seconds=payload_dict.get("response_time_seconds", 0.0),
            core_response=payload_dict.get("core_response", ""),
            applicable_standards=payload_dict.get("applicable_standards", []),
            source_citation=payload_dict.get("source_citation", ""),
            next_step=payload_dict.get("next_step", ""),
            follow_up_prompt=payload_dict.get("follow_up_prompt", ""),
            cache_hit=payload_dict.get("cache_hit", False),
            compliance_metadata=payload_dict.get("compliance_metadata", {}),
            confidence_metrics=payload_dict.get("confidence_metrics", {}),
            audit_metadata=payload_dict.get("audit_metadata", {}),
            token_usage=payload_dict.get("token_usage", {}),
        )
    except SessionRateLimitException as exc:
        logger.warning("Rate limit hit for session %s: %s", payload.session_id, exc.message)
        err_payload = APIErrorPayload(
            status="error",
            error_code=exc.error_code,
            message=exc.message,
            suggested_action="Please initialize a new session or wait before sending further queries.",
            session_id=payload.session_id,
        )
        return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=err_payload.model_dump())
    except Exception as exc:
        logger.exception("Error processing query: %s", exc)
        err_payload = APIErrorPayload(
            status="error",
            error_code="INTERNAL_SERVER_ERROR",
            message=f"Error executing agent turn: {str(exc)}",
            suggested_action="Verify query parameters and try again.",
            session_id=payload.session_id,
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=err_payload.model_dump())


@app.post(
    "/api/v1/voice-query",
    response_model=VoiceQueryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Conversational Agent"],
    summary="Process an audio file query (Voice-to-Text RAG)",
)
async def process_voice_query(
    file: UploadFile = File(..., description="Audio file (.wav, .mp3, .m4a, .ogg, .webm)"),
    session_id: str = Form(default="default", description="Conversation session ID"),
) -> VoiceQueryResponse:
    """
    Upload an audio clip, transcribe via Whisper, and process the transcribed question through RAG.
    """
    allowed_exts = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext and file_ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format '{file_ext}'. Allowed formats: {', '.join(allowed_exts)}",
        )

    # Save uploaded file to temporary path
    suffix = file_ext if file_ext else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
        shutil.copyfileobj(file.file, temp_audio)
        temp_audio_path = temp_audio.name

    try:
        handler = get_audio_handler()
        transcription = handler.transcribe(temp_audio_path)
        if not transcription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not transcribe audio or empty speech detected.",
            )

        # Run transcribed text through RAG turn
        session = session_manager.get_session(session_id)
        state = session.run_turn(transcription)
        payload_dict = session.to_json(state)

        result = QueryResponse(
            session_id=session_id,
            query=transcription,
            intent=payload_dict.get("intent", ""),
            domain=payload_dict.get("domain", ""),
            intent_localized=payload_dict.get("intent_localized", ""),
            llm_provider=payload_dict.get("llm_provider", ""),
            llm_model=payload_dict.get("llm_model", ""),
            response_time_ms=payload_dict.get("response_time_ms", 0.0),
            response_time_seconds=payload_dict.get("response_time_seconds", 0.0),
            core_response=payload_dict.get("core_response", ""),
            applicable_standards=payload_dict.get("applicable_standards", []),
            source_citation=payload_dict.get("source_citation", ""),
            next_step=payload_dict.get("next_step", ""),
            follow_up_prompt=payload_dict.get("follow_up_prompt", ""),
            cache_hit=payload_dict.get("cache_hit", False),
            compliance_metadata=payload_dict.get("compliance_metadata", {}),
            confidence_metrics=payload_dict.get("confidence_metrics", {}),
            audit_metadata=payload_dict.get("audit_metadata", {}),
            token_usage=payload_dict.get("token_usage", {}),
        )

        return VoiceQueryResponse(
            transcription=transcription,
            result=result,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error processing voice query: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice processing error: {str(exc)}",
        )
    finally:
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception:
                pass


@app.get(
    "/api/v1/sessions",
    response_model=SessionInfoResponse,
    tags=["Session Management"],
    summary="List active conversation sessions",
)
async def list_active_sessions() -> SessionInfoResponse:
    """Retrieve metadata for all in-memory conversation sessions."""
    sessions = session_manager.list_sessions()
    return SessionInfoResponse(sessions=sessions, total_active=len(sessions))


@app.delete(
    "/api/v1/sessions/{session_id}",
    response_model=SimpleStatusResponse,
    tags=["Session Management"],
    summary="Reset or delete a session",
)
async def delete_session(session_id: str = APIPath(..., description="Target session ID")) -> SimpleStatusResponse:
    """Clear conversation history and session memory for a given session_id."""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return SimpleStatusResponse(
        status="success",
        message=f"Session '{session_id}' successfully deleted.",
    )


@app.post(
    "/api/v1/cache/clear",
    response_model=CacheClearResponse,
    tags=["Cache Control"],
    summary="Clear persistent response cache",
)
async def clear_cache() -> CacheClearResponse:
    """Purge all entries from the persistent response cache."""
    try:
        cache = ResponseCache()
        cache.clear()
        return CacheClearResponse(
            status="success",
            message="Response cache cleared successfully.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(exc)}",
        )
