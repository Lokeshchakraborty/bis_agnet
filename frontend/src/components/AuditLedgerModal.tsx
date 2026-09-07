import React, { useState, useEffect } from 'react';
import { X, Search, Zap, RefreshCw, Key } from 'lucide-react';
import type { AuditLogRecord } from '../types';
import { getApiUrl } from '../config';


interface AuditLedgerModalProps {
  isOpen: boolean;
  onClose: () => void;
  theme?: 'light' | 'dark';
}

export const AuditLedgerModal: React.FC<AuditLedgerModalProps> = ({ isOpen, onClose, theme = 'light' }) => {
  const [logs, setLogs] = useState<AuditLogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [selectedRecord, setSelectedRecord] = useState<AuditLogRecord | null>(null);
  const isDark = theme === 'dark';

  const fetchLogs = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(getApiUrl('/api/v1/audit-logs?limit=50'));
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (err) {
      console.error('Failed to fetch audit logs from Supabase:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchLogs();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const filteredLogs = logs.filter(
    (l) =>
      l.user_query.toLowerCase().includes(searchFilter.toLowerCase()) ||
      l.session_id.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (l.intent && l.intent.toLowerCase().includes(searchFilter.toLowerCase()))
  );

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.65)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '16px' }}>
      <div className="animate-fade-in modal-responsive-card" style={{ background: isDark ? '#1E1F20' : '#FFFFFF', border: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid var(--glass-border)', borderRadius: '24px', width: '1000px', maxHeight: '90vh', display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px', position: 'relative', boxShadow: isDark ? '0 25px 60px rgba(0, 0, 0, 0.6)' : '0 20px 45px -10px rgba(0, 0, 0, 0.15)' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ padding: '10px', borderRadius: '50%', background: isDark ? 'rgba(217, 119, 6, 0.2)' : '#FEF3C7', color: '#F59E0B' }}>
              <Key size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-main)' }}>Immutable Supabase Audit Ledger</h2>
                <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '12px', background: isDark ? 'rgba(217, 119, 6, 0.2)' : '#FEF3C7', border: '1px solid #FDE68A', color: '#F59E0B', fontWeight: 700, textTransform: 'uppercase' }}>
                  Admin / Officer Restricted
                </span>
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Tamper-evident legal & regulatory audit records stored in Supabase PostgreSQL (Legal non-repudiation)
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={fetchLogs}
              style={{ background: isDark ? '#282A2C' : '#FFFFFF', border: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid var(--glass-border)', color: isDark ? '#E2E8F0' : 'var(--text-subtle)', borderRadius: '50%', padding: '8px', cursor: 'pointer', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}
              title="Refresh Audit Logs"
            >
              <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
            </button>
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '6px' }}>
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Search */}
        <div style={{ background: isDark ? '#131314' : '#F8FAFC', border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid var(--glass-border)', borderRadius: '12px', padding: '8px 14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Search size={16} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search logs by query text, session ID, or intent category..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            style={{ background: 'none', border: 'none', outline: 'none', color: 'var(--text-main)', fontSize: '0.88rem', width: '100%' }}
          />
        </div>


        {/* Table & Detail Split */}
        <div className="modal-grid-2col" style={{ flex: 1, display: 'flex', gap: '16px', overflow: 'hidden' }}>
          {/* Logs List Table */}
          <div style={{ flex: 1, overflowY: 'auto', border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid var(--glass-border)', borderRadius: '12px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: isDark ? '#131314' : '#F1F5F9', color: 'var(--text-main)', borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid var(--glass-border)' }}>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Timestamp</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Session ID</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>User Query</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Cache</th>
                  <th style={{ padding: '12px 14px', fontWeight: 600 }}>Latency</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No audit records found in Supabase.
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((log) => {
                    const isSelected = selectedRecord?.interaction_id === log.interaction_id;
                    return (
                      <tr
                        key={log.interaction_id}
                        onClick={() => setSelectedRecord(log)}
                        style={{
                          borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid var(--glass-border)',
                          background: isSelected ? (isDark ? 'rgba(217, 119, 6, 0.25)' : '#FEF3C7') : 'transparent',
                          cursor: 'pointer',
                        }}
                      >
                        <td style={{ padding: '12px 14px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }} className="mono">
                          {log.timestamp_utc ? new Date(log.timestamp_utc).toLocaleTimeString() : 'N/A'}
                        </td>
                        <td style={{ padding: '12px 14px', color: '#0284C7', fontWeight: 600 }}>{log.session_id}</td>
                        <td style={{ padding: '12px 14px', color: 'var(--text-main)', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {log.user_query}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          {log.cache_hit ? (
                            <span style={{ color: '#B45309', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <Zap size={13} /> ⚡ 0 Tokens
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>🧠 RAG Turn</span>
                          )}
                        </td>
                        <td style={{ padding: '12px 14px', color: 'var(--text-secondary)' }} className="mono">
                          {log.response_time_ms ? `${log.response_time_ms} ms` : 'N/A'}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Selected Record SHA-256 Inspector */}
          {selectedRecord && (
            <div className="glass-panel" style={{ width: '380px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto', background: isDark ? '#131314' : '#F8FAFC', border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid var(--glass-border)' }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#B45309' }}>Cryptographic SHA-256 Verification</h4>
              
              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Interaction ID:</span>
                <div className="mono" style={{ background: isDark ? '#1E1F20' : '#FFFFFF', border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid var(--glass-border)', padding: '6px', borderRadius: '6px', color: '#0284C7', marginTop: '4px', wordBreak: 'break-all' }}>
                  {selectedRecord.interaction_id}
                </div>
              </div>

              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Prompt SHA-256 Hash:</span>
                <div className="mono" style={{ background: isDark ? '#1E1F20' : '#FFFFFF', border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid var(--glass-border)', padding: '6px', borderRadius: '6px', color: '#059669', marginTop: '4px', wordBreak: 'break-all' }}>
                  {selectedRecord.prompt_sha256 || 'N/A'}
                </div>
              </div>

              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Payload SHA-256 Hash:</span>
                <div className="mono" style={{ background: isDark ? '#1E1F20' : '#FFFFFF', border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid var(--glass-border)', padding: '6px', borderRadius: '6px', color: '#B45309', marginTop: '4px', wordBreak: 'break-all' }}>
                  {selectedRecord.payload_sha256 || 'N/A'}
                </div>
              </div>

              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Detected Intent:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-main)', marginTop: '4px' }}>
                  {selectedRecord.intent || 'N/A'}
                </div>
              </div>

              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>LLM Model Checkpoint:</span>
                <div style={{ fontWeight: 600, color: '#0284C7', marginTop: '4px' }}>
                  {selectedRecord.model_checkpoint || 'gemini-3.5-flash'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
