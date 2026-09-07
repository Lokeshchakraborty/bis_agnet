"""
BIS Agentic RAG Assistant - FastAPI REST API
==============================================
Exposes high-performance REST endpoints for text queries, voice audio processing,
session management, and response cache control.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile

import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import time
from fastapi import FastAPI, File, HTTPException, Path as APIPath, UploadFile, Form, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from src.agent.session import Session, SessionRateLimitException
from src.config import CONFIG, validate_environment
from src.schemas import BISResponse, ComplianceMetadata, ConfidenceMetrics, AuditMetadata, APIErrorPayload
from src.tools.cache import ResponseCache

logger = logging.getLogger("bis_api")

# --------------------------------------------------------------------------- #
# In-Memory Session Manager
# --------------------------------------------------------------------------- #
class SessionManager:
    """Manages active conversation sessions mapped strictly by (user_id, session_id) composite keys."""

    def __init__(self) -> None:
        self._sessions: Dict[Tuple[str, str], Session] = {}

    def get_session(self, session_id: str, user_id: str = "default_user") -> Session:
        """Retrieve existing session or create a new isolated session for (user_id, session_id)."""
        uid = user_id or "default_user"
        key = (uid, session_id)
        if key not in self._sessions:
            logger.info("Initializing new isolated session: %s for user: %s", session_id, uid)
            self._sessions[key] = Session()
        return self._sessions[key]

    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict]:
        """Summarize active session states filtered strictly by user_id."""
        summaries = []
        target_user = user_id or "default_user"
        for (uid, sid), sess in self._sessions.items():
            if uid == target_user:
                summaries.append({
                    "session_id": sid,
                    "user_id": uid,
                    "history_turns": len(sess.history),
                    "last_query": sess.history[-1][0] if sess.history else None,
                })
        return summaries

    def delete_session(self, session_id: str, user_id: str = "default_user") -> bool:
        """Remove a session from memory for target user_id."""
        uid = user_id or "default_user"
        key = (uid, session_id)
        if key in self._sessions:
            del self._sessions[key]
            logger.info("Deleted session: %s for user: %s", session_id, uid)
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

class UserSignupRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    full_name: str = Field(..., description="User full name")


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class ChangePasswordRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")


class UserProfile(BaseModel):
    user_id: str
    email: str
    full_name: str
    created_at: Optional[str] = ""
    role: str = "user"
    is_admin: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None


class UserModelConfigRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    llm_provider: str = Field(..., description="LLM provider name")
    llm_model: str = Field(..., description="Target LLM model name")
    llm_api_key: Optional[str] = Field(default="", description="BYOK API key")
    llm_base_url: Optional[str] = Field(default="", description="Base URL for local Ollama / OpenRouter")


class TestModelConnectionRequest(BaseModel):
    llm_provider: Optional[str] = Field(default=None, description="LLM provider name")
    provider: Optional[str] = Field(default=None, description="Alternative key for provider")
    llm_model: Optional[str] = Field(default=None, description="Target LLM model name")
    model: Optional[str] = Field(default=None, description="Alternative key for model")
    llm_api_key: Optional[str] = Field(default="", description="BYOK API key")
    api_key: Optional[str] = Field(default="", description="Alternative key for API key")
    llm_base_url: Optional[str] = Field(default="", description="Base URL")
    base_url: Optional[str] = Field(default="", description="Alternative key for Base URL")


class AuthResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    user: Optional[UserProfile] = None


class QueryRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="User question or prompt for the BIS Agent.")
    prompt: Optional[str] = Field(default=None, description="Alternative key for user query.")
    text: Optional[str] = Field(default=None, description="Alternative key for user text.")
    question: Optional[str] = Field(default=None, description="Alternative key for question.")
    session_id: str = Field(default="default", description="Unique conversation session identifier.")
    user_id: str = Field(default="default_user", description="Logged-in user identifier.")
    llm_provider: Optional[str] = Field(default=None, description="BYOK provider name")
    llm_model: Optional[str] = Field(default=None, description="Target LLM model name")
    llm_api_key: Optional[str] = Field(default=None, description="BYOK API key")
    llm_base_url: Optional[str] = Field(default=None, description="Base URL for local Ollama / OpenRouter")

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
                "session_id": "user-123",
                "user_id": "usr_abc123"
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
    supabase_connected: bool = False


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

    # Initialize Supabase DB tables asynchronously if configured
    try:
        from backend.db.supabase_client import init_supabase_db
        await init_supabase_db()
    except Exception as exc:
        logger.warning("Supabase DB initialization notice: %s", exc)

    yield
    logger.info("Shutting down BIS Agent REST API server...")
    try:
        from backend.db.supabase_client import close_async_db_engine
        await close_async_db_engine()
    except Exception as exc:
        logger.warning("Supabase DB cleanup notice: %s", exc)


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

# Enable GZip compression for large responses (>1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time-Ms header to every HTTP response for latency monitoring."""
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    return response


