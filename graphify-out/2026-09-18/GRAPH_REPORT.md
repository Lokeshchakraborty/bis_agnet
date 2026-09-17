# Graph Report - BIS_AGENT  (2026-09-18)

## Corpus Check
- 60 files · ~65,970 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 5, .css 2, .example 1)

## Summary
- 749 nodes · 1325 edges · 45 communities (39 shown, 6 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 45 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0c612eec`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- scraper.py
- App.tsx
- AgentNodes
- change_password
- supabase_client.py
- package.json
- server.py
- compilerOptions
- nodes.py
- ResponseCache
- generate_compliance_pdf
- compilerOptions
- LocalAudioHandler
- build_vectordb.py
- tools/__init__.py
- _is_research_query
- Session
- vector_store.py
- schema.sql
- process_query
- config.py
- TestBISAgentAPI
- SessionManager
- 🧠 BIS SATHI — Architectural Brain & System Specification
- crawler.py
- create_llm_model
- Production Deployment & Operations Guide
- lifespan
- BIS Agentic RAG Assistant (Voice & Text)
- .oxlintrc.json
- Config
- guardrails.py
- SessionRateLimitException
- process_voice_query
- app.py
- tsconfig.json
- audit.py
- backend/__init__.py
- vercel.json
- get
- React + TypeScript + Vite
- initialize_components
- rules/graphify.md
- workflows/graphify.md
- .log_interaction

## God Nodes (most connected - your core abstractions)
1. `AgentNodes` - 25 edges
2. `Session` - 22 edges
3. `ResponseCache` - 22 edges
4. `BISResponse` - 19 edges
5. `get_async_db_engine()` - 18 edges
6. `compilerOptions` - 18 edges
7. `AgentState` - 18 edges
8. `TokenTracker` - 16 edges
9. `compilerOptions` - 15 edges
10. `Intent` - 14 edges

## Surprising Connections (you probably didn't know these)
- `SessionManager` --uses--> `Session`  [INFERRED]
  app.py → src/agent/session.py
- `QueryResponse` --uses--> `AuditMetadata`  [INFERRED]
  app.py → src/schemas.py
- `QueryResponse` --uses--> `ConfidenceMetrics`  [INFERRED]
  app.py → src/schemas.py
- `process_query()` --uses--> `SessionRateLimitException`  [INFERRED]
  app.py → src/agent/session.py
- `clear_cache()` --uses--> `ResponseCache`  [INFERRED]
  app.py → src/tools/cache.py

## Import Cycles
- None detected.

## Communities (45 total, 6 thin omitted)

### Community 0 - "scraper.py"
Cohesion: 0.06
Nodes (53): CircularRecord, _clean(), CRSRecord, _extract_is_codes(), _extract_search_candidates(), _fetch_live_crs_products(), _fetch_live_qco_registry(), _format_amendments() (+45 more)

### Community 1 - "App.tsx"
Cohesion: 0.08
Nodes (49): App(), AuditLedgerModal(), AuditLedgerModalProps, AuthModal(), AuthModalProps, BisLogo(), BisLogoProps, ChatWindow() (+41 more)

### Community 2 - "AgentNodes"
Cohesion: 0.14
Nodes (16): AgentNodes, _is_difference_query(), Any, Detect if the user is asking to compare or find differences between standards,…, Encapsulates graph node methods and initialized LLM/retriever dependencies., Rewrite a context-dependent query into a standalone query. Args:…, Decorator for exponential backoff on rate limits and transient errors., Rewrite query using chat history only when dependent, saving tokens. (+8 more)

### Community 3 - "change_password"
Cohesion: 0.22
Nodes (9): change_password(), ChangePasswordRequest, delete_session(), Verify old password and update user password in Supabase PostgreSQL., Clear conversation history and session memory for a given session_id from…, SimpleStatusResponse, delete_session_from_supabase(), Delete a session record from Supabase PostgreSQL. (+1 more)

### Community 4 - "supabase_client.py"
Cohesion: 0.11
Nodes (32): Supabase Database Integration Package., authenticate_user_in_supabase(), change_user_password_in_supabase(), clear_all_audit_logs_from_supabase(), fetch_audit_logs_from_supabase(), get_async_db_engine(), get_session_from_supabase(), get_supabase_client() (+24 more)

### Community 5 - "package.json"
Cohesion: 0.06
Nodes (35): dependencies, lucide-react, react, react-dom, devDependencies, autoprefixer, oxlint, postcss (+27 more)

### Community 6 - "server.py"
Cohesion: 0.28
Nodes (8): display_server_banner(), main(), parse_args(), Namespace, BIS Agentic RAG Assistant - REST API Server Entry Point…, Parse CLI arguments for REST API server., Print styled startup banner for REST API., Validate environment and launch Uvicorn web server.

### Community 7 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+11 more)

### Community 8 - "nodes.py"
Cohesion: 0.11
Nodes (16): Enum, build_graph(), LangGraph StateGraph Workflow Construction for BIS Agent., Construct and compile the LangGraph workflow., Agent orchestration package for BIS Agent., _fast_classify(), Graph Node Implementations, Prompt Templates, and Routing Helpers for BIS Agent., Zero-token instant classification for IS codes, greetings, and domain keywords.… (+8 more)

### Community 9 - "ResponseCache"
Cohesion: 0.14
Nodes (11): _normalize(), Any, Path, Lowercase and strip punctuation for stable cache key generation., Manages persistent caching of synthesized responses., Create a short, deterministic SHA-256 hash key isolated per user_id., Return cached payload if valid and not expired, else None., Store a response payload in cache. (+3 more)

### Community 10 - "generate_compliance_pdf"
Cohesion: 0.13
Nodes (16): BytesIO, Paragraph, ParagraphStyle, generate_compliance_pdf(), _flush_table(), NumberedCanvas, _parse_markdown_table(), BIS SATHI - Compliance Research PDF Generator… (+8 more)

### Community 11 - "compilerOptions"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 12 - "LocalAudioHandler"
Cohesion: 0.13
Nodes (8): LocalAudioHandler, Local Audio Processing (Whisper STT + Pyttsx3 Offline TTS)…, Offline voice recorder, Whisper speech-to-text transcriber, and TTS speaker., Lazy loader for Whisper model., Record audio from microphone until user presses Enter., Transcribe WAV audio file into text using Whisper., Speak response aloud using local pyttsx3 engine., Audio processing package for BIS Agent.

### Community 13 - "build_vectordb.py"
Cohesion: 0.15
Nodes (17): _add_metadata(), get_embeddings_model(), ingest_all(), ingest_segment(), main(), Document, Embeddings, BIS ChromaDB Document Ingestion Pipeline… (+9 more)

### Community 14 - "tools/__init__.py"
Cohesion: 0.14
Nodes (16): Tools package for BIS Agent (Caching, Retrieval, and Web Scraping)., _BM25Index, _cosine_rerank(), _embed_documents_cached(), _get_bm25_index(), hybrid_retrieve(), _run_bm25(), any (+8 more)

### Community 15 - "_is_research_query"
Cohesion: 0.22
Nodes (6): _get_scraped_data(), _node(), _is_research_query(), Detect if the user is requesting a comprehensive compliance research…, Factory: returns a retrieval node for domain PDFs using hybrid BM25 + dense…, Concurrent live BIS portal scraping + local Chroma DB retrieval.

### Community 16 - "Session"
Cohesion: 0.11
Nodes (18): Atomically increment total_tokens_burned and total_queries_count in users table…, record_token_burn_for_user_in_supabase(), _clean_agent_for_history(), _format_history(), _needs_rewrite(), Check if query is dependent on prior conversational context. Scans the *entire*…, Strip internal follow-up prompt tag so synthesis LLM does not mention or echo…, Format chat history for LLM prompts. Args: chat_history: List of (user_query,… (+10 more)

### Community 17 - "vector_store.py"
Cohesion: 0.24
Nodes (11): delete_vector_collection(), get_all_documents_for_domain(), get_pg_sync_engine(), get_vector_store(), Document, Embeddings, Vector Store Management & Abstraction Layer…, Retrieve all document contents and metadatas for a collection (used by BM25). (+3 more)

### Community 18 - "schema.sql"
Cohesion: 0.27
Nodes (11): audit_logs, idx_audit_session_id, idx_audit_timestamp, idx_audit_user_id, idx_cache_created_at, idx_sessions_updated_at, idx_sessions_user_id, idx_users_email (+3 more)

### Community 19 - "process_query"
Cohesion: 0.13
Nodes (14): process_query(), process_query_stream(), Any, QueryRequest, QueryResponse, Stream real-time model thinking, retrieval, and synthesis states as SSE events., Execute a turn of conversation with the BIS Agent. - Uses session history for…, get_user_model_config_from_supabase() (+6 more)

### Community 20 - "config.py"
Cohesion: 0.16
Nodes (14): display_token_summary(), display_welcome_banner(), main(), parse_args(), Namespace, BIS Agentic RAG Assistant (Voice & Text Enabled)…, Parse command line arguments., Print styled startup banner with system configuration. (+6 more)

### Community 21 - "TestBISAgentAPI"
Cohesion: 0.11
Nodes (7): KeepAliveManager, Derive target health ping URL. Prioritizes public RENDER_EXTERNAL_URL to…, Execute a single HTTP GET health check ping., Background loop running every interval_seconds (default 600s = 10 min)., Automated background worker that periodically sends self-pings to the /health…, Automated REST API integration tests for BIS Agentic RAG Assistant., TestBISAgentAPI

### Community 22 - "SessionManager"
Cohesion: 0.18
Nodes (6): Manages active conversation sessions mapped strictly by (user_id, session_id)…, Retrieve existing session or create a new isolated session for (user_id,…, Summarize active session states filtered strictly by user_id., Remove a session from memory for target user_id., Clear all active sessions., SessionManager

### Community 23 - "🧠 BIS SATHI — Architectural Brain & System Specification"
Cohesion: 0.05
Nodes (38): 10.1 Containerized Deployment (`Dockerfile`), 10.2 Single-Service Cloud Deployment (Render / Heroku), 10.3 Air-Gapped / Sovereign Enterprise Setup, 10. Deployment & Infrastructure, 1. Executive Overview, 1. Unified 7-Intent Architecture, ⚡ 1. Zero-Token Instant Cache Bypass, 2.1 Backend & Orchestration (+30 more)

### Community 24 - "crawler.py"
Cohesion: 0.26
Nodes (11): _clean(), crawl_live_circulars_and_orders(), crawl_live_crs_products(), crawl_live_qco_registry(), Live Regulatory Intelligence, QCO & CRS Notification Crawler…, Crawl latest Gazette circulars and regulatory notifications., Save crawled QCOs, CRS products, and circulars into structured domain text…, Collapse consecutive whitespace and trim. (+3 more)

### Community 25 - "create_llm_model"
Cohesion: 0.40
Nodes (4): BaseChatModel, create_llm_model(), Unified LLM Factory for Multi-Provider & BYOK Execution…, Instantiate the appropriate LangChain ChatModel based on provider and model…

### Community 26 - "Production Deployment & Operations Guide"
Cohesion: 0.12
Nodes (16): 1. Clone & Configure Environment, 1. Deploy Backend (Render / Railway / Fly.io), 2. Build & Launch Containers, 2. Deploy Frontend on Vercel, 3. Verify Container Status, 4. Test Health Endpoint, 🏗 Architecture Overview, 🗄 Database Initialization (Supabase PGVector) (+8 more)

### Community 27 - "lifespan"
Cohesion: 0.40
Nodes (5): lifespan(), Startup and shutdown events., close_async_db_engine(), Gracefully dispose and close SQLAlchemy AsyncEngine pool on server shutdown., FastAPI

### Community 28 - "BIS Agentic RAG Assistant (Voice & Text)"
Cohesion: 0.18
Nodes (10): 1. Configure Environment, 2. Ingest BIS Documents, 3. Run via CLI, 4. Run REST API Server, BIS Agentic RAG Assistant (Voice & Text), Example Query Request (`POST /api/v1/query`), ⚡ Key Optimizations & Features, 🏗 Project Architecture (+2 more)

### Community 29 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 30 - "Config"
Cohesion: 0.50
Nodes (3): Config, Central configuration for models, paths, retrieval parameters, and caching., Format database URL for psycopg3 driver used by PGVector.

### Community 31 - "guardrails.py"
Cohesion: 0.17
Nodes (14): clean_leaked_system_blocks(), format_markdown_tables(), guarantee_valid_pydantic_output(), Deterministic Output Guardrails & Post-Synthesis Validation Layer…, Detect and strip system integration blocks, leaked JSON schemas, and artificial…, Ensure Markdown tables have proper formatting and heal broken rows, orphan…, Run output through strict Pydantic model validation. Guarantees fields like…, Validate, sanitize, and score a synthesized BIS response. (+6 more)

### Community 33 - "SessionRateLimitException"
Cohesion: 0.50
Nodes (3): Exception, Raised when a session exceeds maximum turn or token consumption caps., SessionRateLimitException

### Community 34 - "process_voice_query"
Cohesion: 0.33
Nodes (6): get_audio_handler(), process_voice_query(), Lazy initialization of LocalAudioHandler for voice endpoint., Upload an audio clip, transcribe via Whisper, and process the transcribed…, VoiceQueryResponse, UploadFile

### Community 35 - "app.py"
Cohesion: 0.11
Nodes (32): AuthResponse, CacheClearResponse, clear_cache(), export_compliance_pdf(), list_active_sessions(), PDFExportRequest, BaseModel, BIS Agentic RAG Assistant - FastAPI REST API… (+24 more)

### Community 37 - "audit.py"
Cohesion: 0.29
Nodes (6): AuditLogger, get_audit_logger(), Path, Immutable Audit Ledger Logger for BIS Agent…, Manages immutable audit logging for every agent interaction., Return global AuditLogger instance.

### Community 40 - "get"
Cohesion: 0.10
Nodes (21): add_process_time_header(), get_audit_logs(), get_keep_alive_status(), get_session_history(), get_user_account_usage(), health_check(), health_ping(), HealthResponse (+13 more)

### Community 42 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the Oxlint configuration, React Compiler, React + TypeScript + Vite

### Community 43 - "initialize_components"
Cohesion: 0.50
Nodes (4): ChatGoogleGenerativeAI, initialize_components(), any, Initialize LLM, Embeddings, Catalog Retriever, and Domain Collections.

## Knowledge Gaps
- **142 isolated node(s):** `$schema`, `plugins`, `react/rules-of-hooks`, `react/only-export-components`, `name` (+137 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 394 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ResponseCache` connect `ResponseCache` to `AgentNodes`, `app.py`, `nodes.py`, `tools/__init__.py`, `Session`, `config.py`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `Session` connect `Session` to `AgentNodes`, `app.py`, `nodes.py`, `ResponseCache`, `config.py`, `SessionManager`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `generate_compliance_pdf()` connect `generate_compliance_pdf` to `app.py`, `guardrails.py`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `AgentNodes` (e.g. with `AgentState` and `BISResponse`) actually correct?**
  _`AgentNodes` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Session` (e.g. with `SessionManager` and `AgentState`) actually correct?**
  _`Session` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `ResponseCache` (e.g. with `clear_cache()` and `AgentNodes`) actually correct?**
  _`ResponseCache` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `BISResponse` (e.g. with `guarantee_valid_pydantic_output()` and `validate_and_sanitize_response()`) actually correct?**
  _`BISResponse` has 5 INFERRED edges - model-reasoned connections that need verification._