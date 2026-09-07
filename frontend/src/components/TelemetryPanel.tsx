import React from 'react';
import { X, Cpu, Zap, ShieldCheck, Activity, BarChart2 } from 'lucide-react';
import type { QueryResponse } from '../types';


interface TelemetryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  lastResponse: QueryResponse | null;
  theme?: 'light' | 'dark';
}

export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({
  isOpen,
  onClose,
  lastResponse,
  theme = 'light',
}) => {
  if (!isOpen) return null;

  const isDark = theme === 'dark';
  const tu = lastResponse?.token_usage;

  return (
    <aside
      className="glass-panel animate-fade-in telemetry-drawer-mobile"
      style={{
        width: '320px',
        borderRadius: 0,
        borderTop: 0,
        borderBottom: 0,
        borderRight: 0,
        borderLeft: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid var(--glass-border)',
        background: isDark ? '#1E1F20' : '#FFFFFF',
        display: 'flex',
        flexDirection: 'column',
        padding: '20px',
        gap: '20px',
        zIndex: 1000,
        boxShadow: isDark ? '-4px 0 25px rgba(0, 0, 0, 0.5)' : '-4px 0 20px rgba(0, 0, 0, 0.05)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <BarChart2 size={20} color="#0284C7" />
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>Telemetry & Metrics</h3>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
          <X size={18} />
        </button>
      </div>

      {!lastResponse ? (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', textAlign: 'center', padding: '32px 0' }}>
          No turn telemetry recorded yet. Ask a query to inspect live LLM & vector search telemetry.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Latency & Cache Status */}
          <div style={{ padding: '12px', borderRadius: '12px', background: isDark ? '#131314' : '#F8FAFC', border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid var(--glass-border)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Turn Response Latency</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#0284C7' }} className="mono">
              {lastResponse.response_time_ms} <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>ms</span>
            </div>
            <div style={{ marginTop: '8px', fontSize: '0.75rem' }}>
              {lastResponse.cache_hit ? (
                <span style={{ color: '#D97706', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <Zap size={14} /> ⚡ 0-Token Instant Cache Hit
                </span>
              ) : (
                <span style={{ color: '#059669', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <Activity size={14} /> LangGraph Hybrid RAG Execution
                </span>
              )}
            </div>
          </div>

          {/* Token Consumption */}
          <div style={{ padding: '12px', borderRadius: '12px', background: isDark ? '#131314' : '#F8FAFC', border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid var(--glass-border)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Cpu size={14} color="#D97706" /> Token Telemetry Summary
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Turn Prompt Tokens:</span>
              <span className="mono" style={{ fontWeight: 600, color: 'var(--text-main)' }}>{tu?.turn_prompt_tokens || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Turn Completion Tokens:</span>
              <span className="mono" style={{ fontWeight: 600, color: 'var(--text-main)' }}>{tu?.turn_completion_tokens || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', paddingTop: '6px', borderTop: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid var(--glass-border)' }}>
              <span style={{ color: '#D97706', fontWeight: 600 }}>Session Total Saved:</span>
              <span className="mono" style={{ color: '#D97706', fontWeight: 700 }}>⚡ {tu?.session_total_saved_tokens || 0} tokens</span>
            </div>
          </div>

          {/* Intent & Regulatory Parameters */}
          <div style={{ padding: '12px', borderRadius: '12px', background: isDark ? '#131314' : '#F8FAFC', border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid var(--glass-border)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldCheck size={14} color="#059669" /> Intent & Compliance Parameters
            </div>

            <div style={{ fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Detected Intent:</span>
              <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{lastResponse.intent || 'N/A'}</span>
            </div>
            <div style={{ fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Domain Category:</span>
              <span style={{ fontWeight: 600, color: '#0284C7' }}>{lastResponse.domain || 'N/A'}</span>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
