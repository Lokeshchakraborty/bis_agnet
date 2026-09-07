import React from 'react';
import { Menu, Database, BarChart3, User, LogOut, ShieldCheck, Cpu, Sun, Moon } from 'lucide-react';
import type { HealthResponse, UserProfile } from '../types';
import { BisLogo } from './BisLogo';

interface HeaderProps {
  health: HealthResponse | null;
  currentUser: UserProfile | null;
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
  onToggleTelemetry: () => void;
  onOpenAuditLedger?: () => void;
  onOpenAuthModal: () => void;
  onOpenProfileModal: (tab?: 'details' | 'model' | 'usage') => void;
  onLogout: () => void;
  onToggleSidebar?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  currentUser,
  theme = 'light',
  onToggleTheme,
  onToggleTelemetry,
  onOpenAuditLedger,
  onOpenAuthModal,
  onOpenProfileModal,
  onLogout,
  onToggleSidebar,
}) => {




  return (
    <header
      className="header-compact-padding"
      style={{
        height: '56px',
        background: 'var(--gemini-bg-main)',
        borderBottom: '1px solid var(--glass-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingBlock: "30px",
        paddingLeft: "12px",
        paddingRight: "12px",
        zIndex: 10,
      }}
    >
      {/* Left: Sidebar Toggle + Gemini Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-subtle)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.2s ease',
              marginBlock: "30px",
            }}
            title="Toggle Menu"
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.06)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <Menu size={20} />
          </button>
        )}

        {/* Official BIS Brand Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <BisLogo size={26} />
          </div>
          <span className="header-brand-title" style={{ fontSize: '1.08rem', fontWeight: 800, color: theme === 'dark' ? '#FFFFFF' : '#0F172A', letterSpacing: '-0.01em' }}>
            BIS SATHI
          </span>
        </div>
      </div>

      {/* Right: Status Badges & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Supabase Connection Status (Hidden on very small screens) */}
        <div
          className="header-hide-mobile"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.76rem',
            color: health?.supabase_connected ? '#059669' : '#DC2626',
            background: health?.supabase_connected ? 'rgba(5, 150, 105, 0.1)' : 'rgba(220, 38, 38, 0.1)',
            padding: '4px 10px',
            borderRadius: '20px',
            border: `1px solid ${health?.supabase_connected ? 'rgba(5, 150, 105, 0.25)' : 'rgba(220, 38, 38, 0.25)'}`,
          }}
        >
          <Database size={12} />
          <span>{health?.supabase_connected ? 'Supabase' : 'Offline'}</span>
        </div>

        {/* Audit Ledger Button (Restricted to Admin Accounts Only) */}
        {(currentUser?.is_admin || currentUser?.email?.toLowerCase().includes('admin') || currentUser?.email?.toLowerCase().endsWith('@bis.gov.in')) && onOpenAuditLedger && (
          <button
            onClick={onOpenAuditLedger}
            title="Inspect Immutable Legal Audit Trail (Admin Privileges Active)"
            style={{
              background: 'rgba(217, 119, 6, 0.1)',
              border: '1px solid rgba(217, 119, 6, 0.3)',
              color: '#D97706',
              padding: '5px 10px',
              borderRadius: '20px',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(217, 119, 6, 0.18)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(217, 119, 6, 0.1)')}
          >
            <ShieldCheck size={14} color="#D97706" />
            <span className="header-btn-label">Audit</span>
            <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '8px', background: '#D97706', color: '#FFFFFF', fontWeight: 700, textTransform: 'uppercase' }}>Admin</span>
          </button>
        )}

        {/* Quick Dark/Light Mode Switcher */}
        {onToggleTheme && (
          <button
            onClick={onToggleTheme}
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            style={{
              background: 'var(--gemini-bg-card)',
              border: '1px solid var(--glass-border)',
              color: theme === 'dark' ? '#F59E0B' : '#475569',
              padding: '5px 10px',
              borderRadius: '20px',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              transition: 'all 0.2s ease',
            }}
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            <span className="header-btn-label">{theme === 'dark' ? 'Light' : 'Dark'}</span>
          </button>
        )}

        {/* Telemetry Button */}
        <button
          onClick={onToggleTelemetry}
          title="Toggle Turn Telemetry Panel"
          style={{
            background: 'var(--gemini-bg-card)',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-subtle)',
            padding: '5px 10px',
            borderRadius: '20px',
            fontSize: '0.78rem',
            fontWeight: 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
          }}
        >
          <BarChart3 size={14} />
          <span className="header-btn-label">Telemetry</span>
        </button>

        {/* User Account / Auth Button */}
        {currentUser ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {/* Dynamic Model Selector Badge */}
            <button
              onClick={() => onOpenProfileModal('model')}
              title={`Active Model: ${currentUser.llm_model || 'gemini-3.5-flash'} (Click to change)`}
              style={{
                background: theme === 'dark' ? 'rgba(37, 99, 235, 0.16)' : 'rgba(37, 99, 235, 0.08)',
                border: '1px solid rgba(37, 99, 235, 0.25)',
                color: theme === 'dark' ? '#93C5FD' : '#1D4ED8',
                padding: '4px 10px',
                borderRadius: '20px',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(37, 99, 235, 0.24)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = theme === 'dark' ? 'rgba(37, 99, 235, 0.16)' : 'rgba(37, 99, 235, 0.08)')}
            >
              <Cpu size={13} color={theme === 'dark' ? '#93C5FD' : '#1D4ED8'} />
              <span className="header-btn-label" style={{ maxWidth: '110px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {currentUser.llm_model || 'gemini-3.5-flash'}
              </span>
            </button>

            <div
              onClick={() => onOpenProfileModal('details')}
              title="View Account Details, Theme & Standards Settings"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: '20px',
                background: theme === 'dark' ? 'rgba(37, 99, 235, 0.16)' : 'rgba(37, 99, 235, 0.08)',
                border: '1px solid rgba(37, 99, 235, 0.2)',
                color: theme === 'dark' ? '#F1F5F9' : '#0F172A',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'background 0.2s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(37, 99, 235, 0.24)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = theme === 'dark' ? 'rgba(37, 99, 235, 0.16)' : 'rgba(37, 99, 235, 0.08)')}
            >
              <User size={14} color="var(--gemini-blue)" />
              <span className="header-btn-label">{currentUser.full_name}</span>
            </div>
            <button
              onClick={onLogout}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '5px' }}
              title="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuthModal}
            style={{
              padding: '6px 14px',
              borderRadius: '20px',
              background: 'var(--gemini-sparkle-gradient)',
              border: 'none',
              color: '#FFFFFF',
              fontSize: '0.80rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}
          >
            <User size={14} />
            <span className="header-btn-label">Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
};

