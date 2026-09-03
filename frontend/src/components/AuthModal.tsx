import React, { useState } from 'react';
import { X, Lock, Mail, User, Sparkles, Loader2, LogIn, UserPlus } from 'lucide-react';
import type { UserProfile, AuthResponse } from '../types';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (user: UserProfile) => void;
  initialMode?: 'login' | 'signup';
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onAuthSuccess, initialMode = 'login' }) => {
  const [isLoginTab, setIsLoginTab] = useState(initialMode === 'login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  React.useEffect(() => {
    setIsLoginTab(initialMode === 'login');
  }, [initialMode, isOpen]);


  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    setIsLoading(true);

    const endpoint = isLoginTab ? '/api/v1/auth/login' : '/api/v1/auth/signup';
    const payload = isLoginTab
      ? { email, password }
      : { email, password, full_name: fullName };

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data: AuthResponse = await res.json();
      if (!res.ok || !data.success || !data.user) {
        throw new Error(data.error || 'Authentication failed.');
      }

      onAuthSuccess(data.user);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Server authentication error.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(19, 19, 20, 0.85)', backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '20px' }}>
      <div style={{ background: 'var(--gemini-bg-card)', border: '1px solid var(--glass-border)', borderRadius: '24px', width: '420px', padding: '28px', display: 'flex', flexDirection: 'column', gap: '20px', position: 'relative', boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)' }}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{ position: 'absolute', top: '20px', right: '20px', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
        >
          <X size={20} />
        </button>

        {/* Modal Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '50%', background: 'var(--gemini-sparkle-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(155, 81, 224, 0.4)' }}>
            <Sparkles size={22} color="#FFFFFF" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#FFFFFF' }}>BIS SATHI Account</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Sign in to sync your conversation sessions in Supabase.
            </p>
          </div>
        </div>

        {/* Tab Toggle */}
        <div style={{ display: 'flex', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '16px', padding: '4px', border: '1px solid var(--glass-border)' }}>
          <button
            onClick={() => { setIsLoginTab(true); setErrorMessage(''); }}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '12px',
              border: 'none',
              background: isLoginTab ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
              color: isLoginTab ? '#FFFFFF' : 'var(--text-muted)',
              fontWeight: isLoginTab ? 600 : 500,
              fontSize: '0.88rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <LogIn size={15} />
            Sign In
          </button>
          <button
            onClick={() => { setIsLoginTab(false); setErrorMessage(''); }}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '12px',
              border: 'none',
              background: !isLoginTab ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
              color: !isLoginTab ? '#FFFFFF' : 'var(--text-muted)',
              fontWeight: !isLoginTab ? 600 : 500,
              fontSize: '0.88rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <UserPlus size={15} />
            Create Account
          </button>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div style={{ padding: '10px 14px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#EF4444', fontSize: '0.82rem', textAlign: 'center' }}>
            {errorMessage}
          </div>
        )}

        {/* Form Inputs */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {!isLoginTab && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-subtle)' }}>Full Name</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '14px', padding: '10px 14px' }}>
                <User size={18} color="var(--text-muted)" />
                <input
                  type="text"
                  placeholder="e.g. Rajesh Sharma"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required={!isLoginTab}
                  style={{ background: 'none', border: 'none', outline: 'none', color: '#FFF', fontSize: '0.92rem', width: '100%' }}
                />
              </div>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-subtle)' }}>Email Address</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '14px', padding: '10px 14px' }}>
              <Mail size={18} color="var(--text-muted)" />
              <input
                type="email"
                placeholder="officer@bis.gov.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{ background: 'none', border: 'none', outline: 'none', color: '#FFF', fontSize: '0.92rem', width: '100%' }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-subtle)' }}>Password</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'var(--gemini-bg-main)', border: '1px solid var(--glass-border)', borderRadius: '14px', padding: '10px 14px' }}>
              <Lock size={18} color="var(--text-muted)" />
              <input
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{ background: 'none', border: 'none', outline: 'none', color: '#FFF', fontSize: '0.92rem', width: '100%' }}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              marginTop: '8px',
              padding: '12px',
              borderRadius: '24px',
              background: 'var(--gemini-sparkle-gradient)',
              border: 'none',
              color: '#FFFFFF',
              fontWeight: 600,
              fontSize: '0.92rem',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 4px 16px rgba(155, 81, 224, 0.3)',
            }}
          >
            {isLoading ? <Loader2 size={18} className="gemini-pulse" /> : isLoginTab ? <LogIn size={18} /> : <UserPlus size={18} />}
            {isLoading ? 'Authenticating...' : isLoginTab ? 'Sign In' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  );
};
