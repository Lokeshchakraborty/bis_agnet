import React from 'react';
import { Menu, Database, BarChart3, User, LogOut, ShieldCheck, Cpu } from 'lucide-react';
import type { HealthResponse, UserProfile } from '../types';
import { BisLogo } from './BisLogo';

interface HeaderProps {
  health: HealthResponse | null;
  currentUser: UserProfile | null;
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
  onToggleTelemetry,
  onOpenAuditLedger,
  onOpenAuthModal,
  onOpenProfileModal,
  onLogout,
  onToggleSidebar,
}) => {




  return (
    <header
      style={{
        height: '56px',
        background: 'var(--gemini-bg-main)',
        borderBottom: '1px solid var(--glass-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        zIndex: 10,
      }}
    >
      {/* Left: Sidebar Toggle + Gemini Logo + Model Selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-subtle)',
              cursor: 'pointer',
              padding: '8px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.2s ease',
            }}
            title="Toggle Menu"
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <Menu size={20} />
          </button>
        )}

        {/* Official BIS Brand Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <BisLogo size={28} />
          </div>
          <span style={{ fontSize: '1.08rem', fontWeight: 800, color: '#FFFFFF', letterSpacing: '-0.01em' }}>
            BIS SATHI
          </span>
        </div>
      </div>



      {/* Right: Status Badges & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Supabase Connection Status */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.78rem',
            color: health?.supabase_connected ? '#10B981' : '#EF4444',
            background: health?.supabase_connected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            padding: '4px 12px',
            borderRadius: '20px',
            border: `1px solid ${health?.supabase_connected ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
          }}
        >
          <Database size={13} />
          <span>{health?.supabase_connected ? 'Supabase Active' : 'Offline'}</span>
        </div>

        {/* Audit Ledger Button (Restricted to Admin Accounts Only) */}
        {(currentUser?.is_admin || currentUser?.email?.toLowerCase().includes('admin') || currentUser?.email?.toLowerCase().endsWith('@bis.gov.in')) && onOpenAuditLedger && (
          <button
            onClick={onOpenAuditLedger}
            title="Inspect Immutable Legal Audit Trail (Admin Privileges Active)"
            style={{
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.35)',
              color: '#F59E0B',
              padding: '6px 14px',
              borderRadius: '20px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(245, 158, 11, 0.22)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(245, 158, 11, 0.12)')}
          >
            <ShieldCheck size={14} color="#F59E0B" />
            <span>Audit Ledger</span>
            <span style={{ fontSize: '0.68rem', padding: '1px 6px', borderRadius: '10px', background: '#F59E0B', color: '#000', fontWeight: 700, textTransform: 'uppercase' }}>Admin</span>
          </button>
        )}

        {/* Telemetry Button */}
        <button
          onClick={onToggleTelemetry}
          style={{
            background: 'var(--gemini-bg-card)',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-subtle)',
            padding: '6px 14px',
            borderRadius: '20px',
            fontSize: '0.82rem',
            fontWeight: 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <BarChart3 size={14} />
          Telemetry
        </button>

        {/* User Account / Auth Button */}
        {currentUser ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Dynamic Model Selector Badge */}
            <button
              onClick={() => onOpenProfileModal('model')}
              title="Configure AI Model & BYOK Provider (Click to change)"
              style={{
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.35)',
                color: '#F59E0B',
                padding: '5px 12px',
                borderRadius: '20px',
                fontSize: '0.80rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(245, 158, 11, 0.22)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(245, 158, 11, 0.12)')}
            >
              <Cpu size={13} color="#F59E0B" />
              <span>{currentUser.llm_model || 'gemini-3.5-flash-lite'}</span>
            </button>

            <div
              onClick={() => onOpenProfileModal('usage')}
              title="View Lifetime Token Analytics & Account Details"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '4px 14px',
                borderRadius: '20px',
                background: 'rgba(155, 81, 224, 0.15)',
                border: '1px solid rgba(155, 81, 224, 0.3)',
                color: '#FFFFFF',
                fontSize: '0.82rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'background 0.2s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(155, 81, 224, 0.25)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(155, 81, 224, 0.15)')}
            >
              <User size={14} color="var(--gemini-purple)" />
              <span>{currentUser.full_name}</span>
            </div>
            <button
              onClick={onLogout}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '6px' }}
              title="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (

          <button
            onClick={onOpenAuthModal}
            style={{
              padding: '6px 16px',
              borderRadius: '20px',
              background: 'var(--gemini-sparkle-gradient)',
              border: 'none',
              color: '#FFFFFF',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <User size={14} />
            Sign In
          </button>
        )}
      </div>
    </header>
  );
};