# --------------------------------------------------------------------------- #
# API Endpoints
# --------------------------------------------------------------------------- #
@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health_check() -> HealthResponse:
    """Check API health, active configuration, vector DB status, and Supabase connection."""
    chroma_exists = os.path.exists(CONFIG.db_path)
    supabase_ok = bool(CONFIG.database_url or CONFIG.supabase_url)
    return HealthResponse(
        status="ok",
        service="BIS Agentic RAG Assistant REST API",
        llm_model=CONFIG.llm_model,
        embedding_provider=CONFIG.embedding_provider,
        cache_enabled=CONFIG.cache_enabled,
        chroma_db_exists=chroma_exists,
        active_sessions_count=len(session_manager._sessions),
        supabase_connected=supabase_ok,
    )


@app.get("/", tags=["Diagnostics"], summary="Root endpoint - serves UI or API status")
async def root_endpoint(request: Request):
    """Serve React frontend index.html for browser navigation, or HealthResponse JSON for API clients."""
    accept = request.headers.get("accept", "")
    frontend_dist_path = os.path.join(os.path.dirname(__file__), "frontend", "dist")
    index_file = os.path.join(frontend_dist_path, "index.html")
    if "text/html" in accept and os.path.exists(index_file):
        return FileResponse(index_file)
    return await health_check()



# --------------------------------------------------------------------------- #
# User Authentication Endpoints
# --------------------------------------------------------------------------- #
@app.post(
    "/api/v1/auth/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    tags=["User Authentication"],
    summary="Register a new user",
)
async def user_signup(payload: UserSignupRequest) -> AuthResponse:
    """Create a new user account in Supabase PostgreSQL."""
    from backend.db.supabase_client import create_user_in_supabase
    res = await create_user_in_supabase(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    if not res.get("success"):
        return AuthResponse(success=False, error=res.get("error", "Signup failed."))
    return AuthResponse(success=True, user=UserProfile(**res["user"]))


@app.post(
    "/api/v1/auth/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    tags=["User Authentication"],
    summary="Authenticate user login",
)
async def user_login(payload: UserLoginRequest) -> AuthResponse:
    """Authenticate email & password against Supabase PostgreSQL."""
    from backend.db.supabase_client import authenticate_user_in_supabase
    res = await authenticate_user_in_supabase(
        email=payload.email,
        password=payload.password,
    )
    if not res.get("success"):
        return AuthResponse(success=False, error=res.get("error", "Invalid credentials."))
    return AuthResponse(success=True, user=UserProfile(**res["user"]))


@app.post(
    "/api/v1/auth/change-password",
    response_model=SimpleStatusResponse,
    status_code=status.HTTP_200_OK,
    tags=["User Authentication"],
    summary="Change user password",
)
async def change_password(payload: ChangePasswordRequest) -> SimpleStatusResponse:
    """Verify old password and update user password in Supabase PostgreSQL."""
    from backend.db.supabase_client import change_user_password_in_supabase
    res = await change_user_password_in_supabase(
        user_id=payload.user_id,
        old_password=payload.old_password,
        new_password=payload.new_password,
    )
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("error", "Password change failed."))
    return SimpleStatusResponse(status="success", message=res.get("message", "Password updated successfully."))


@app.get(
    "/api/v1/auth/user-usage/{user_id}",

    tags=["User Authentication"],
    summary="Get cumulative lifetime account token usage for a user",
)
async def get_user_account_usage(user_id: str = APIPath(..., description="Target user ID")):
    """Calculate cumulative lifetime account-wide token usage for a user from Supabase PostgreSQL."""
    from backend.db.supabase_client import get_user_account_usage_from_supabase
    return await get_user_account_usage_from_supabase(user_id)


