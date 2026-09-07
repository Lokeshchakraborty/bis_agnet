import React, { useState, useEffect, useCallback } from 'react';
import {
  X, User, Key, CheckCircle2, AlertCircle,
  Loader2, Cpu, Zap, Eye, EyeOff, RefreshCw, Flame,
  Sun, Moon, Palette
} from 'lucide-react';
import type { UserProfile, QueryResponse } from '../types';
import { getApiUrl } from '../config';

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile | null;
  lastResponse: QueryResponse | null;
  onUpdateUser?: (updatedUser: UserProfile) => void;
  initialTab?: 'details' | 'model' | 'usage';
  theme?: 'light' | 'dark';
  onSelectTheme?: (theme: 'light' | 'dark') => void;
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
    models: ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.6-flash', 'gemini-flash-latest', 'gemini-pro-latest'],
    defaultBaseUrl: '',
    keyPlaceholder: 'Enter Gemini API Key (or leave empty for server default)...',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    icon: '🤖',
    badge: 'GPT-4o',
    models: ['gpt-4o', 'gpt-4o-mini', 'o3-mini', 'gpt-4-turbo'],
    defaultBaseUrl: '',
    keyPlaceholder: 'sk-...',
  },
  {
    id: 'mistral',
    name: 'Mistral AI',
    icon: '🌪️',
    badge: 'Mistral',
    models: ['mistral-large-latest', 'mistral-small-latest', 'open-mixtral-8x22b', 'codestral-latest'],
    defaultBaseUrl: '',
    keyPlaceholder: 'Enter Mistral API Key...',
  },
  {
    id: 'claude',
    name: 'Anthropic Claude',
    icon: '🧠',
    badge: 'Claude 3.5',
    models: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'],
    defaultBaseUrl: '',
    keyPlaceholder: 'sk-ant-...',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    icon: '🌐',
    badge: 'Multi-LLM',
    models: ['anthropic/claude-3.5-sonnet', 'deepseek/deepseek-r1', 'deepseek/deepseek-chat', 'meta-llama/llama-3.3-70b-instruct', 'qwen/qwen-2.5-72b-instruct'],
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
    keyPlaceholder: 'sk-or-...',
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
    id: 'ollama',
    name: 'Ollama (Local)',
    icon: '🦙',
    badge: 'Local / $0 Cost',
    models: ['llama3.2', 'llama3.1', 'mistral', 'qwen2.5', 'phi4', 'gemma2', 'deepseek-r1:8b'],
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
  theme = 'light',
  onSelectTheme,
}) => {
  const [activeTab, setActiveTab] = useState<'details' | 'model' | 'usage'>(initialTab);

  // Dynamic Model State
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini');
  const [selectedModel, setSelectedModel] = useState<string>('gemini-3.5-flash');
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
      const res = await fetch(getApiUrl(`/api/v1/auth/user-usage/${encodeURIComponent(identifier)}`));
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
      let m = currentUser.llm_model || 'gemini-3.5-flash';
      if (m.startsWith('gemini-2.5') || m.startsWith('gemini-2.0') || m.startsWith('gemini-1.5') || m.startsWith('gemini-1.0')) {
        m = 'gemini-3.5-flash';
      }
      setSelectedModel(m);
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
    if (provId === 'ollama') {
      setApiKey('');
    }
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
      const res = await fetch(getApiUrl('/api/v1/auth/test-model-connection'), {
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
        setTestResult({ success: false, message: data.detail || data.message || 'Connection test failed.' });
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
      const res = await fetch(getApiUrl('/api/v1/auth/user-model-config'), {
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
      const res = await fetch(getApiUrl('/api/v1/auth/change-password'), {
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
  const promptTokens = accountUsage?.total_prompt_tokens ?? (tu?.turn_prompt_tokens || tu?.prompt_tokens || 0);
  const completionTokens = accountUsage?.total_completion_tokens ?? (tu?.turn_completion_tokens || tu?.completion_tokens || 0);

  const totalTokensBurned = accountUsage?.total_tokens_burned ?? (promptTokens + completionTokens);

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
        background: 'rgba(15, 23, 42, 0.45)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div
        className="animate-fade-in modal-responsive-card"
        style={{
          width: '100%',
          maxWidth: '680px',
          maxHeight: '90vh',
          overflowY: 'auto',
          background: theme === 'dark' ? '#1E1F20' : '#FFFFFF',
          borderRadius: '24px',
          border: '1px solid var(--glass-border)',
          boxShadow: theme === 'dark' ? '0 20px 50px rgba(0, 0, 0, 0.6)' : '0 20px 45px -10px rgba(0, 0, 0, 0.15)',
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
            background: theme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)',
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
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)', margin: 0 }}>
                {currentUser.full_name}
              </h2>
              {currentUser.is_admin && (
                <span style={{ fontSize: '0.72rem', background: '#FEF3C7', border: '1px solid #FDE68A', color: '#B45309', padding: '2px 8px', borderRadius: '10px', fontWeight: 700 }}>
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
        <div style={{ display: 'flex', background: theme === 'dark' ? '#131314' : '#F1F5F9', borderRadius: '16px', padding: '4px', border: '1px solid var(--glass-border)', gap: '4px' }}>
          <button
            onClick={() => setActiveTab('details')}
            style={{
              flex: 1,
              padding: '9px 12px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === 'details' ? (theme === 'dark' ? '#282A2C' : '#FFFFFF') : 'transparent',
              color: activeTab === 'details' ? (theme === 'dark' ? '#FFFFFF' : '#0F172A') : 'var(--text-muted)',
              fontWeight: activeTab === 'details' ? 600 : 500,
              fontSize: '0.84rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: activeTab === 'details' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            <User size={14} />
            Settings
          </button>
          <button
            onClick={() => setActiveTab('model')}
            style={{
              flex: 1.2,
              padding: '9px 12px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === 'model' ? (theme === 'dark' ? '#282A2C' : '#FFFFFF') : 'transparent',
              color: activeTab === 'model' ? (theme === 'dark' ? '#60A5FA' : '#2563EB') : 'var(--text-muted)',
              fontWeight: activeTab === 'model' ? 700 : 500,
              fontSize: '0.84rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: activeTab === 'model' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            <Cpu size={14} color={activeTab === 'model' ? (theme === 'dark' ? '#60A5FA' : '#2563EB') : 'var(--text-muted)'} />
            AI Model & BYOK
          </button>
          <button
            onClick={() => setActiveTab('usage')}
            style={{
              flex: 1.2,
              padding: '9px 12px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === 'usage' ? (theme === 'dark' ? '#282A2C' : '#FFFFFF') : 'transparent',
              color: activeTab === 'usage' ? (theme === 'dark' ? '#F87171' : '#DC2626') : 'var(--text-muted)',
              fontWeight: activeTab === 'usage' ? 700 : 500,
              fontSize: '0.84rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: activeTab === 'usage' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            <Flame size={14} color={activeTab === 'usage' ? (theme === 'dark' ? '#F87171' : '#DC2626') : 'var(--text-muted)'} />
            Token Analytics
          </button>
        </div>

        {/* TAB 1: Account Security & Appearance */}
        {activeTab === 'details' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {/* Theme & Appearance Setting */}
            {onSelectTheme && (
              <div style={{ background: theme === 'dark' ? '#131314' : '#F8FAFC', border: '1px solid var(--glass-border)', borderRadius: '18px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)', fontWeight: 600, fontSize: '0.92rem' }}>
                    <Palette size={16} color="var(--gemini-cyan)" />
                    Workspace Theme & Appearance
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Applies to chatbot & workspace
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <button
                    type="button"
                    onClick={() => onSelectTheme('light')}
                    style={{
                      padding: '12px',
                      borderRadius: '14px',
                      border: theme === 'light' ? '2px solid #2563EB' : '1px solid var(--glass-border)',
                      background: theme === 'light' ? '#EFF6FF' : '#1E1F20',
                      color: theme === 'light' ? '#2563EB' : 'var(--text-muted)',
                      fontWeight: theme === 'light' ? 700 : 500,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      fontSize: '0.88rem',
                      boxShadow: theme === 'light' ? '0 2px 8px rgba(37, 99, 235, 0.15)' : 'none',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Sun size={16} color={theme === 'light' ? '#2563EB' : 'var(--text-muted)'} />
                    <span>Light Mode</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onSelectTheme('dark')}
                    style={{
                      padding: '12px',
                      borderRadius: '14px',
                      border: theme === 'dark' ? '2px solid #3B82F6' : '1px solid var(--glass-border)',
                      background: theme === 'dark' ? '#282A2C' : '#FFFFFF',
                      color: theme === 'dark' ? '#93C5FD' : 'var(--text-muted)',
                      fontWeight: theme === 'dark' ? 700 : 500,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      fontSize: '0.88rem',
                      boxShadow: theme === 'dark' ? '0 2px 8px rgba(59, 130, 246, 0.25)' : 'none',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Moon size={16} color={theme === 'dark' ? '#93C5FD' : 'var(--text-muted)'} />
                    <span>Dark Mode</span>
                  </button>
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: theme === 'dark' ? '#131314' : '#F8FAFC', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Account ID</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)', fontFamily: 'monospace' }}>
                  {currentUser.user_id}
                </div>
              </div>
              <div style={{ background: theme === 'dark' ? '#131314' : '#F8FAFC', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Active Role</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#059669' }}>
                  {currentUser.is_admin ? 'Compliance Administrator' : 'Standard User'}
                </div>
              </div>
            </div>

            <form onSubmit={handleChangePassword} style={{ background: theme === 'dark' ? '#131314' : '#F8FAFC', border: '1px solid var(--glass-border)', borderRadius: '18px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)', fontWeight: 600, fontSize: '0.92rem' }}>
                <Key size={16} color="#7C3AED" />
                Update Password
              </div>

              {passwordSuccess && (
                <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '10px', padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '8px', color: '#059669', fontSize: '0.85rem' }}>
                  <CheckCircle2 size={15} />
                  {passwordSuccess}
                </div>
              )}

              {passwordError && (
                <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '10px', padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '8px', color: '#DC2626', fontSize: '0.85rem' }}>
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
                style={{ width: '100%', background: theme === 'dark' ? '#1E1F20' : '#FFFFFF', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)', fontSize: '0.9rem', outline: 'none' }}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <input
                  type="password"
                  placeholder="New Password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  style={{ width: '100%', background: theme === 'dark' ? '#1E1F20' : '#FFFFFF', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)', fontSize: '0.9rem', outline: 'none' }}
                />
                <input
                  type="password"
                  placeholder="Confirm New Password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  style={{ width: '100%', background: theme === 'dark' ? '#1E1F20' : '#FFFFFF', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px 14px', color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)', fontSize: '0.9rem', outline: 'none' }}
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
              <div className="modal-provider-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
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
                        background: isSelected ? (theme === 'dark' ? 'rgba(37, 99, 235, 0.25)' : '#EFF6FF') : (theme === 'dark' ? '#131314' : '#F8FAFC'),
                        border: isSelected ? '1px solid #2563EB' : '1px solid var(--glass-border)',
                        boxShadow: isSelected ? '0 2px 8px rgba(37, 99, 235, 0.15)' : 'none',
                        color: isSelected ? (theme === 'dark' ? '#93C5FD' : '#1D4ED8') : (theme === 'dark' ? '#E2E8F0' : 'var(--text-main)'),
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '6px',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <span style={{ fontSize: '1.3rem' }}>{prov.icon}</span>
                      <span style={{ fontSize: '0.8rem', fontWeight: isSelected ? 700 : 500, textAlign: 'center', color: isSelected ? (theme === 'dark' ? '#93C5FD' : '#1D4ED8') : 'inherit' }}>
                        {prov.name}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Model Selector */}
            <div className="modal-grid-2col" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                  2. Select Model
                </label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  style={{
                    width: '100%',
                    background: theme === 'dark' ? '#131314' : '#FFFFFF',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '12px',
                    padding: '10px 14px',
                    color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                >
                  {currentPreset.models.map((m) => (
                    <option key={m} value={m} style={{ background: theme === 'dark' ? '#1E1F20' : '#FFFFFF', color: theme === 'dark' ? '#FFFFFF' : '#0F172A' }}>
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
                    background: theme === 'dark' ? '#131314' : '#FFFFFF',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '12px',
                    padding: '10px 14px',
                    color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)',
                    fontSize: '0.88rem',
                    outline: 'none',
                  }}
                />
              </div>
            </div>

            {/* API Key (BYOK) */}
            {selectedProvider === 'ollama' ? (
              <div
                style={{
                  background: '#ECFDF5',
                  border: '1px solid #A7F3D0',
                  borderRadius: '14px',
                  padding: '14px 16px',
                  color: '#059669',
                  fontSize: '0.86rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <CheckCircle2 size={18} />
                <div>
                  <div style={{ fontWeight: 700, color: '#0F172A' }}>Local Ollama Selected (No API Key Required)</div>
                  <div style={{ fontSize: '0.78rem', color: '#047857', marginTop: '2px' }}>
                    Connects directly to your local server at <code>{baseUrl || 'http://localhost:11434'}</code>. Make sure <code>ollama serve</code> is running.
                  </div>
                </div>
              </div>
            ) : (
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
                      background: theme === 'dark' ? '#131314' : '#FFFFFF',
                      border: '1px solid var(--glass-border)',
                      borderRadius: '12px',
                      padding: '10px 42px 10px 14px',
                      color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)',
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
            )}

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
                  background: theme === 'dark' ? '#131314' : '#FFFFFF',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '12px',
                  padding: '10px 14px',
                  color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)',
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
                  background: testResult.success ? '#ECFDF5' : '#FEF2F2',
                  border: `1px solid ${testResult.success ? '#A7F3D0' : '#FECACA'}`,
                  borderRadius: '10px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.85rem',
                  color: testResult.success ? '#059669' : '#DC2626',
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
                  background: modelSaveMessage.startsWith('✓') ? '#EFF6FF' : '#FEF2F2',
                  border: `1px solid ${modelSaveMessage.startsWith('✓') ? '#BFDBFE' : '#FECACA'}`,
                  borderRadius: '10px',
                  padding: '10px 14px',
                  fontSize: '0.85rem',
                  color: modelSaveMessage.startsWith('✓') ? '#1D4ED8' : '#DC2626',
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
                  background: theme === 'dark' ? 'rgba(59, 130, 246, 0.15)' : '#EFF6FF',
                  border: '1px solid #BFDBFE',
                  borderRadius: '12px',
                  padding: '11px',
                  color: theme === 'dark' ? '#93C5FD' : '#1D4ED8',
                  fontWeight: 600,
                  fontSize: '0.88rem',
                  cursor: isTestingConnection ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = theme === 'dark' ? 'rgba(59, 130, 246, 0.25)' : '#DBEAFE')}
                onMouseLeave={(e) => (e.currentTarget.style.background = theme === 'dark' ? 'rgba(59, 130, 246, 0.15)' : '#EFF6FF')}
              >
                {isTestingConnection ? <Loader2 size={16} className="animate-spin" /> : '⚡ Test Connection'}
              </button>

              <button
                type="submit"
                disabled={isSavingModel}
                style={{
                  flex: 1.5,
                  background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '12px',
                  padding: '11px',
                  fontWeight: 700,
                  fontSize: '0.88rem',
                  cursor: isSavingModel ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)')}
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
                background: '#FEF3C7',
                border: '1px solid #FCD34D',
                borderRadius: '20px',
                padding: '18px 22px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                boxShadow: '0 4px 20px rgba(217, 119, 6, 0.08)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div
                  style={{
                    width: '46px',
                    height: '46px',
                    borderRadius: '14px',
                    background: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Flame size={24} color="#EF4444" />
                </div>
                <div>
                  <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: '#B45309', fontWeight: 700 }}>
                    Lifetime Account Consumption
                  </div>
                  <div style={{ fontSize: '1.85rem', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.5px', lineHeight: 1.2, marginTop: '2px' }}>
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
                  background: theme === 'dark' ? '#1E1F20' : '#FFFFFF',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '12px',
                  padding: '8px 14px',
                  color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
                }}
              >
                <RefreshCw size={13} className={isRefreshingUsage ? 'animate-spin' : ''} />
                <span>{isRefreshingUsage ? 'Syncing...' : 'Sync'}</span>
              </button>
            </div>

            {/* Metric Breakdown Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              <div style={{ background: theme === 'dark' ? '#131314' : '#F8FAFC', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Prompt Tokens</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#2563EB', marginTop: '4px' }}>
                  {promptTokens.toLocaleString()}
                </div>
              </div>

              <div style={{ background: theme === 'dark' ? '#131314' : '#F8FAFC', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Completion Tokens</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#7C3AED', marginTop: '4px' }}>
                  {completionTokens.toLocaleString()}
                </div>
              </div>

              <div style={{ background: theme === 'dark' ? '#131314' : '#F8FAFC', border: '1px solid var(--glass-border)', padding: '14px', borderRadius: '16px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Queries</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#059669', marginTop: '4px' }}>
                  {totalQueries.toLocaleString()}
                </div>
              </div>
            </div>

            {/* Visual Token Distribution Progress Bar */}
            <div style={{ background: theme === 'dark' ? '#131314' : '#F8FAFC', border: '1px solid var(--glass-border)', borderRadius: '18px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: theme === 'dark' ? '#FFFFFF' : 'var(--text-main)' }}>Token Distribution Breakdown</span>
                <span style={{ fontSize: '0.75rem', color: '#059669', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                  <Zap size={12} /> Cache Saved: {savedTokens.toLocaleString()}
                </span>
              </div>

              <div style={{ height: '14px', width: '100%', borderRadius: '10px', background: theme === 'dark' ? '#282A2C' : '#E2E8F0', overflow: 'hidden', display: 'flex' }}>
                <div style={{ width: `${Math.min(100, Math.max(5, (promptTokens / (totalTokensBurned || 1)) * 100))}%`, background: '#2563EB' }} title={`Prompt Tokens: ${promptTokens.toLocaleString()}`} />
                <div style={{ width: `${Math.min(100, Math.max(5, (completionTokens / (totalTokensBurned || 1)) * 100))}%`, background: '#7C3AED' }} title={`Completion Tokens: ${completionTokens.toLocaleString()}`} />
                {savedTokens > 0 && (
                  <div style={{ width: `${Math.min(100, Math.max(5, (savedTokens / (totalTokensBurned + savedTokens || 1)) * 100))}%`, background: '#059669' }} title={`Saved Cache Tokens: ${savedTokens.toLocaleString()}`} />
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', fontSize: '0.78rem', color: 'var(--text-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#2563EB' }} />
                  <span>Prompt ({promptTokens.toLocaleString()})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#7C3AED' }} />
                  <span>Completion ({completionTokens.toLocaleString()})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#059669' }} />
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
