import React from 'react';
import { Shield, CheckCircle, ArrowRight, Database, Lock, LogIn, UserPlus } from 'lucide-react';
import { BisLogo } from './BisLogo';

interface LandingPageProps {
  onOpenLogin: () => void;
  onOpenSignup: () => void;
}

const FEATURE_CARDS = [
  {
    title: 'Gold Hallmarking & HUID',
    description: 'Instant compliance guidance for IS 1417 gold purity, 6-digit HUID marking, and AHC center registration.',
    icon: <BisLogo size={32} />,
  },
  {
    title: 'Electronics CRS Registration',
    description: 'Mandatory documentation checklists and portal filing rules for MeitY electronic & IT equipment.',
    icon: <BisLogo size={32} />,
  },
  {
    title: 'FMCS Overseas Certification',
    description: 'Foreign Manufacturers Certification Scheme procedures and Authorized Indian Representative (AIR) rules.',
    icon: <BisLogo size={32} />,
  },
  {
    title: 'BIS Testing Lab Networks',
    description: 'Locate NABL and BIS-accredited testing laboratories for chemical, physical, and safety parameters.',
    icon: <BisLogo size={32} />,
  },
  {
    title: 'Real-Time User Usage Analytics',
    description: 'Track cumulative LLM token burn, query execution counts, and cache savings per user account in real time.',
    icon: <BisLogo size={32} />,
  },
  {
    title: '0-Token Instant Cache',
    description: 'Front-loaded caching for frequent compliance queries bypassing LLM execution for 0-latency results.',
    icon: <BisLogo size={32} />,
  },
];


export const LandingPage: React.FC<LandingPageProps> = ({ onOpenLogin, onOpenSignup }) => {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--gemini-bg-main)', color: 'var(--text-main)', display: 'flex', flexDirection: 'column', overflowY: 'auto', }}>
      {/* Navigation Header */}
      <nav
        style={{
          height: '64px',
          padding: '0 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--glass-border)',
          background: 'var(--gemini-bg-main)',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BisLogo size={32} />
          <span style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#FFFFFF' }}>
            BIS SATHI
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <button
            onClick={onOpenLogin}
            style={{
              padding: '8px 20px',
              borderRadius: '24px',
              background: 'transparent',
              border: '1px solid var(--glass-border)',
              color: '#FFFFFF',
              fontSize: '0.88rem',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'background 0.2s ease',
            }}
          >
            <LogIn size={15} />
            Sign In
          </button>
          <button
            onClick={onOpenSignup}
            style={{
              padding: '8px 20px',
              borderRadius: '24px',
              background: 'var(--gemini-sparkle-gradient)',
              border: 'none',
              color: '#FFFFFF',
              fontSize: '0.88rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 4px 16px rgba(155, 81, 224, 0.3)',
            }}
          >
            <UserPlus size={15} />
            Create Account
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{ maxWidth: '1000px', margin: '0 auto', padding: '80px 24px 60px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '28px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 16px', borderRadius: '20px', background: 'rgba(66, 133, 244, 0.1)', border: '1px solid rgba(66, 133, 244, 0.3)', color: 'var(--gemini-blue)', fontSize: '0.82rem', fontWeight: 600 }}>
          <Shield size={15} /> Official Compliance Intelligence Platform
        </div>

        <h1 className="gemini-gradient-text" style={{ fontSize: '3.6rem', fontWeight: 700, letterSpacing: '-0.03em', lineHeight: '1.15' }}>
          AI-Powered BIS Compliance & Regulatory Intelligence
        </h1>

        <p style={{ fontSize: '1.15rem', color: 'var(--text-subtle)', lineHeight: '1.65', maxWidth: '720px' }}>
          Get instant, authoritative answers on Indian Standards (IS codes), Gold Hallmarking, MeitY CRS registration, Foreign FMCS licenses, and testing laboratory networks.
        </p>

        {/* CTA Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px' }}>
          <button
            onClick={onOpenLogin}
            style={{
              padding: '16px 36px',
              borderRadius: '30px',
              background: 'var(--gemini-sparkle-gradient)',
              border: 'none',
              color: '#FFFFFF',
              fontSize: '1.05rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              boxShadow: '0 6px 24px rgba(155, 81, 224, 0.4)',
              transition: 'transform 0.2s ease',
            }}
          >
            <span>Sign In to Start Chat</span>
            <ArrowRight size={20} />
          </button>
        </div>

        {/* Live Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap', justifyContent: 'center', marginTop: '20px', fontSize: '0.86rem', color: 'var(--text-muted)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle size={16} color="var(--gemini-green)" />
            <span>50,000+ Indian Standards</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Database size={16} color="var(--gemini-purple)" />
            <span>Supabase PostgreSQL Persistence</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Lock size={16} color="var(--gemini-gold)" />
            <span>Encrypted User Sessions</span>
          </div>
        </div>
      </section>

      {/* Feature Grid */}
      <section style={{ maxWidth: '1100px', margin: '0 auto', padding: '40px 24px 80px 24px', width: '100%' }}>
        <h2 style={{ fontSize: '1.8rem', fontWeight: 600, color: '#FFFFFF', textAlign: 'center', marginBottom: '40px' }}>
          Comprehensive Compliance Capabilities
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
          {FEATURE_CARDS.map((feat, idx) => (
            <div
              key={idx}
              className="gemini-card"
              style={{
                padding: '28px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ fontSize: '2rem', padding: '10px', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '16px', width: 'fit-content' }}>
                {feat.icon}
              </div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 600, color: '#FFFFFF', marginTop: '6px' }}>
                {feat.title}
              </h3>
              <p style={{ fontSize: '0.92rem', color: 'var(--text-subtle)', lineHeight: '1.6' }}>
                {feat.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--glass-border)', padding: '24px', textAlign: 'center', fontSize: '0.82rem', color: 'var(--text-muted)', background: 'var(--gemini-bg-main)' }}>
        © 2026 BIS SATHI - Bureau of Indian Standards Agentic RAG Assistant. Powered by FastAPI & Supabase.
      </footer>
    </div>
  );
};