@app.post(
    "/api/v1/auth/user-model-config",
    response_model=SimpleStatusResponse,
    status_code=status.HTTP_200_OK,
    tags=["User Authentication"],
    summary="Save user BYOK AI model configuration",
)
async def update_user_model_config(payload: UserModelConfigRequest) -> SimpleStatusResponse:
    """Save user BYOK model provider, model name, API key, and base URL in Supabase PostgreSQL."""
    from backend.db.supabase_client import update_user_model_config_in_supabase
    res = await update_user_model_config_in_supabase(
        user_id=payload.user_id,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
        llm_api_key=payload.llm_api_key or "",
        llm_base_url=payload.llm_base_url or "",
    )
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("error", "Failed to save configuration."))
    return SimpleStatusResponse(status="success", message=res.get("message", "Model configuration saved successfully."))


@app.post(
    "/api/v1/auth/test-model-connection",
    response_model=SimpleStatusResponse,
    status_code=status.HTTP_200_OK,
    tags=["User Authentication"],
    summary="Test BYOK model API key and connection",
)
async def test_model_connection(payload: TestModelConnectionRequest) -> SimpleStatusResponse:
    """Instantiate target LLM model and verify connection with a test prompt."""
    from src.agent.llm_factory import create_llm_model
    provider = payload.llm_provider or payload.provider or "google"
    model = payload.llm_model or payload.model or CONFIG.llm_model or "gemini-3.5-flash"
    api_key = payload.llm_api_key or payload.api_key or ""
    base_url = payload.llm_base_url or payload.base_url or ""
    try:
        llm = create_llm_model(
            provider=provider,
            model_name=model,
            api_key=api_key,
            base_url=base_url,
        )
        res = llm.invoke("Hi")
        actual_model = getattr(llm, "model", model)
        return SimpleStatusResponse(
            status="success",
            message=f"Successfully connected to {provider.upper()} ({actual_model})!",
        )
    except Exception as exc:
        logger.warning("Test model connection failed for provider %s model %s: %s", provider, model, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection failed: {str(exc)}",
        )


from fastapi.responses import StreamingResponse


