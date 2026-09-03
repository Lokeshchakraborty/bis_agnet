import React from 'react';
import { Menu, Database, BarChart3, Sparkles, User, LogOut } from 'lucide-react';
import type { HealthResponse, UserProfile } from '../types';


interface HeaderProps {
  health: HealthResponse | null;
  currentUser: UserProfile | null;
  onToggleTelemetry: () => void;
  onOpenAuthModal: () => void;
  onOpenProfileModal: () => void;
  onLogout: () => void;
  onToggleSidebar?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  currentUser,
  onToggleTelemetry,
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

        {/* Gemini Brand Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Sparkles size={22} className="gemini-sparkle-icon" color="#9B51E0" />
          </div>
          <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#FFFFFF', letterSpacing: '-0.01em' }}>
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
            <div
              onClick={onOpenProfileModal}
              title="View Account Details & Token Usage"
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

