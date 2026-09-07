export interface UserProfile {
  user_id: string;
  email: string;
  full_name: string;
  created_at?: string;
  role?: string;
  is_admin?: boolean;
  llm_provider?: string;
  llm_model?: string;
  llm_api_key?: string;
  llm_base_url?: string;
}

export interface AuthResponse {
  success: boolean;
  error?: string;
  user?: UserProfile;
}

export interface ComplianceMetadata {
  is_code_referenced?: string;
  air_mandatory?: boolean;
  lab_accreditation_required?: boolean;
  amendment_status?: string;
  scheme_category?: string;
}

export interface ConfidenceMetrics {
  intent_confidence?: number;
  ambiguity_score?: number;
  requires_clarification?: boolean;
}

export interface AuditMetadata {
  interaction_id?: string;
  timestamp_utc?: string;
  prompt_sha256?: string;
  payload_sha256?: string;
  model_checkpoint?: string;
}

export interface TokenUsageSummary {
  llm_provider: string;
  llm_model: string;
  response_time_ms: number;
  response_time_seconds: number;
  turn_llm_tokens: number;
  turn_prompt_tokens: number;
  turn_completion_tokens: number;
  total_tokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  turn_embedding_tokens: number;
  session_total_llm_tokens: number;
  session_total_saved_tokens: number;
  estimated_saved_tokens?: number;
  embedding_provider: string;
}

export interface QueryResponse {
  session_id: string;
  query: string;
  intent: string;
  domain: string;
  intent_localized: string;
  llm_provider: string;
  llm_model: string;
  response_time_ms: number;
  response_time_seconds: number;
  core_response: string;
  applicable_standards: string[];
  source_citation: string;
  next_step: string;
  follow_up_prompt: string;
  cache_hit: boolean;
  compliance_metadata?: ComplianceMetadata;
  confidence_metrics?: ConfidenceMetrics;
  audit_metadata?: AuditMetadata;
  token_usage: TokenUsageSummary;
}


export interface VoiceQueryResponse {
  transcription: string;
  result: QueryResponse;
}

export interface HealthResponse {
  status: string;
  service: string;
  llm_model: string;
  embedding_provider: string;
  cache_enabled: boolean;
  chroma_db_exists: boolean;
  active_sessions_count: number;
  supabase_connected: boolean;
}

export interface AuditLogRecord {
  interaction_id: string;
  timestamp_utc: string;
  session_id: string;
  user_query: string;
  standalone_query?: string;
  prompt_sha256?: string;
  intent?: string;
  intent_localized?: string;
  model_checkpoint?: string;
  embedding_provider?: string;
  cache_hit?: boolean;
  response_time_ms?: number;
  confidence_metrics?: ConfidenceMetrics;
  compliance_metadata?: ComplianceMetadata;
  token_usage?: TokenUsageSummary;
  payload_sha256?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  query?: string;
  response?: QueryResponse;
  timestamp: string;
  isStreaming?: boolean;
}