@app.post(
    "/api/v1/query/stream",
    tags=["Conversational Agent"],
    summary="Process query with real-time SSE state streaming",
)
async def process_query_stream(payload: QueryRequest):
    """
    Stream real-time model thinking, retrieval, and synthesis states as SSE events.
    """
    llm_provider = payload.llm_provider
    llm_model = payload.llm_model
    llm_api_key = payload.llm_api_key
    llm_base_url = payload.llm_base_url

    if not llm_provider and payload.user_id and payload.user_id != "default_user":
        try:
            from backend.db.supabase_client import get_user_model_config_from_supabase
            user_config = await get_user_model_config_from_supabase(payload.user_id)
            if user_config and user_config.get("llm_provider"):
                llm_provider = user_config.get("llm_provider")
                llm_model = user_config.get("llm_model")
                llm_api_key = user_config.get("llm_api_key")
                llm_base_url = user_config.get("llm_base_url")
        except Exception:
            pass

    session = session_manager.get_session(payload.session_id, payload.user_id)

    async def event_generator():
        try:
            async for chunk in session.run_turn_stream(
                user_query=payload.query,
                session_id=payload.session_id,
                user_id=payload.user_id,
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            logger.exception("Error in query stream: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
        llm_provider = payload.llm_provider
        llm_model = payload.llm_model
        llm_api_key = payload.llm_api_key
        llm_base_url = payload.llm_base_url

        if not llm_provider and payload.user_id and payload.user_id != "default_user":
            try:
                from backend.db.supabase_client import get_user_model_config_from_supabase
                user_config = await get_user_model_config_from_supabase(payload.user_id)
                if user_config and user_config.get("llm_provider"):
                    llm_provider = user_config.get("llm_provider")
                    llm_model = user_config.get("llm_model")
                    llm_api_key = user_config.get("llm_api_key")
                    llm_base_url = user_config.get("llm_base_url")
            except Exception:
                pass

        session = session_manager.get_session(payload.session_id, payload.user_id)
        state = session.run_turn(
            payload.query,
            session_id=payload.session_id,
            user_id=payload.user_id,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
        )
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
        state = session.run_turn(transcription, session_id=session_id)
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
    summary="List active conversation sessions for a user",
)
async def list_active_sessions(user_id: str = "default_user") -> SessionInfoResponse:
    """Retrieve metadata for conversation sessions, combining in-memory active states with Supabase PostgreSQL."""
    sessions_dict: Dict[str, Dict] = {}

    # 1. Load active in-memory sessions
    for s in session_manager.list_sessions(user_id=user_id):
        sessions_dict[s["session_id"]] = s

    # 2. Merge with Supabase PostgreSQL records if available
    try:
        from backend.db.supabase_client import list_user_sessions_from_supabase
        db_sessions = await list_user_sessions_from_supabase(user_id)
        if db_sessions:
            for s in db_sessions:
                sessions_dict[s["session_id"]] = s
    except Exception as exc:
        logger.warning("Error fetching sessions from Supabase: %s", exc)

    combined = list(sessions_dict.values())
    return SessionInfoResponse(sessions=combined, total_active=len(combined))


@app.get(
    "/api/v1/sessions/{session_id}",
    tags=["Session Management"],
    summary="Get conversation history for a session",
)
async def get_session_history(
    session_id: str = APIPath(..., description="Target session ID"),
    user_id: str = "default_user",
):
    """Retrieve full conversation turn history for a session from Supabase or in-memory cache."""
    try:
        from backend.db.supabase_client import get_session_from_supabase
        db_sess = await get_session_from_supabase(session_id, user_id=user_id)
        if db_sess and "history" in db_sess:
            history = db_sess["history"]
            if isinstance(history, str):
                history = json.loads(history)
            return {"session_id": session_id, "history": history}
    except Exception as exc:
        logger.warning("Error fetching session '%s' from Supabase: %s", session_id, exc)

    mem_sess = session_manager.get_session(session_id, user_id=user_id)
    raw_history = list(mem_sess.history)
    history_json = [{"user": u, "assistant": a} for u, a in raw_history]
    return {"session_id": session_id, "history": history_json}




@app.delete(
    "/api/v1/sessions/{session_id}",
    response_model=SimpleStatusResponse,
    tags=["Session Management"],
    summary="Reset or delete a session",
)
async def delete_session(
    session_id: str = APIPath(..., description="Target session ID"),
    user_id: str = "default_user",
) -> SimpleStatusResponse:
    """Clear conversation history and session memory for a given session_id from memory and Supabase."""
    deleted_mem = session_manager.delete_session(session_id, user_id=user_id)
    deleted_db = False
    try:
        from backend.db.supabase_client import delete_session_from_supabase
        deleted_db = await delete_session_from_supabase(session_id, user_id=user_id)
    except Exception as exc:
        logger.warning("Error deleting session '%s' from Supabase: %s", session_id, exc)

    if not deleted_mem and not deleted_db:
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


@app.get(
    "/api/v1/audit-logs",
    response_model=List[Dict],
    tags=["Compliance & Audit"],
    summary="Retrieve audit ledger records from Supabase",
)
async def get_audit_logs(
    session_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """Fetch structured legal & compliance audit trail records from Supabase PostgreSQL."""
    try:
        from backend.db.supabase_client import fetch_audit_logs_from_supabase
        logs = await fetch_audit_logs_from_supabase(session_id=session_id, limit=limit)
        return logs
    except Exception as exc:
        logger.exception("Failed to fetch audit logs: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit logs: {str(exc)}",
        )


class PDFExportRequest(BaseModel):
    query: str
    core_response: str
    applicable_standards: List[str] = Field(default_factory=list)
    next_step: Optional[str] = None
    intent: Optional[str] = "compliance"
    user_name: Optional[str] = "Compliance Officer / Applicant"
    session_id: Optional[str] = "default"


@app.post(
    "/api/v1/export/pdf",
    tags=["Compliance & Audit"],
    summary="Generate and download official BIS compliance research dossier PDF",
)
async def export_compliance_pdf(payload: PDFExportRequest) -> StreamingResponse:
    """Generate and stream a full-fledged official Bureau of Indian Standards (BIS) compliance dossier PDF."""
    import re
    try:
        from src.tools.pdf_generator import generate_compliance_pdf
        pdf_buffer = generate_compliance_pdf(
            query=payload.query,
            core_response=payload.core_response,
            applicable_standards=payload.applicable_standards,
            next_step=payload.next_step,
            intent=payload.intent,
            user_name=payload.user_name,
            session_id=payload.session_id,
        )
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", payload.query[:30]).strip("_") or "Dossier"
        filename = f"BIS_Compliance_Research_{safe_name}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as exc:
        logger.exception("Failed to export compliance PDF: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate compliance PDF: {str(exc)}",
        )


# --------------------------------------------------------------------------- #
# Static File Serving (Optional: Single-Service Production Deployment)
# --------------------------------------------------------------------------- #
from fastapi.staticfiles import StaticFiles

frontend_dist_path = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist_path):
    logger.info("Mounting production frontend build from: %s", frontend_dist_path)
    assets_path = os.path.join(frontend_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="static_assets")
    app.mount("/", StaticFiles(directory=frontend_dist_path, html=True), name="static_frontend")
