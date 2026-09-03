import React from 'react';
import { Plus, MessageSquare, Trash2, Zap, Bookmark, Sparkles, LogOut, LogIn } from 'lucide-react';
import type { UserProfile } from '../types';


interface SessionSidebarProps {
  sessions: { session_id: string; history_turns: number; last_query?: string }[];
  activeSessionId: string;
  currentUser: UserProfile | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onClearSession: (id: string) => void;
  onClearCache: () => void;
  onSelectPrompt: (prompt: string) => void;
  onOpenAuthModal: () => void;
  onOpenProfileModal?: () => void;
  onLogout: () => void;
  isOpen?: boolean;
}

const BIS_SAMPLE_PROMPTS = [
  { label: 'Gold Hallmarking HUID', prompt: 'What is the procedure for getting a Gold Hallmarking license under BIS?' },
  { label: 'CRS Electronics Scheme', prompt: 'What are the required compliance documents for electronics CRS registration?' },
  { label: 'FMCS Overseas License', prompt: 'Explain the Foreign Manufacturers Certification Scheme (FMCS) requirements.' },
  { label: 'BIS Testing Labs', prompt: 'How to check BIS recognized testing laboratory networks for steel testing?' },
];

export const SessionSidebar: React.FC<SessionSidebarProps> = ({
  sessions,
  activeSessionId,
  currentUser,
  onSelectSession,
  onNewSession,
  onClearSession,
  onClearCache,
  onSelectPrompt,
  onOpenAuthModal,
  onOpenProfileModal,
  onLogout,
  isOpen = true,
}) => {


  if (!isOpen) return null;

  return (
    <aside
      style={{
        width: '270px',
        background: 'var(--gemini-bg-sidebar)',
        borderRight: '1px solid var(--glass-border)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '16px 12px',
        gap: '16px',
        zIndex: 20,
      }}
    >
      {/* Gemini "+ New chat" Pill Button */}
      <button
        onClick={onNewSession}
        style={{
          width: '100%',
          padding: '12px 18px',
          borderRadius: '24px',
          background: 'rgba(255, 255, 255, 0.06)',
          border: '1px solid var(--glass-border)',
          color: 'var(--text-main)',
          fontSize: '0.9rem',
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--gemini-bg-card-hover)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)')}
      >
        <Plus size={18} color="var(--gemini-blue)" />
        New chat
      </button>

      {/* Recent Conversation History List */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-muted)', padding: '6px 10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Recent Activity
        </div>

        {sessions.length === 0 ? (
          <div style={{ padding: '12px 10px', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            No recent activity.
          </div>
        ) : (
          sessions.map((sess) => {
            const isActive = sess.session_id === activeSessionId;
            return (
              <div
                key={sess.session_id}
                onClick={() => onSelectSession(sess.session_id)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '20px',
                  background: isActive ? 'rgba(66, 133, 244, 0.15)' : 'transparent',
                  color: isActive ? '#FFFFFF' : 'var(--text-subtle)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '0.86rem',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                  <MessageSquare size={15} color={isActive ? '#4285F4' : 'var(--text-muted)'} />
                  <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '150px' }}>
                    {sess.last_query || sess.session_id}
                  </span>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onClearSession(sess.session_id);
                  }}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', opacity: 0.6 }}
                  title="Delete chat"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Quick Prompts */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingTop: '12px', borderTop: '1px solid var(--glass-border)' }}>
        <div style={{ fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-muted)', padding: '0 4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Bookmark size={13} color="var(--gemini-purple)" />
          Suggested Compliance Prompts
        </div>
        {BIS_SAMPLE_PROMPTS.map((p, idx) => (
          <button
            key={idx}
            onClick={() => onSelectPrompt(p.prompt)}
            style={{
              padding: '8px 12px',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: 'none',
              color: 'var(--text-subtle)',
              fontSize: '0.8rem',
              textAlign: 'left',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              transition: 'background 0.2s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--gemini-bg-card-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)')}
          >
            💡 {p.label}
          </button>
        ))}
      </div>

      {/* Clear Cache Button */}
      <button
        onClick={onClearCache}
        style={{
          width: '100%',
          padding: '8px 12px',
          borderRadius: '20px',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          color: '#EF4444',
          fontSize: '0.78rem',
          fontWeight: 500,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px',
        }}
      >
        <Zap size={14} />
        Clear Response Cache
      </button>

      {/* Gemini User Profile Footer */}
      <div style={{ paddingTop: '12px', borderTop: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div
          onClick={currentUser && onOpenProfileModal ? onOpenProfileModal : onOpenAuthModal}
          title={currentUser ? "View Account Details & Token Usage" : "Sign In"}
          style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden', cursor: 'pointer' }}
        >
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: currentUser ? 'linear-gradient(135deg, #A855F7 0%, #EC4899 100%)' : 'var(--gemini-sparkle-gradient)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF',
              fontWeight: 700,
              fontSize: '0.9rem',
              flexShrink: 0,
            }}
          >
            {currentUser ? currentUser.full_name.charAt(0).toUpperCase() : <Sparkles size={18} color="#FFFFFF" />}
          </div>
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: '0.86rem', fontWeight: 600, color: '#FFFFFF', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {currentUser ? currentUser.full_name : 'Guest User'}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {currentUser ? currentUser.email : 'Supabase Connected'}
            </div>
          </div>
        </div>


        {currentUser ? (
          <button
            onClick={onLogout}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '6px' }}
            title="Sign Out"
          >
            <LogOut size={16} />
          </button>
        ) : (
          <button
            onClick={onOpenAuthModal}
            style={{ background: 'none', border: 'none', color: 'var(--gemini-purple)', cursor: 'pointer', padding: '6px' }}
            title="Sign In"
          >
            <LogIn size={16} />
          </button>
        )}
      </div>
    </aside>
  );

};
