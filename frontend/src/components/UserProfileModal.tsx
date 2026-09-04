import React, { useState, useEffect, useCallback } from 'react';
import {
  X, User, Key, CheckCircle2, AlertCircle,
  Loader2, Cpu, Zap, Eye, EyeOff, RefreshCw, Flame
} from 'lucide-react';
import type { UserProfile, QueryResponse } from '../types';

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile | null;
  lastResponse: QueryResponse | null;
  onUpdateUser?: (updatedUser: UserProfile) => void;
  initialTab?: 'details' | 'model' | 'usage';
}

interface UserAccountUsage {
  user_id: string;
  total_queries: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens_burned: number;
  total_cache_saved_tokens: number;
}

interface ProviderOption {
  id: string;
  name: string;
  icon: string;
  badge: string;
  models: string[];
  defaultBaseUrl: string;
  keyPlaceholder: string;
}

const PROVIDER_OPTIONS: ProviderOption[] = [
  {
    id: 'gemini',
    name: 'Google Gemini',
    icon: '✦',
    badge: 'Official',
    models: ['gemini-3.5-flash-lite', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash'],
    defaultBaseUrl: '',
    keyPlaceholder: 'Enter Gemini API Key (or leave empty for server default)...',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    icon: '🤖',
    badge: 'GPT-4o',
    models: ['gpt-4o-mini', 'gpt-4o', 'o3-mini', 'gpt-4-turbo'],
    defaultBaseUrl: '',
    keyPlaceholder: 'sk-...',
  },
  {
    id: 'claude',
    name: 'Anthropic Claude',
    icon: '🧠',
    badge: 'Claude 3.5',
    models: ['claude-3-5-haiku-20241022', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229'],
    defaultBaseUrl: '',
    keyPlaceholder: 'sk-ant-...',
  },
  {
    id: 'mistral',
    name: 'Mistral AI',
    icon: '🌪️',
    badge: 'Mistral',
    models: ['mistral-small-latest', 'mistral-large-latest', 'codestral-latest'],
    defaultBaseUrl: '',
    keyPlaceholder: 'Enter Mistral API Key...',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    icon: '⚡',
    badge: 'Reasoner',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    defaultBaseUrl: 'https://api.deepseek.com',
    keyPlaceholder: 'sk-...',
  },
  {
    id: 'qwen',
    name: 'Qwen (DashScope)',
    icon: '🐲',
    badge: 'Qwen 2.5',
    models: ['qwen-turbo', 'qwen-plus', 'qwen-max', 'qwen-2.5-72b-instruct'],
    defaultBaseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
    keyPlaceholder: 'sk-...',
  },
  {
    id: 'huggingface',
    name: 'Hugging Face',
    icon: '🤗',
    badge: 'Inference',
    models: ['meta-llama/Meta-Llama-3-70B-Instruct', 'mistralai/Mistral-7B-Instruct-v0.3', 'Qwen/Qwen2.5-72B-Instruct'],
    defaultBaseUrl: 'https://api-inference.huggingface.co/v1',
    keyPlaceholder: 'hf_...',
  },
  {
    id: 'ollama',
    name: 'Ollama (Local)',
    icon: '🦙',
    badge: 'Local / Self-Hosted',
    models: ['llama3.2', 'qwen2.5:7b', 'mistral', 'deepseek-r1:8b'],
    defaultBaseUrl: 'http://localhost:11434',
    keyPlaceholder: 'No API key required for local Ollama',
  },
];

export const UserProfileModal: React.FC<UserProfileModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  lastResponse,
  onUpdateUser,
  initialTab = 'details',
}) => {
  const [activeTab, setActiveTab] = useState<'details' | 'model' | 'usage'>(initialTab);

  // Dynamic Model State
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini');
  const [selectedModel, setSelectedModel] = useState<string>('gemini-3.5-flash-lite');
  const [apiKey, setApiKey] = useState<string>('');
  const [baseUrl, setBaseUrl] = useState<string>('');
  const [showApiKey, setShowApiKey] = useState<boolean>(false);
  const [isTestingConnection, setIsTestingConnection] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isSavingModel, setIsSavingModel] = useState<boolean>(false);
  const [modelSaveMessage, setModelSaveMessage] = useState<string>('');

  // Change Password Form State
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState('');
  const [passwordError, setPasswordError] = useState('');

  // Account-Wide Token Usage State
  const [accountUsage, setAccountUsage] = useState<UserAccountUsage | null>(null);
  const [isRefreshingUsage, setIsRefreshingUsage] = useState<boolean>(false);

  // Fetch Token Usage Function
  const fetchUsage = useCallback(async () => {
    if (!currentUser) return;
    const identifier = currentUser.user_id || currentUser.email;
    if (!identifier) return;

    try {
      setIsRefreshingUsage(true);
      const res = await fetch(`/api/v1/auth/user-usage/${encodeURIComponent(identifier)}`);
      if (res.ok) {
        const data: UserAccountUsage = await res.json();
        setAccountUsage(data);
      }
    } catch (err) {
      console.error('Error fetching account usage:', err);
    } finally {
      setIsRefreshingUsage(false);
    }
  }, [currentUser]);

  // Sync state when modal opens or currentUser updates
  useEffect(() => {
    if (currentUser) {
      const p = currentUser.llm_provider || 'gemini';
      setSelectedProvider(p);
      setSelectedModel(currentUser.llm_model || 'gemini-3.5-flash-lite');
      setApiKey(currentUser.llm_api_key || '');
      setBaseUrl(currentUser.llm_base_url || '');
    }
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [isOpen, currentUser, initialTab]);

  // Fetch token usage whenever modal opens or tab changes to usage
  useEffect(() => {
    if (isOpen && currentUser) {
      fetchUsage();
      const timer = setTimeout(fetchUsage, 600);
      return () => clearTimeout(timer);
    }
  }, [isOpen, currentUser, activeTab, fetchUsage, lastResponse]);

  if (!isOpen || !currentUser) return null;

  const currentPreset = PROVIDER_OPTIONS.find((p) => p.id === selectedProvider) || PROVIDER_OPTIONS[0];

  const handleProviderChange = (provId: string) => {
    setSelectedProvider(provId);
    const targetPreset = PROVIDER_OPTIONS.find((p) => p.id === provId) || PROVIDER_OPTIONS[0];
    setSelectedModel(targetPreset.models[0]);
    if (targetPreset.defaultBaseUrl) {
      setBaseUrl(targetPreset.defaultBaseUrl);
    } else {
      setBaseUrl('');
    }
    setTestResult(null);
    setModelSaveMessage('');
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setTestResult(null);
    try {
      const res = await fetch('/api/v1/auth/test-model-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          llm_provider: selectedProvider,
          llm_model: selectedModel,
          llm_api_key: apiKey.trim(),
          llm_base_url: baseUrl.trim(),
        }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        setTestResult({ success: true, message: data.message || 'Connection verified successfully!' });
      } else {
        setTestResult({ success: false, message: data.message || 'Connection test failed.' });
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || 'Error connecting to model provider.' });
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleSaveModelConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingModel(true);
    setModelSaveMessage('');
    try {
      const res = await fetch('/api/v1/auth/user-model-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: currentUser.user_id,
          llm_provider: selectedProvider,
          llm_model: selectedModel,
          llm_api_key: apiKey.trim(),
          llm_base_url: baseUrl.trim(),
        }),
      });

      const data = await res.json();
      if (!res.ok || data.status !== 'success') {
        throw new Error(data.detail || 'Failed to save model settings.');
      }

      const updatedUser: UserProfile = {
        ...currentUser,
        llm_provider: selectedProvider,
        llm_model: selectedModel,
        llm_api_key: apiKey.trim(),
        llm_base_url: baseUrl.trim(),
      };

      if (onUpdateUser) {
        onUpdateUser(updatedUser);
      }
      localStorage.setItem('bis_user', JSON.stringify(updatedUser));
      setModelSaveMessage('✓ AI Model settings saved and applied to active session!');
      setTimeout(() => setModelSaveMessage(''), 3000);
    } catch (err: any) {
      setModelSaveMessage(`❌ Error: ${err.message}`);
    } finally {
      setIsSavingModel(false);
    }
  };

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

  // Robust lifetime usage token calculation
  const tu = lastResponse?.token_usage;
  const promptTokens = (accountUsage && accountUsage.total_prompt_tokens > 0)
    ? accountUsage.total_prompt_tokens
    : (tu?.turn_prompt_tokens || tu?.prompt_tokens || 0);

  const completionTokens = (accountUsage && accountUsage.total_completion_tokens > 0)
    ? accountUsage.total_completion_tokens
    : (tu?.turn_completion_tokens || tu?.completion_tokens || 0);

  const totalTokensBurned = Math.max(
    accountUsage?.total_tokens_burned || 0,
    promptTokens + completionTokens,
    tu?.session_total_llm_tokens || 0,
    tu?.total_tokens || 0,
    (tu?.turn_prompt_tokens || 0) + (tu?.turn_completion_tokens || 0)
  );

  const totalQueries = Math.max(
    accountUsage?.total_queries || 0,
    lastResponse ? 1 : 0
  );

  const savedTokens = Math.max(
    accountUsage?.total_cache_saved_tokens || 0,
    tu?.session_total_saved_tokens || tu?.estimated_saved_tokens || 0
  );

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div
        className="animate-fade-in"
        style={{
          width: '100%',
          maxWidth: '680px',
          maxHeight: '90vh',
          overflowY: 'auto',
          background: 'var(--gemini-bg-card)',
          borderRadius: '24px',
          border: '1px solid var(--glass-border)',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)',
          padding: '28px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          position: 'relative',
        }}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            background: 'rgba(255, 255, 255, 0.05)',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '8px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <X size={18} />
        </button>

        {/* Modal Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '54px',
              height: '54px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #10B981, #059669)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF',
              fontSize: '1.4rem',
              fontWeight: 700,
              boxShadow: '0 4px 15px rgba(16, 185, 129, 0.3)',
            }}
          >
            {currentUser.full_name.charAt(0).toUpperCase()}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#FFFFFF', margin: 0 }}>
                {currentUser.full_name}
              </h2>
              {currentUser.is_admin && (
                <span style={{ fontSize: '0.72rem', background: 'rgba(245, 158, 11, 0.2)', border: '1px solid rgba(245, 158, 11, 0.4)', color: '#F59E0B', padding: '2px 8px', borderRadius: '10px', fontWeight: 700 }}>
                  ADMIN
                </span>
              )}
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
              {currentUser.email}
            </p>
          </div>
        </div>

        {/* 3-Tab Toggle Bar */}
        <div style={{ display: 'flex', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '16px', padding: '4px', border: '1px solid var(--glass-border)', gap: '4px' }}>
          <button
            onClick={() => setActiveTab('details')}
            style={{
              flex: 1,
              padding: '9px 12px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === 'details' ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
              color: activeTab === 'details' ? '#FFFFFF' : 'var(--text-muted)',
              fontWeight: activeTab === 'details' ? 600 : 500,
              fontSize: '0.84rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <User size={14} />
            Security
          </button>
          <button
            onClick={() => setActiveTab('model')}
            style={{
              flex: 1.2,
              padding: '9px 12px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === 'model' ? 'rgba(245, 158, 11, 0.15)' : 'transparent',
              color: activeTab === 'model' ? '#F59E0B' : 'var(--text-muted)',
              fontWeight: activeTab === 'model' ? 700 : 500,
              fontSize: '0.84rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <Cpu size={14} />
            AI Model & BYOK
          </button>
          <button
            onClick={() => setActiveTab('usage')}
            style={{
              flex: 1.2,
              padding: '9px 12px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === 'usage' ? 'rgba(239, 68, 68, 0.15)' : 'transparent',
              color: activeTab === 'usage' ? '#F87171' : 'var(--text-muted)',
              fontWeight: activeTab === 'usage' ? 700 : 500,
              fontSize: '0.84rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <Flame size={14} color={activeTab === 'usage' ? '#F87171' : 'var(--text-muted)'} />
            Token Analytics
          </button>
        </div>

        {/* TAB 1: Account Security & Password */}
        {activeTab === 'details' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Account ID</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#FFFFFF', fontFamily: 'monospace' }}>
                  {currentUser.user_id}
                </div>
              </div>
              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Active Role</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#10B981' }}>
                  {currentUser.is_admin ? 'Compliance Administrator' : 'Standard User'}
                </div>
              </div>
            </div>

            <form onSubmit={handleChangePassword} style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '18px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#FFFFFF', fontWeight: 600, fontSize: '0.92rem' }}>
                <Key size={16} color="var(--gemini-purple)" />
                Update Password
              </div>

              {passwordSuccess && (
                <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '10px', padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '8px', color: '#10B981', fontSize: '0.85rem' }}>
                  <CheckCircle2 size={15} />
                  {passwordSuccess}
                </div>
              )}

              {passwordError && (
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '10px', padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '8px', color: '#EF4444', fontSize: '0.85rem' }}>
                  <AlertCircle size={15} />
                  {passwordError}
                </div>
              )}

              <input
                type="password"
                placeholder="Current Password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
                style={{ width: '100%', background: 'var(--gemini-bg-input)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: '#FFFFFF', fontSize: '0.9rem', outline: 'none' }}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <input
                  type="password"
                  placeholder="New Password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  style={{ width: '100%', background: 'var(--gemini-bg-input)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: '#FFFFFF', fontSize: '0.9rem', outline: 'none' }}
                />
                <input
                  type="password"
                  placeholder="Confirm New Password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  style={{ width: '100%', background: 'var(--gemini-bg-input)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: '#FFFFFF', fontSize: '0.9rem', outline: 'none' }}
                />
              </div>

              <button
                type="submit"
                disabled={isChangingPassword}
                style={{ background: '#2563EB', color: '#FFFFFF', border: 'none', borderRadius: '12px', padding: '10px', fontWeight: 600, fontSize: '0.88rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginTop: '4px' }}
              >
                {isChangingPassword ? <Loader2 size={16} className="animate-spin" /> : 'Save New Password'}
              </button>
            </form>
          </div>
        )}

        {/* TAB 2: AI Model Selection & BYOK */}
        {activeTab === 'model' && (
          <form onSubmit={handleSaveModelConfig} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px', display: 'block' }}>
                1. Select AI Model Provider
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                {PROVIDER_OPTIONS.map((prov) => {
                  const isSelected = selectedProvider === prov.id;
                  return (
                    <button
                      key={prov.id}
                      type="button"
                      onClick={() => handleProviderChange(prov.id)}
                      style={{
                        padding: '12px 8px',
                        borderRadius: '14px',
                        background: isSelected ? 'rgba(245, 158, 11, 0.15)' : 'var(--gemini-bg-main)',
                        border: isSelected ? '1px solid #F59E0B' : '1px solid var(--glass-border)',
                        color: isSelected ? '#FFFFFF' : 'var(--text-subtle)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '6px',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <span style={{ fontSize: '1.3rem' }}>{prov.icon}</span>
                      <span style={{ fontSize: '0.8rem', fontWeight: isSelected ? 700 : 500, textAlign: 'center' }}>
                        {prov.name}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Model Selector */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                  2. Select Model
                </label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'var(--gemini-bg-input)',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '12px',
                    padding: '10px 14px',
                    color: '#FFFFFF',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                >
                  {currentPreset.models.map((m) => (
                    <option key={m} value={m} style={{ background: '#1e293b' }}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                  Custom Model ID (Optional)
                </label>
                <input
                  type="text"
                  placeholder="Or enter custom model name..."
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'var(--gemini-bg-input)',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '12px',
                    padding: '10px 14px',
                    color: '#FFFFFF',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                />
              </div>
            </div>

            {/* API Key (BYOK) */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                  3. {currentPreset.name} API Key (BYOK)
                </label>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-subtle)' }}>
                  {selectedProvider === 'gemini' ? 'Leave empty to use server default' : 'Stored securely for your account'}
                </span>
              </div>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <input
                  type={showApiKey ? 'text' : 'password'}
                  placeholder={currentPreset.keyPlaceholder}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'var(--gemini-bg-input)',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '12px',
                    padding: '10px 42px 10px 14px',
                    color: '#FFFFFF',
                    fontSize: '0.88rem',
                    outline: 'none',
                    fontFamily: showApiKey ? 'monospace' : 'inherit',
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                  }}
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Base URL (Optional / Custom Endpoints) */}
            <div>
              <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                4. Base URL / Endpoint (Optional)
              </label>
              <input
                type="text"
                placeholder={currentPreset.defaultBaseUrl || 'Default vendor API endpoint'}
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                style={{
                  width: '100%',
                  background: 'var(--gemini-bg-input)',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '12px',
                  padding: '10px 14px',
                  color: '#FFFFFF',
                  fontSize: '0.88rem',
                  outline: 'none',
                  fontFamily: 'monospace',
                }}
              />
            </div>

            {/* Test Result Message */}
            {testResult && (
              <div
                style={{
                  background: testResult.success ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                  border: `1px solid ${testResult.success ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)'}`,
                  borderRadius: '10px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.85rem',
                  color: testResult.success ? '#10B981' : '#EF4444',
                }}
              >
                {testResult.success ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                <span>{testResult.message}</span>
              </div>
            )}

            {/* Save Status Message */}
            {modelSaveMessage && (
              <div
                style={{
                  background: modelSaveMessage.startsWith('✓') ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  border: `1px solid ${modelSaveMessage.startsWith('✓') ? '#F59E0B' : '#EF4444'}`,
                  borderRadius: '10px',
                  padding: '10px 14px',
                  fontSize: '0.85rem',
                  color: modelSaveMessage.startsWith('✓') ? '#F59E0B' : '#EF4444',
                  fontWeight: 600,
                }}
              >
                {modelSaveMessage}
              </div>
            )}

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={isTestingConnection}
                style={{
                  flex: 1,
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '12px',
                  padding: '11px',
                  color: '#FFFFFF',
                  fontWeight: 600,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {isTestingConnection ? <Loader2 size={16} className="animate-spin" /> : '⚡ Test Connection'}
              </button>

              <button
                type="submit"
                disabled={isSavingModel}
                style={{
                  flex: 1.5,
                  background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                  color: '#000000',
                  border: 'none',
                  borderRadius: '12px',
                  padding: '11px',
                  fontWeight: 700,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  boxShadow: '0 4px 14px rgba(245, 158, 11, 0.3)',
                }}
              >
                {isSavingModel ? <Loader2 size={16} className="animate-spin" /> : '✓ Save & Apply Model'}
              </button>
            </div>
          </form>
        )}

        {/* TAB 3: Account Token Analytics */}
        {activeTab === 'usage' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {/* Prominent High-Impact Total Tokens Burned Banner */}
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(245, 158, 11, 0.15) 100%)',
                border: '1px solid rgba(245, 158, 11, 0.4)',
                borderRadius: '20px',
                padding: '18px 22px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                boxShadow: '0 4px 20px rgba(245, 158, 11, 0.1)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div
                  style={{
                    width: '46px',
                    height: '46px',
                    borderRadius: '14px',
                    background: 'rgba(239, 68, 68, 0.2)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Flame size={24} color="#EF4444" />
                </div>
                <div>
                  <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: '#F59E0B', fontWeight: 700 }}>
                    Lifetime Account Consumption
                  </div>
                  <div style={{ fontSize: '1.85rem', fontWeight: 800, color: '#FFFFFF', letterSpacing: '-0.5px', lineHeight: 1.2, marginTop: '2px' }}>
                    {totalTokensBurned.toLocaleString()} <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-muted)' }}>tokens</span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={fetchUsage}
                disabled={isRefreshingUsage}
                title="Refresh metrics directly from Supabase PostgreSQL"
                style={{
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '12px',
                  padding: '8px 14px',
                  color: '#FFFFFF',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <RefreshCw size={13} className={isRefreshingUsage ? 'animate-spin' : ''} />
                <span>{isRefreshingUsage ? 'Syncing...' : 'Sync'}</span>
              </button>
            </div>

            {/* Metric Breakdown Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Prompt Tokens</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#4285F4', marginTop: '4px' }}>
                  {promptTokens.toLocaleString()}
                </div>
              </div>

              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Completion Tokens</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#9B51E0', marginTop: '4px' }}>
                  {completionTokens.toLocaleString()}
                </div>
              </div>

              <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Queries</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#10B981', marginTop: '4px' }}>
                  {totalQueries.toLocaleString()}
                </div>
              </div>
            </div>

            {/* Visual Token Distribution Progress Bar */}
            <div style={{ background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '18px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#FFFFFF' }}>Token Distribution Breakdown</span>
                <span style={{ fontSize: '0.75rem', color: '#10B981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Zap size={12} /> Cache Saved: {savedTokens.toLocaleString()}
                </span>
              </div>

              <div style={{ height: '14px', width: '100%', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden', display: 'flex' }}>
                <div style={{ width: `${Math.min(100, Math.max(5, (promptTokens / (totalTokensBurned || 1)) * 100))}%`, background: '#4285F4' }} title={`Prompt Tokens: ${promptTokens.toLocaleString()}`} />
                <div style={{ width: `${Math.min(100, Math.max(5, (completionTokens / (totalTokensBurned || 1)) * 100))}%`, background: '#9B51E0' }} title={`Completion Tokens: ${completionTokens.toLocaleString()}`} />
                {savedTokens > 0 && (
                  <div style={{ width: `${Math.min(100, Math.max(5, (savedTokens / (totalTokensBurned + savedTokens || 1)) * 100))}%`, background: '#10B981' }} title={`Saved Cache Tokens: ${savedTokens.toLocaleString()}`} />
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', fontSize: '0.78rem', color: 'var(--text-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#4285F4' }} />
                  <span>Prompt ({promptTokens.toLocaleString()})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#9B51E0' }} />
                  <span>Completion ({completionTokens.toLocaleString()})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#10B981' }} />
                  <span>Saved Cache ({savedTokens.toLocaleString()})</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
