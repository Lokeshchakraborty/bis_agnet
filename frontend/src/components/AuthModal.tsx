import React, { useState } from 'react';
import { X, Lock, Mail, User, Loader2, LogIn, UserPlus } from 'lucide-react';
import type { UserProfile, AuthResponse } from '../types';
import { getApiUrl } from '../config';

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
      const res = await fetch(getApiUrl(endpoint), {
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
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.45)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '16px' }}>
      <div className="animate-fade-in modal-responsive-card" style={{ background: '#FFFFFF', border: '1px solid var(--glass-border)', borderRadius: '24px', width: '420px', maxWidth: '95vw', padding: '28px', display: 'flex', flexDirection: 'column', gap: '20px', position: 'relative', boxShadow: '0 20px 45px -10px rgba(0, 0, 0, 0.15)' }}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{ position: 'absolute', top: '20px', right: '20px', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
        >
          <X size={20} />
        </button>

        {/* Modal Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>

          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-main)' }}>BIS SATHI Account</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Sign in to sync your conversation sessions in Supabase.
            </p>
          </div>
        </div>

        {/* Tab Toggle */}
        <div style={{ display: 'flex', background: '#F1F5F9', borderRadius: '16px', padding: '4px', border: '1px solid var(--glass-border)' }}>
          <button
            onClick={() => { setIsLoginTab(true); setErrorMessage(''); }}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '12px',
              border: 'none',
              background: isLoginTab ? '#FFFFFF' : 'transparent',
              color: isLoginTab ? '#0F172A' : 'var(--text-muted)',
              fontWeight: isLoginTab ? 600 : 500,
              fontSize: '0.88rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: isLoginTab ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
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
              background: !isLoginTab ? '#FFFFFF' : 'transparent',
              color: !isLoginTab ? '#0F172A' : 'var(--text-muted)',
              fontWeight: !isLoginTab ? 600 : 500,
              fontSize: '0.88rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: !isLoginTab ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            <UserPlus size={15} />
            Create Account
          </button>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div style={{ padding: '10px 14px', borderRadius: '12px', background: '#FEE2E2', border: '1px solid #FCA5A5', color: '#B91C1C', fontSize: '0.82rem', textAlign: 'center' }}>
            {errorMessage}
          </div>
        )}

        {/* Form Inputs */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {!isLoginTab && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-subtle)' }}>Full Name</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: '#F8FAFC', border: '1px solid var(--glass-border)', borderRadius: '14px', padding: '10px 14px' }}>
                <User size={18} color="var(--text-muted)" />
                <input
                  type="text"
                  placeholder="e.g. Rajesh Sharma"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required={!isLoginTab}
                  style={{ background: 'none', border: 'none', outline: 'none', color: 'var(--text-main)', fontSize: '0.92rem', width: '100%' }}
                />
              </div>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-subtle)' }}>Email Address</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: '#F8FAFC', border: '1px solid var(--glass-border)', borderRadius: '14px', padding: '10px 14px' }}>
              <Mail size={18} color="var(--text-muted)" />
              <input
                type="email"
                placeholder="officer@bis.gov.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{ background: 'none', border: 'none', outline: 'none', color: 'var(--text-main)', fontSize: '0.92rem', width: '100%' }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-subtle)' }}>Password</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: '#F8FAFC', border: '1px solid var(--glass-border)', borderRadius: '14px', padding: '10px 14px' }}>
              <Lock size={18} color="var(--text-muted)" />
              <input
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{ background: 'none', border: 'none', outline: 'none', color: 'var(--text-main)', fontSize: '0.92rem', width: '100%' }}
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
              background: 'var(--gemini-blue)',
              border: 'none',
              color: '#FFFFFF',
              fontWeight: 600,
              fontSize: '0.92rem',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 4px 16px rgba(79, 114, 230, 0.3)',
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
