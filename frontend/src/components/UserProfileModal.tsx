import React, { useState } from 'react';
import { X, User, Key, BarChart2, Shield, CheckCircle2, AlertCircle, Loader2, Cpu, Zap } from 'lucide-react';
import type { UserProfile, QueryResponse } from '../types';


interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile | null;
  lastResponse: QueryResponse | null;
}

interface UserAccountUsage {
  user_id: string;
  total_queries: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens_burned: number;
  total_cache_saved_tokens: number;
}

export const UserProfileModal: React.FC<UserProfileModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  lastResponse,
}) => {
  const [activeTab, setActiveTab] = useState<'details' | 'usage'>('details');

  // Change Password Form State
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState('');
  const [passwordError, setPasswordError] = useState('');

  // Account-Wide Token Usage State
  const [accountUsage, setAccountUsage] = useState<UserAccountUsage | null>(null);

  React.useEffect(() => {
    if (isOpen && currentUser && activeTab === 'usage') {
      const fetchUsage = () => {
        fetch(`/api/v1/auth/user-usage/${encodeURIComponent(currentUser.user_id)}`)
          .then((res) => (res.ok ? res.json() : null))
          .then((data: UserAccountUsage | null) => {
            if (data) setAccountUsage(data);
          })
          .catch((err) => console.error('Error fetching account usage:', err));
      };

      fetchUsage();
      // Brief delay refetch to capture background audit database writes
      const timer = setTimeout(fetchUsage, 800);
      return () => clearTimeout(timer);
    }
  }, [isOpen, currentUser, activeTab, lastResponse]);

  if (!isOpen || !currentUser) return null;

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordSuccess('');
    setPasswordError('');

    if (newPassword !== confirmPassword) {
      setPasswordError('New password and confirmation do not match.');
      return;
    }

    if (newPassword.length < 6) {
      setPasswordError('New password must be at least 6 characters.');
      return;
    }

    setIsChangingPassword(true);

    try {
      const res = await fetch('/api/v1/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: currentUser.user_id,
          old_password: oldPassword,
          new_password: newPassword,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.status !== 'success') {
        throw new Error(data.detail || data.message || 'Failed to change password.');
      }

      setPasswordSuccess('Password updated successfully!');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordError(err.message || 'Error updating password.');
    } finally {
      setIsChangingPassword(false);
    }
  };

  const tu = lastResponse?.token_usage;
  const promptTokens = accountUsage?.total_prompt_tokens ? accountUsage.total_prompt_tokens : (tu?.turn_prompt_tokens ?? 0);
  const completionTokens = accountUsage?.total_completion_tokens ? accountUsage.total_completion_tokens : (tu?.turn_completion_tokens ?? 0);
  const totalTokensBurned = Math.max(
    accountUsage?.total_tokens_burned || 0,
    tu?.session_total_llm_tokens || 0,
    (tu?.turn_prompt_tokens || 0) + (tu?.turn_completion_tokens || 0)
  );
  const savedTokens = Math.max(accountUsage?.total_cache_saved_tokens || 0, tu?.session_total_saved_tokens || 0);
  const totalQueries = Math.max(accountUsage?.total_queries || 0, tu ? 1 : 0);
  const activeModel = lastResponse?.llm_model || 'gemini-3.5-flash-lite';
  const llmProvider = lastResponse?.llm_provider || 'Google Gemini API';
  const embedProvider = tu?.embedding_provider || 'MistralAIEmbeddings';




  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(19, 19, 20, 0.85)', backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '20px' }}>
      <div style={{ background: 'var(--gemini-bg-card)', border: '1px solid var(--glass-border)', borderRadius: '24px', width: '560px', maxWidth: '95vw', maxHeight: '90vh', overflowY: 'auto', padding: '28px', display: 'flex', flexDirection: 'column', gap: '20px', position: 'relative', boxShadow: '0 12px 40px rgba(0, 0, 0, 0.5)' }}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{ position: 'absolute', top: '20px', right: '20px', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
        >
          <X size={20} />
        </button>

        {/* User Badge Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ width: '52px', height: '52px', borderRadius: '50%', background: 'linear-gradient(135deg, #A855F7 0%, #EC4899 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFFFFF', fontWeight: 700, fontSize: '1.4rem', boxShadow: '0 0 20px rgba(168, 85, 247, 0.4)' }}>
            {currentUser.full_name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              {currentUser.full_name}
            </h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
              {currentUser.email}
            </p>
          </div>
        </div>

        {/* Tab Toggle Bar */}
        <div style={{ display: 'flex', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '16px', padding: '4px', border: '1px solid var(--glass-border)' }}>
          <button
            onClick={() => setActiveTab('details')}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === 'details' ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
              color: activeTab === 'details' ? '#FFFFFF' : 'var(--text-muted)',
              fontWeight: activeTab === 'details' ? 600 : 500,
              fontSize: '0.88rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <User size={15} />
            Account Details & Security
          </button>
          <button
            onClick={() => setActiveTab('usage')}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === 'usage' ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
              color: activeTab === 'usage' ? '#FFFFFF' : 'var(--text-muted)',
              fontWeight: activeTab === 'usage' ? 600 : 500,
              fontSize: '0.88rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <BarChart2 size={15} />
            Token Usage & AI Model
          </button>
        </div>

        {/* TAB 1: Account Details & Change Password */}
        {activeTab === 'details' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Account Info Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>User ID</div>
                <div style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--gemini-blue)', fontFamily: 'monospace' }}>
                  {currentUser.user_id}
                </div>
              </div>

              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Account Status</div>
                <div style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--gemini-green)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Shield size={14} /> Verified Active
                </div>
              </div>
            </div>

            {/* Change Password Form */}
            <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '18px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.95rem', fontWeight: 600, color: '#FFFFFF' }}>
                <Key size={16} color="var(--gemini-purple)" />
                Change Account Password
              </div>

              {passwordSuccess && (
                <div style={{ padding: '10px 14px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#10B981', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 size={15} /> {passwordSuccess}
                </div>
              )}

              {passwordError && (
                <div style={{ padding: '10px 14px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#EF4444', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertCircle size={15} /> {passwordError}
                </div>
              )}

              <form onSubmit={handleChangePassword} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '4px', display: 'block' }}>Current Password</label>
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    required
                    style={{ width: '100%', background: 'rgba(0, 0, 0, 0.3)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: '#FFF', fontSize: '0.88rem', outline: 'none' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '4px', display: 'block' }}>New Password</label>
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    style={{ width: '100%', background: 'rgba(0, 0, 0, 0.3)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: '#FFF', fontSize: '0.88rem', outline: 'none' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '4px', display: 'block' }}>Confirm New Password</label>
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    style={{ width: '100%', background: 'rgba(0, 0, 0, 0.3)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: '#FFF', fontSize: '0.88rem', outline: 'none' }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isChangingPassword}
                  style={{
                    marginTop: '6px',
                    padding: '10px',
                    borderRadius: '20px',
                    background: 'var(--gemini-sparkle-gradient)',
                    border: 'none',
                    color: '#FFFFFF',
                    fontWeight: 600,
                    fontSize: '0.88rem',
                    cursor: isChangingPassword ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                  }}
                >
                  {isChangingPassword ? <Loader2 size={16} className="gemini-pulse" /> : <Key size={15} />}
                  {isChangingPassword ? 'Updating Password...' : 'Update Password'}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* TAB 2: Token Usage & AI Model Graph */}
        {activeTab === 'usage' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Active Model Badges */}
            <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '18px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-subtle)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Cpu size={15} color="var(--gemini-blue)" /> Active AI Models & Provider Infrastructure
              </div>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <div style={{ padding: '6px 12px', borderRadius: '16px', background: 'rgba(66, 133, 244, 0.15)', border: '1px solid rgba(66, 133, 244, 0.3)', color: '#FFFFFF', fontSize: '0.82rem', fontWeight: 500 }}>
                  LLM: <strong>{activeModel}</strong> ({llmProvider})
                </div>
                <div style={{ padding: '6px 12px', borderRadius: '16px', background: 'rgba(155, 81, 224, 0.15)', border: '1px solid rgba(155, 81, 224, 0.3)', color: '#FFFFFF', fontSize: '0.82rem', fontWeight: 500 }}>
                  Embeddings: <strong>{embedProvider}</strong>
                </div>
              </div>
            </div>

            {/* Account-Wide Token Metric Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Account Token Burn</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#FFFFFF', marginTop: '2px' }}>
                  {totalTokensBurned.toLocaleString()}
                </div>
              </div>

              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Account Prompt/Comp</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--gemini-blue)', marginTop: '2px' }}>
                  {promptTokens.toLocaleString()} / {completionTokens.toLocaleString()}
                </div>
              </div>

              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Account Queries</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--gemini-green)', marginTop: '2px' }}>
                  {totalQueries.toLocaleString()}
                </div>
              </div>
            </div>

            {/* Visual Token Consumption SVG Bar Graph */}
            <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '18px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#FFFFFF' }}>Lifetime Account Token Distribution</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--gemini-purple)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Zap size={12} /> Cache Saved: {savedTokens.toLocaleString()}
                </span>
              </div>

              {/* Stacked Progress Bar */}
              <div style={{ height: '14px', width: '100%', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden', display: 'flex' }}>
                <div style={{ width: `${(promptTokens / (totalTokensBurned || 1)) * 100}%`, background: '#4285F4' }} title={`Prompt Tokens: ${promptTokens}`} />
                <div style={{ width: `${(completionTokens / (totalTokensBurned || 1)) * 100}%`, background: '#9B51E0' }} title={`Completion Tokens: ${completionTokens}`} />
                <div style={{ width: `${(savedTokens / (totalTokensBurned + savedTokens || 1)) * 100}%`, background: '#10B981' }} title={`Saved Cache Tokens: ${savedTokens}`} />
              </div>


              {/* Graph Legend */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', fontSize: '0.78rem', color: 'var(--text-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#4285F4' }} />
                  <span>Prompt ({promptTokens})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#9B51E0' }} />
                  <span>Completion ({completionTokens})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#10B981' }} />
                  <span>Saved Cache ({savedTokens})</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
