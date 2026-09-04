import React, { useState, useEffect } from 'react';
import { X, Search, Zap, RefreshCw, Key } from 'lucide-react';
import type { AuditLogRecord } from '../types';
import { getApiUrl } from '../config';


interface AuditLedgerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuditLedgerModal: React.FC<AuditLedgerModalProps> = ({ isOpen, onClose }) => {
  const [logs, setLogs] = useState<AuditLogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [selectedRecord, setSelectedRecord] = useState<AuditLogRecord | null>(null);

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
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(19, 19, 20, 0.88)', backdropFilter: 'blur(12px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '32px' }}>
      <div style={{ background: 'var(--gemini-bg-card)', border: '1px solid var(--glass-border)', borderRadius: '24px', width: '1000px', height: '85vh', display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px', position: 'relative' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ padding: '10px', borderRadius: '50%', background: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B' }}>
              <Key size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#FFFFFF' }}>Immutable Supabase Audit Ledger</h2>
                <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '12px', background: 'rgba(245, 158, 11, 0.2)', border: '1px solid rgba(245, 158, 11, 0.4)', color: '#F59E0B', fontWeight: 700, textTransform: 'uppercase' }}>
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
              style={{ padding: '8px 16px', borderRadius: '20px', background: 'rgba(255, 255, 255, 0.06)', border: '1px solid var(--glass-border)', color: 'var(--text-subtle)', fontSize: '0.82rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <RefreshCw size={14} className={isLoading ? 'gemini-pulse' : ''} />
              Refresh
            </button>
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <X size={22} />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '20px', padding: '10px 18px' }}>
          <Search size={18} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search by User Query, Session ID, or Intent..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            style={{ background: 'none', border: 'none', outline: 'none', color: '#FFF', fontSize: '0.88rem', width: '100%' }}
          />
        </div>


        {/* Table & Detail Split */}
        <div style={{ flex: 1, display: 'flex', gap: '16px', overflow: 'hidden' }}>
          {/* Logs List Table */}
          <div style={{ flex: 1, overflowY: 'auto', border: '1px solid var(--glass-border)', borderRadius: '12px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'rgba(30, 41, 59, 0.6)', color: 'var(--text-muted)', borderBottom: '1px solid var(--glass-border)' }}>
                  <th style={{ padding: '12px 14px' }}>Timestamp</th>
                  <th style={{ padding: '12px 14px' }}>Session ID</th>
                  <th style={{ padding: '12px 14px' }}>User Query</th>
                  <th style={{ padding: '12px 14px' }}>Cache</th>
                  <th style={{ padding: '12px 14px' }}>Latency</th>
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
                          borderBottom: '1px solid var(--glass-border)',
                          background: isSelected ? 'rgba(245, 158, 11, 0.12)' : 'transparent',
                          cursor: 'pointer',
                        }}
                      >
                        <td style={{ padding: '12px 14px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }} className="mono">
                          {log.timestamp_utc ? new Date(log.timestamp_utc).toLocaleTimeString() : 'N/A'}
                        </td>
                        <td style={{ padding: '12px 14px', color: '#06B6D4', fontWeight: 600 }}>{log.session_id}</td>
                        <td style={{ padding: '12px 14px', color: '#FFF', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {log.user_query}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          {log.cache_hit ? (
                            <span style={{ color: '#F59E0B', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
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
            <div className="glass-panel" style={{ width: '380px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto' }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#F59E0B' }}>Cryptographic SHA-256 Verification</h4>
              
              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Interaction ID:</span>
                <div className="mono" style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '6px', borderRadius: '6px', color: '#06B6D4', marginTop: '4px', wordBreak: 'break-all' }}>
                  {selectedRecord.interaction_id}
                </div>
              </div>

              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Prompt SHA-256 Hash:</span>
                <div className="mono" style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '6px', borderRadius: '6px', color: '#10B981', marginTop: '4px', wordBreak: 'break-all' }}>
                  {selectedRecord.prompt_sha256 || 'N/A'}
                </div>
              </div>

              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Payload SHA-256 Hash:</span>
                <div className="mono" style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '6px', borderRadius: '6px', color: '#F59E0B', marginTop: '4px', wordBreak: 'break-all' }}>
                  {selectedRecord.payload_sha256 || 'N/A'}
                </div>
              </div>

              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Detected Intent:</span>
                <div style={{ fontWeight: 600, color: '#FFF', marginTop: '4px' }}>
                  {selectedRecord.intent || 'N/A'}
                </div>
              </div>

              <div style={{ fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>LLM Model Checkpoint:</span>
                <div style={{ fontWeight: 600, color: '#06B6D4', marginTop: '4px' }}>
                  {selectedRecord.model_checkpoint || 'gemini-3.5-flash-lite'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
