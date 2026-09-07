import React, { useState } from 'react';
import {
  Shield,
  CheckCircle2,
  ArrowRight,
  Database,
  Lock,
  LogIn,
  UserPlus,
  Sparkles,
  Zap,
  Layers,
  ChevronDown,
  Check,
  FileCheck,
  Building2,
  Factory,
  Gem,
  Laptop,
  FlaskConical,
  ExternalLink,
  ShieldCheck,
  Activity,
  Award,
  BookOpen,
  ArrowUpRight,
  Menu,
  X,
} from 'lucide-react';
import { BisLogo } from './BisLogo';

interface LandingPageProps {
  onOpenLogin: () => void;
  onOpenSignup: () => void;
}

// --------------------------------------------------------------------------- //
// Interactive Simulator Presets
// --------------------------------------------------------------------------- //
interface SimulatorPreset {
  id: string;
  category: string;
  badge: string;
  query: string;
  intent: string;
  standardCode: string;
  standardTitle: string;
  confidence: number;
  latency: string;
  tokensBurned: number;
  cacheStatus: string;
  answerSummary: string;
  keyPoints: string[];
  mandatoryClause: string;
}

const SIMULATOR_PRESETS: SimulatorPreset[] = [
  {
    id: 'gold-hallmark',
    category: 'Gold & Jewellery',
    badge: 'IS 1417:2016',
    query: 'What are the mandatory 6-digit HUID hallmarking rules for 22K and 18K gold jewellery?',
    intent: 'GOLD_HALLMARKING_HUID_COMPLIANCE',
    standardCode: 'IS 1417:2016 (Amd 3)',
    standardTitle: 'Gold and Gold Alloys, Platings and Finishes — Fineness and Hallmarking',
    confidence: 99.4,
    latency: '0.04s (0-Token Instant Cache)',
    tokensBurned: 0,
    cacheStatus: 'CACHE_HIT',
    answerSummary:
      'Under the BIS Hallmarking Order 2021 and Amendment 2023, sale of gold jewellery without a 6-digit alphanumeric HUID (Hallmarking Unique Identification) is legally prohibited across all notified districts.',
    keyPoints: [
      'Recognized Caratages: 14K (585), 18K (750), 20K (833), 22K (916), 23K (958), and 24K (999).',
      'The 3 mandatory marks: BIS Logo, Purity in Carat & Fineness (e.g., 22K916), and 6-digit Alphanumeric HUID code.',
      'Jewelers must register through the manakonline.in portal with zero government fee for turnover under ₹40 Lakhs.',
    ],
    mandatoryClause: 'Mandatory under Ministry of Consumer Affairs Gazette Notification S.O. 1433(E)',
  },
  {
    id: 'electronics-crs',
    category: 'Electronics & IT (CRS)',
    badge: 'IS 13252:2010',
    query: 'How to register a new laptop model under MeitY Compulsory Registration Scheme (CRS)?',
    intent: 'MEITY_CRS_REGISTRATION_WORKFLOW',
    standardCode: 'IS 13252 (Part 1):2010 / IEC 60950-1',
    standardTitle: 'Information Technology Equipment — Safety — Part 1: General Requirements',
    confidence: 98.8,
    latency: '1.18s (Hybrid Vector Search)',
    tokensBurned: 840,
    cacheStatus: 'RETRIEVED_FROM_GAZETTE_INDEX',
    answerSummary:
      'Laptops fall under Item 2 of MeitY CRS Order Phase I. Registration requires testing from an accredited BIS-recognized Indian laboratory followed by portal filing on the CRS e-governance platform.',
    keyPoints: [
      'Submit test samples to a BIS-recognized testing lab in India with complete Bill of Materials (BOM) & schematics.',
      'Obtain valid test report (test report validity is 90 days for initial application submission).',
      'Foreign manufacturers must appoint an Authorized Indian Representative (AIR) under Form VI.',
      'Affix standard mark: "Self Declaration — Conforming to IS 13252 (Part 1)" with R-number and portal URL.',
    ],
    mandatoryClause: 'Compulsory registration under Electronics and IT Goods (Requirement for Compulsory Registration) Order',
  },
  {
    id: 'lithium-batteries',
    category: 'Batteries & Energy',
    badge: 'IS 16046:2018',
    query: 'What safety test parameters are required for Secondary Lithium Cells and Batteries for portable applications?',
    intent: 'LITHIUM_BATTERY_SAFETY_AUDIT',
    standardCode: 'IS 16046 (Part 2):2018 / IEC 62133-2',
    standardTitle: 'Secondary Cells and Batteries Containing Alkaline or Other Non-Acid Electrolytes (Lithium Systems)',
    confidence: 99.1,
    latency: '0.92s (BM25 + Semantic Cross-Encoder)',
    tokensBurned: 760,
    cacheStatus: 'VERIFIED_COMPLIANT',
    answerSummary:
      'IS 16046 (Part 2) mandates comprehensive electrical, mechanical, and thermal endurance testing to prevent catastrophic thermal runaway and short circuits in consumer electronics.',
    keyPoints: [
      'Mandatory mechanical stress tests: Continuous vibration, mechanical shock, and drop tests from 1.0m height.',
      'Mandatory thermal & electrical tests: External short circuit at 55°C, thermal abuse up to 130°C, and overcharge protection.',
      'Traceability requirement: Battery pack label must display nominal voltage, rated capacity, manufacturing date, and batch code.',
    ],
    mandatoryClause: 'Mandatory under Ministry of Power & MeitY CRS Phase III Notifications',
  },
  {
    id: 'fmcs-overseas',
    category: 'Overseas Importers (FMCS)',
    badge: 'FMCS Scheme I',
    query: 'What are the eligibility requirements and AIR agreement norms for foreign plants seeking BIS license?',
    intent: 'FOREIGN_MANUFACTURERS_CERTIFICATION_SCHEME',
    standardCode: 'BIS (Conformity Assessment) Reg. 2018',
    standardTitle: 'Scheme I (Marking Fee & Performance Bank Guarantee Guidelines)',
    confidence: 97.9,
    latency: '1.24s (Agentic Workflow)',
    tokensBurned: 920,
    cacheStatus: 'PARSED_FROM_FMCS_MANUAL',
    answerSummary:
      'The Foreign Manufacturers Certification Scheme (FMCS) enables overseas manufacturing facilities to apply for BIS ISI mark licenses, provided an Authorized Indian Representative (AIR) is legally nominated.',
    keyPoints: [
      'The factory must maintain in-house testing equipment matching the respective Indian Standard specifications.',
      'Mandatory appointment of an Authorized Indian Representative (AIR) residing in India who accepts legal accountability.',
      'Physical inspection of overseas factory premises by a BIS auditor with sample drawing for testing in India.',
      'Submission of Performance Bank Guarantee (PBG) of USD 10,000 from an RBI-approved international bank.',
    ],
    mandatoryClause: 'Subject to Scheme I of Bureau of Indian Standards (Conformity Assessment) Regulations 2018',
  },
  {
    id: 'tmt-steel-cement',
    category: 'Heavy Industry & QCO',
    badge: 'IS 1786:2008',
    query: 'What are the mandatory chemical limits for Fe 500D and Fe 550D TMT re-bars under the Steel QCO?',
    intent: 'STEEL_QCO_TECHNICAL_SPECIFICATIONS',
    standardCode: 'IS 1786:2008 (Grade Fe 500D/550D)',
    standardTitle: 'High Strength Deformed Steel Bars and Wires for Concrete Reinforcement',
    confidence: 99.6,
    latency: '0.05s (0-Token Instant Cache)',
    tokensBurned: 0,
    cacheStatus: 'CACHE_HIT',
    answerSummary:
      'The Ministry of Steel Quality Control Order mandates that no steel rebar may be manufactured, imported, or stocked without conforming to IS 1786 with rigorous chemical phosphorus and sulphur ceilings.',
    keyPoints: [
      'Carbon (max): 0.25% for Fe 500D and Fe 550D (guarantees weldability on infrastructure sites).',
      'Phosphorus + Sulphur (max combined): 0.075% for Fe 500D; 0.075% for Fe 550D for superior ductility.',
      'Mandatory elongation: Minimum 16.0% with mandatory Charpy V-notch impact toughness for earthquake zones.',
    ],
    mandatoryClause: 'Enforced under Steel and Steel Products (Quality Control) Order 2024',
  },
];

// --------------------------------------------------------------------------- //
// Compliance Domains Explorer Data (Shades Theme)
// --------------------------------------------------------------------------- //
const DOMAIN_CARDS = [
  {
    icon: <Gem size={26} color="#D97706" />,
    title: 'Gold Hallmarking & Jewellery',
    standard: 'IS 1417 & IS 2112',
    accentColor: '#FEF3C7',
    borderColor: '#FDE68A',
    description:
      'Complete regulatory clarity for retail jewelers and Assaying & Hallmarking Centers (AHC). Navigate 6-digit HUID generation, purity assays (14K to 24K), and portal integration.',
    features: ['HUID Audit Verification', 'AHC Lab Accreditation Guide', 'Purity Caratage Tolerances', 'Exemption Notification Checks'],
  },
  {
    icon: <Laptop size={26} color="#0284C7" />,
    title: 'Electronics & IT Goods (CRS)',
    standard: 'IS 13252, IS 16046, IS 616',
    accentColor: '#E0F2FE',
    borderColor: '#BAE6FD',
    description:
      'Streamline MeitY Compulsory Registration Scheme compliance for 70+ categories including smart meters, telecom routers, lithium battery systems, and POS terminals.',
    features: ['MeitY Phase I-V Categorization', 'Test Report Checklist (90 Days)', 'Label Marking Regulations', 'Series Inclusions Rules'],
  },
  {
    icon: <Factory size={26} color="#059669" />,
    title: 'Heavy Industry, Steel & QCOs',
    standard: 'IS 1786, IS 269, IS 1489',
    accentColor: '#D1FAE5',
    borderColor: '#A7F3D0',
    description:
      'Ensure strict conformity with Ministry of Steel, Cement, and DPIIT Quality Control Orders (QCOs). Prevent custom seizures and supply chain delays at Indian ports.',
    features: ['Chemical & Tensile Parameters', 'Factory Surveillance Audits', 'Port Import Clearance Rules', 'Surplus Stock Disposals'],
  },
  {
    icon: <Building2 size={26} color="#6366F1" />,
    title: 'Foreign Manufacturers (FMCS)',
    standard: 'Scheme I - Overseas Plants',
    accentColor: '#EEF2FF',
    borderColor: '#C7D2FE',
    description:
      'Dedicated guidance for international manufacturers exporting to India. Master Authorized Indian Representative (AIR) agreements, bank guarantees, and factory inspection logistics.',
    features: ['AIR Legal Responsibility', 'USD 10K Performance Guarantee', 'Pre-Inspection Factory Audit', 'Sample Import Duty Exemption'],
  },
  {
    icon: <FlaskConical size={26} color="#2563EB" />,
    title: 'BIS Testing Labs & NABL Locator',
    standard: 'ISO/IEC 17025 Conformity',
    accentColor: '#EFF6FF',
    borderColor: '#BFDBFE',
    description:
      'Locate recognized government and private laboratories for sample testing. Cross-reference testing capability matrices, scope schedules, and turn-around times.',
    features: ['2,000+ Recognized Lab Network', 'Chemical & Physical Testing Matrix', 'Dispute Sample Testing Protocol', 'Valid NABL Accreditation Scope'],
  },
  {
    icon: <ShieldCheck size={26} color="#0284C7" />,
    title: 'Toys, Chemicals & Consumer Safety',
    standard: 'IS 9873 & Mandatory QCOs',
    accentColor: '#F0FDFA',
    borderColor: '#99F6E4',
    description:
      'Comprehensive safety directives for electric and non-electric toys, industrial chemicals, caustic soda, fertilizers, and child safety products under mandatory ISI licensing.',
    features: ['Mechanical Safety & Flammability', 'Heavy Metal Phthalate Migration', 'Factory Quality Manual Prep', 'Customs Harmonized Codes (HSN)'],
  },
];

// --------------------------------------------------------------------------- //
// FAQ Accordion Data
// --------------------------------------------------------------------------- //
const FAQ_ITEMS = [
  {
    id: 'faq-1',
    question: 'How does BIS SATHI guarantee accurate Indian Standards citations without LLM hallucination?',
    answer:
      'Unlike generic public LLMs that extrapolate from unverified training data, BIS SATHI implements an authoritative Agentic RAG pipeline. Every user prompt undergoes strict semantic classification and is grounded against official Gazette Quality Control Orders, BIS product manuals, and indexed Indian Standard specifications stored in high-dimensional vector embeddings with BM25 hybrid ranking. Citations include authentic IS codes, gazette notification numbers, and clause references.',
  },
  {
    id: 'faq-2',
    question: 'What is the 6-digit HUID and when is it legally mandatory for Indian jewelers?',
    answer:
      'HUID (Hallmarking Unique Identification) is a 6-digit alphanumeric code laser-etched onto every piece of gold jewellery alongside the BIS logo and purity mark (e.g., 22K916). Hallmarking is mandatory across all notified districts in India for 14K, 18K, 20K, 22K, 23K, and 24K items. Jewelers cannot legally sell gold jewellery without HUID unless specifically exempted under special weight or trade categories.',
  },
  {
    id: 'faq-3',
    question: 'Can foreign manufacturers get certified under BIS without an entity in India?',
    answer:
      'Yes, through the Foreign Manufacturers Certification Scheme (FMCS). The foreign entity does not need a local branch office, but must formally appoint an Authorized Indian Representative (AIR) residing in India who will act as the local liaison and sign the legal indemnity agreement on behalf of the overseas applicant.',
  },
  {
    id: 'faq-4',
    question: 'What is the difference between BIS ISI Mark Certification and MeitY CRS Registration?',
    answer:
      'BIS ISI Mark (Scheme I) is primarily for industrial products, steel, cement, chemicals, and consumer safety goods; it mandates comprehensive factory audits and in-house laboratory equipment. MeitY CRS (Scheme II) is a self-declaration scheme for electronic and IT products where products are tested in accredited Indian laboratories and registered digitally through the portal without mandatory prior overseas factory visits.',
  },
  {
    id: 'faq-5',
    question: 'How does the 0-Token Instant Cache work?',
    answer:
      'Frequently asked compliance directives, chemical grade specifications, and statutory gazette deadlines are pre-computed and stored in high-performance semantic cache stores. When a matching query is detected, BIS SATHI returns the verified compliance answer in under 0.05 seconds with zero LLM API token consumption, cutting enterprise operational overhead.',
  },
];

export const LandingPage: React.FC<LandingPageProps> = ({ onOpenLogin, onOpenSignup }) => {
  // Mobile Nav Drawer Toggle
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // State for Interactive Simulator
  const [activeSimTab, setActiveSimTab] = useState<string>('gold-hallmark');

  // State for Readiness Calculator
  const [readinessChecks, setReadinessChecks] = useState<Record<string, boolean>>({
    inHouseLab: true,
    calibrationCert: true,
    airAppointed: false,
    form1Filled: true,
    labTestReport: false,
    qualityManual: false,
  });

  // State for FAQ Accordion
  const [expandedFaqId, setExpandedFaqId] = useState<string | null>('faq-1');

  const selectedPreset = SIMULATOR_PRESETS.find((p) => p.id === activeSimTab) || SIMULATOR_PRESETS[0];

  const totalChecks = Object.keys(readinessChecks).length;
  const passedChecks = Object.values(readinessChecks).filter(Boolean).length;
  const readinessPercentage = Math.round((passedChecks / totalChecks) * 100);

  const toggleCheck = (key: string) => {
    setReadinessChecks((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const closeMobileMenu = () => setIsMobileMenuOpen(false);

  return (
    <div className="landing-ambient-bg" style={{ minHeight: '100vh', color: '#1E293B', display: 'flex', flexDirection: 'column', overflowX: 'hidden', background: "#F8FAFC" }}>

      {/* ------------------------------------------------------------------- */}
      {/* Sticky Header Navigation */}
      {/* ------------------------------------------------------------------- */}
      <nav
        style={{
          height: '64px',
          padding: '0 clamp(16px, 3vw, 32px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #E2E8F0',
          backgroundColor: '#FFFFFF',
          position: 'sticky',
          top: 0,
          paddingBlock: "40px",
          zIndex: 60,
        }}
      >
        {/* Brand & Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BisLogo size={32} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.15rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#0F172A' }}>
                BIS SATHI
              </span>
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  padding: '2px 6px',
                  borderRadius: '6px',
                  backgroundColor: '#EFF6FF',
                  border: '1px solid #BFDBFE',
                  color: '#1D4ED8',
                  letterSpacing: '0.04em',
                }}
              >
                v2.4
              </span>
            </div>
            <span className="landing-header-sublabel" style={{ fontSize: '0.70rem', color: '#64748B', fontWeight: 500 }}>
              Bureau of Indian Standards AI Assistant
            </span>
          </div>
        </div>

        {/* Desktop Anchor Navigation Links */}
        <div className="landing-nav-links" style={{ display: 'flex', alignItems: 'center', gap: '24px', fontSize: '0.86rem', fontWeight: 500 }}>
          <a href="#simulator" style={{ color: '#475569', textDecoration: 'none', transition: 'color 0.2s' }} onMouseEnter={(e) => (e.currentTarget.style.color = '#0F172A')} onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}>
            Live Simulator
          </a>
          <a href="#domains" style={{ color: '#475569', textDecoration: 'none', transition: 'color 0.2s' }} onMouseEnter={(e) => (e.currentTarget.style.color = '#0F172A')} onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}>
            Standards Directory
          </a>
          <a href="#architecture" style={{ color: '#475569', textDecoration: 'none', transition: 'color 0.2s' }} onMouseEnter={(e) => (e.currentTarget.style.color = '#0F172A')} onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}>
            Pipeline
          </a>
          <a href="#readiness" style={{ color: '#475569', textDecoration: 'none', transition: 'color 0.2s' }} onMouseEnter={(e) => (e.currentTarget.style.color = '#0F172A')} onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}>
            Readiness
          </a>
          <a href="#faq" style={{ color: '#475569', textDecoration: 'none', transition: 'color 0.2s' }} onMouseEnter={(e) => (e.currentTarget.style.color = '#0F172A')} onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}>
            FAQ
          </a>
        </div>

        {/* Action CTAs Desktop & Mobile Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={onOpenLogin}
            className="btn-glass-outline"
            style={{
              padding: '7px 16px',
              borderRadius: '18px',
              fontSize: '0.84rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <LogIn size={14} />
            Sign In
          </button>
          <button
            onClick={onOpenSignup}
            className="btn-primary-shade header-hide-mobile"
            style={{
              padding: '7px 18px',
              borderRadius: '18px',
              fontSize: '0.84rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <UserPlus size={14} />
            <span>Create Account</span>
          </button>
          {/* Mobile Hamburger Toggle Button */}
          <button
            onClick={() => setIsMobileMenuOpen((prev) => !prev)}
            className="mobile-only-flex"
            style={{
              background: 'transparent',
              border: '1px solid #E2E8F0',
              color: '#0F172A',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '8px',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            aria-label="Toggle navigation menu"
          >
            {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </nav>

      {/* Mobile Navigation Dropdown Drawer */}
      {isMobileMenuOpen && (
        <div
          style={{
            position: 'sticky',
            top: '64px',
            zIndex: 55,
            backgroundColor: '#FFFFFF',
            borderBottom: '1px solid #E2E8F0',
            padding: '18px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
            boxShadow: '0 12px 28px rgba(0, 0, 0, 0.08)',
          }}
        >
          <a href="#simulator" onClick={closeMobileMenu} style={{ color: '#1E293B', textDecoration: 'none', fontSize: '0.95rem', padding: '6px 0' }}>
            ⚡ Live Simulator
          </a>
          <a href="#domains" onClick={closeMobileMenu} style={{ color: '#1E293B', textDecoration: 'none', fontSize: '0.95rem', padding: '6px 0' }}>
            📚 Standards Directory
          </a>
          <a href="#architecture" onClick={closeMobileMenu} style={{ color: '#1E293B', textDecoration: 'none', fontSize: '0.95rem', padding: '6px 0' }}>
            🛡️ Agentic Pipeline
          </a>
          <a href="#readiness" onClick={closeMobileMenu} style={{ color: '#1E293B', textDecoration: 'none', fontSize: '0.95rem', padding: '6px 0' }}>
            ✓ Readiness Audit
          </a>
          <a href="#faq" onClick={closeMobileMenu} style={{ color: '#1E293B', textDecoration: 'none', fontSize: '0.95rem', padding: '6px 0' }}>
            ❓ FAQ
          </a>
          <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
            <button
              onClick={() => { closeMobileMenu(); onOpenSignup(); }}
              className="btn-primary-shade"
              style={{ flex: 1, padding: '10px', borderRadius: '12px', fontSize: '0.88rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
            >
              <UserPlus size={15} /> Create Account
            </button>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Hero Section */}
      {/* ------------------------------------------------------------------- */}
      <section
        id="overview"
        style={{
          maxWidth: '1180px',
          margin: '0 auto',
          padding: 'clamp(40px, 7vw, 80px) clamp(16px, 4vw, 24px) clamp(36px, 5vw, 60px) clamp(16px, 4vw, 24px)',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '24px',
          position: 'relative',
          width: '100%',
        }}
      >
        {/* Shaded Announcement Pill */}
        <div className="landing-pill-badge">
          <Sparkles size={14} color="#2563EB" />
          <span style={{ fontSize: 'clamp(0.74rem, 1.6vw, 0.82rem)' }}>Next-Gen BIS Intelligence • 50,000+ Standards</span>
          <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#059669', flexShrink: 0 }} />
        </div>

        {/* Master Headline (Fluid clamp typography) */}
        <h1
          className="hero-title-responsive"
          style={{
            fontSize: 'clamp(2.1rem, 5vw, 3.8rem)',
            fontWeight: 800,
            letterSpacing: '-0.035em',
            lineHeight: '1.15',
            maxWidth: '960px',
            color: '#0F172A',
          }}
        >
          Instant BIS Compliance &{' '}
          <span style={{ color: "#2563EB" }}>Regulatory AI Intelligence</span>
        </h1>

        {/* Subtitle */}
        <p
          className="hero-subtitle-responsive"
          style={{
            fontSize: 'clamp(0.95rem, 1.8vw, 1.18rem)',
            color: '#475569',
            lineHeight: '1.65',
            maxWidth: '780px',
            fontWeight: 400,
          }}
        >
          Empowering Indian manufacturers, gold jewelers, electronics importers, and foreign factories with verified IS codes, 6-digit HUID rules, MeitY CRS filings, and audit-ready legal citations in sub-seconds.
        </p>

        {/* Primary CTA Buttons (Responsive Flex Group) */}
        <div className="hero-cta-group" style={{ display: 'flex', alignItems: 'center', gap: '14px', marginTop: '6px', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button
            onClick={onOpenLogin}
            className="btn-primary-shade"
            style={{
              padding: '14px 32px',
              borderRadius: '28px',
              fontSize: '1.0rem',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <span>Start Compliance Chat</span>
            <ArrowRight size={18} />
          </button>
          <a
            href="#simulator"
            className="btn-glass-outline"
            style={{
              padding: '14px 26px',
              borderRadius: '28px',
              fontSize: '1.0rem',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Zap size={16} color="#0284C7" />
            <span>Try Interactive Demo</span>
          </a>
        </div>

        {/* Quick Assurance Tags */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '18px', flexWrap: 'wrap', justifyContent: 'center', fontSize: '0.82rem', color: '#64748B', marginTop: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle2 size={15} color="#059669" />
            <span style={{ color: '#475569' }}>Gazette Cross-Checked</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Database size={15} color="#2563EB" />
            <span style={{ color: '#475569' }}>Supabase Audit Trail</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Lock size={15} color="#D97706" />
            <span style={{ color: '#475569' }}>Encrypted Sessions</span>
          </div>
        </div>

        {/* Key Metrics Counter Bar */}
        <div
          className="hero-metrics-bar"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))',
            gap: '14px',
            width: '100%',
            maxWidth: '1050px',
            marginTop: '20px',
          }}
        >
          <div className="metric-stat-box">
            <span style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.2rem)', fontWeight: 800, color: '#0F172A' }}>50,000+</span>
            <span style={{ fontSize: '0.80rem', color: '#64748B', marginTop: '2px' }}>Indian Standards Indexed</span>
            <span style={{ fontSize: '0.70rem', color: '#059669', marginTop: '2px', fontWeight: 600 }}>100% QCO Coverage</span>
          </div>
          <div className="metric-stat-box">
            <span style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.2rem)', fontWeight: 800, color: '#0284C7' }}>&lt; 0.2s</span>
            <span style={{ fontSize: '0.80rem', color: '#64748B', marginTop: '2px' }}>Semantic 0-Token Cache</span>
            <span style={{ fontSize: '0.70rem', color: '#0284C7', marginTop: '2px', fontWeight: 600 }}>Zero API Token Burn</span>
          </div>
          <div className="metric-stat-box">
            <span style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.2rem)', fontWeight: 800, color: '#2563EB' }}>99.4%</span>
            <span style={{ fontSize: '0.80rem', color: '#64748B', marginTop: '2px' }}>Retrieval Precision</span>
            <span style={{ fontSize: '0.70rem', color: '#2563EB', marginTop: '2px', fontWeight: 600 }}>Zero Hallucination</span>
          </div>
          <div className="metric-stat-box">
            <span style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.2rem)', fontWeight: 800, color: '#D97706' }}>2,000+</span>
            <span style={{ fontSize: '0.80rem', color: '#64748B', marginTop: '2px' }}>Testing Lab Networks</span>
            <span style={{ fontSize: '0.70rem', color: '#D97706', marginTop: '2px', fontWeight: 600 }}>NABL & BIS Recognized</span>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* Interactive Live Compliance Simulator */}
      {/* ------------------------------------------------------------------- */}
      <section
        id="simulator"
        style={{
          maxWidth: '1140px',
          margin: '0 auto',
          padding: 'clamp(40px, 6vw, 60px) clamp(14px, 3vw, 24px) clamp(50px, 6vw, 80px) clamp(14px, 3vw, 24px)',
          width: '100%',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div className="landing-pill-badge" style={{ marginBottom: '12px' }}>
            <Activity size={14} color="#0284C7" />
            <span>Interactive Compliance Sandbox</span>
          </div>
          <h2 style={{ fontSize: 'clamp(1.8rem, 3.8vw, 2.4rem)', fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em' }}>
            Test Real-World Compliance Inquiries
          </h2>
          <p style={{ fontSize: '0.98rem', color: '#64748B', maxWidth: '640px', margin: '6px auto 0 auto' }}>
            Click below to inspect how BIS SATHI classifies intents, extracts precise Indian Standards, and generates verified guidance.
          </p>
        </div>

        {/* Simulator Category Selector Tabs (Swipeable on Mobile) */}
        <div
          className="no-scrollbar"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            overflowX: 'auto',
            WebkitOverflowScrolling: 'touch',
            paddingBottom: '12px',
            marginBottom: '20px',
            justifyContent: 'flex-start',
          }}
        >
          {SIMULATOR_PRESETS.map((preset) => {
            const isActive = preset.id === activeSimTab;
            return (
              <button
                key={preset.id}
                onClick={() => setActiveSimTab(preset.id)}
                style={{
                  padding: '9px 16px',
                  borderRadius: '999px',
                  fontSize: '0.82rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: isActive ? '#EFF6FF' : '#FFFFFF',
                  borderColor: isActive ? '#93C5FD' : '#E2E8F0',
                  borderWidth: '1px',
                  borderStyle: 'solid',
                  color: isActive ? '#1D4ED8' : '#475569',
                  transition: 'all 0.2s ease',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                  boxShadow: isActive ? '0 2px 8px rgba(37, 99, 235, 0.12)' : 'none',
                }}
              >
                <span>{preset.category}</span>
                <span
                  style={{
                    fontSize: '0.70rem',
                    padding: '2px 7px',
                    borderRadius: '8px',
                    backgroundColor: isActive ? '#2563EB' : '#F1F5F9',
                    color: isActive ? '#FFFFFF' : '#64748B',
                    fontWeight: 600,
                  }}
                >
                  {preset.badge}
                </span>
              </button>
            );
          })}
        </div>

        {/* Live Simulator Viewport Card */}
        <div
          className="landing-interactive-card"
          style={{
            padding: 'clamp(18px, 3vw, 32px)',
            border: '1px solid #E2E8F0',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.05)',
          }}
        >
          {/* Query Box Bar */}
          <div
            className="simulator-query-bar"
            style={{
              padding: '14px 18px',
              borderRadius: '14px',
              backgroundColor: '#F8FAFC',
              border: '1px solid #E2E8F0',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '20px',
            }}
          >
            <div style={{ width: '32px', height: '32px', borderRadius: '50%', backgroundColor: '#EFF6FF', border: '1px solid #BFDBFE', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <span style={{ fontSize: '1.0rem' }}>💬</span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.72rem', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
                Simulated User Query
              </div>
              <div style={{ fontSize: 'clamp(0.92rem, 1.8vw, 1.02rem)', color: '#0F172A', fontWeight: 600, marginTop: '2px', wordBreak: 'break-word' }}>
                "{selectedPreset.query}"
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <span style={{ fontSize: '0.74rem', padding: '4px 10px', borderRadius: '8px', backgroundColor: '#ECFDF5', color: '#059669', fontWeight: 600, border: '1px solid #A7F3D0' }}>
                Confidence {selectedPreset.confidence}%
              </span>
            </div>
          </div>

          {/* AI Response Card Container (Responsive 2-column or 1-column stack) */}
          <div className="landing-simulator-grid">
            {/* Left: Detailed Answer & Key Roadmaps */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BisLogo size={22} />
                <span style={{ fontSize: '0.90rem', fontWeight: 700, color: '#0F172A' }}>BIS SATHI Official RAG Synthesis</span>
              </div>

              <p style={{ fontSize: '0.94rem', color: '#334155', lineHeight: '1.65' }}>
                {selectedPreset.answerSummary}
              </p>

              <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '14px', padding: '14px' }}>
                <div style={{ fontSize: '0.80rem', fontWeight: 700, color: '#0284C7', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <FileCheck size={15} /> Statutory Roadmap & Action Items
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {selectedPreset.keyPoints.map((pt, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: '0.86rem', color: '#334155' }}>
                      <Check size={15} color="#059669" style={{ flexShrink: 0, marginTop: '2px' }} />
                      <span>{pt}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ fontSize: '0.76rem', color: '#64748B', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Shield size={13} color="#D97706" style={{ flexShrink: 0 }} />
                <span>{selectedPreset.mandatoryClause}</span>
              </div>
            </div>

            {/* Right: Technical Metadata & Audit Telemetry */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Standard Citation Card */}
              <div style={{ backgroundColor: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: '14px', padding: '16px' }}>
                <div style={{ fontSize: '0.70rem', color: '#1D4ED8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Verified Standard Citation
                </div>
                <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0F172A', marginTop: '4px' }}>
                  {selectedPreset.standardCode}
                </div>
                <div style={{ fontSize: '0.82rem', color: '#475569', marginTop: '4px', lineHeight: '1.4' }}>
                  {selectedPreset.standardTitle}
                </div>
              </div>

              {/* RAG Telemetry Specs */}
              <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '14px', padding: '14px', fontSize: '0.80rem', display: 'flex', flexDirection: 'column', gap: '9px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #E2E8F0', paddingBottom: '6px' }}>
                  <span style={{ color: '#64748B' }}>Classified Intent</span>
                  <span style={{ color: '#4F46E5', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{selectedPreset.intent}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #E2E8F0', paddingBottom: '6px' }}>
                  <span style={{ color: '#64748B' }}>Response Latency</span>
                  <span style={{ color: '#059669', fontWeight: 600 }}>{selectedPreset.latency}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #E2E8F0', paddingBottom: '6px' }}>
                  <span style={{ color: '#64748B' }}>LLM Tokens Burned</span>
                  <span style={{ color: selectedPreset.tokensBurned === 0 ? '#059669' : '#0F172A', fontWeight: 600 }}>
                    {selectedPreset.tokensBurned} Tokens
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748B' }}>Cache Status</span>
                  <span style={{ color: '#D97706', fontWeight: 600 }}>{selectedPreset.cacheStatus}</span>
                </div>
              </div>

              {/* Action Button inside simulator */}
              <button
                onClick={onOpenLogin}
                className="btn-primary-shade"
                style={{
                  marginTop: 'auto',
                  padding: '12px 18px',
                  borderRadius: '12px',
                  fontSize: '0.86rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  width: '100%',
                }}
              >
                <span>Ask your specific BIS query</span>
                <ArrowUpRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* Multi-Domain Regulatory Directory */}
      {/* ------------------------------------------------------------------- */}
      <section
        id="domains"
        style={{
          maxWidth: '1180px',
          margin: '0 auto',
          padding: 'clamp(40px, 6vw, 60px) clamp(16px, 3vw, 24px) clamp(50px, 6vw, 80px) clamp(16px, 3vw, 24px)',
          width: '100%',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '36px' }}>
          <div className="landing-pill-badge" style={{ marginBottom: '12px' }}>
            <Layers size={14} color="#818CF8" />
            <span>Multi-Domain Coverage</span>
          </div>
          <h2 style={{ fontSize: 'clamp(1.8rem, 3.8vw, 2.4rem)', fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em' }}>
            Comprehensive Standards & Mandates Directory
          </h2>
          <p style={{ fontSize: '1.0rem', color: '#64748B', maxWidth: '680px', margin: '6px auto 0 auto' }}>
            Covering every notified sector regulated under the Bureau of Indian Standards Act, 2016 and statutory Quality Control Orders.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))', gap: '20px' }}>
          {DOMAIN_CARDS.map((card, idx) => (
            <div
              key={idx}
              className="landing-interactive-card"
              style={{
                padding: 'clamp(20px, 3vw, 28px)',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ padding: '10px', borderRadius: '14px', backgroundColor: card.accentColor, border: `1px solid ${card.borderColor}` }}>
                  {card.icon}
                </div>
                <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '3px 8px', borderRadius: '8px', backgroundColor: '#F1F5F9', color: '#475569', border: '1px solid #E2E8F0' }}>
                  {card.standard}
                </span>
              </div>

              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#0F172A' }}>
                  {card.title}
                </h3>
                <p style={{ fontSize: '0.88rem', color: '#475569', lineHeight: '1.6', marginTop: '6px' }}>
                  {card.description}
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: 'auto', paddingTop: '12px', borderTop: '1px solid #E2E8F0' }}>
                {card.features.map((feat, fIdx) => (
                  <div key={fIdx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.80rem', color: '#334155' }}>
                    <CheckCircle2 size={13} color="#2563EB" style={{ flexShrink: 0 }} />
                    <span>{feat}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* Agentic RAG Architecture & Governance Section */}
      {/* ------------------------------------------------------------------- */}
      <section
        id="architecture"
        style={{
          maxWidth: '1180px',
          margin: '0 auto',
          padding: 'clamp(40px, 6vw, 60px) clamp(16px, 3vw, 24px) clamp(50px, 6vw, 80px) clamp(16px, 3vw, 24px)',
          width: '100%',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '36px' }}>
          <div className="landing-pill-badge" style={{ marginBottom: '12px' }}>
            <Award size={14} color="#D97706" />
            <span>Engineered for Zero Hallucination</span>
          </div>
          <h2 style={{ fontSize: 'clamp(1.8rem, 3.8vw, 2.4rem)', fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em' }}>
            How BIS SATHI Works: 4-Stage Agentic RAG
          </h2>
          <p style={{ fontSize: '1.0rem', color: '#64748B', maxWidth: '680px', margin: '6px auto 0 auto' }}>
            Generic AI models fail at legal compliance due to dated knowledge cutoffs and hallucinations. BIS SATHI uses strict multi-stage verification.
          </p>
        </div>

        {/* 4-Stage Pipeline Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 230px), 1fr))', gap: '18px', marginBottom: '36px' }}>
          <div className="landing-interactive-card" style={{ padding: '22px' }}>
            <div style={{ width: '38px', height: '38px', borderRadius: '12px', backgroundColor: '#EFF6FF', border: '1px solid #BFDBFE', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1D4ED8', fontWeight: 800, fontSize: '1.05rem', marginBottom: '12px' }}>
              01
            </div>
            <h4 style={{ fontSize: '1.0rem', fontWeight: 700, color: '#0F172A' }}>
              Intent Classification
            </h4>
            <p style={{ fontSize: '0.85rem', color: '#475569', lineHeight: '1.55', marginTop: '6px' }}>
              Decodes user queries to identify specific regulatory regimes: HUID Gold, MeitY CRS, FMCS, or Industrial QCOs.
            </p>
          </div>

          <div className="landing-interactive-card" style={{ padding: '22px' }}>
            <div style={{ width: '38px', height: '38px', borderRadius: '12px', backgroundColor: '#F5F3FF', border: '1px solid #DDD6FE', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6D28D9', fontWeight: 800, fontSize: '1.05rem', marginBottom: '12px' }}>
              02
            </div>
            <h4 style={{ fontSize: '1.0rem', fontWeight: 700, color: '#0F172A' }}>
              Hybrid Vector + BM25 Search
            </h4>
            <p style={{ fontSize: '0.85rem', color: '#475569', lineHeight: '1.55', marginTop: '6px' }}>
              Simultaneously searches semantic vector embeddings and exact lexical standard numbers (e.g., IS 1417, IS 13252).
            </p>
          </div>

          <div className="landing-interactive-card" style={{ padding: '22px' }}>
            <div style={{ width: '38px', height: '38px', borderRadius: '12px', backgroundColor: '#F0F9FF', border: '1px solid #BAE6FD', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0284C7', fontWeight: 800, fontSize: '1.05rem', marginBottom: '12px' }}>
              03
            </div>
            <h4 style={{ fontSize: '1.0rem', fontWeight: 700, color: '#0F172A' }}>
              Dual Gazette Cross-Check
            </h4>
            <p style={{ fontSize: '0.85rem', color: '#475569', lineHeight: '1.55', marginTop: '6px' }}>
              Every recommendation is cross-referenced with latest S.O. Gazette notifications to verify if a standard is voluntary or mandatory.
            </p>
          </div>

          <div className="landing-interactive-card" style={{ padding: '22px' }}>
            <div style={{ width: '38px', height: '38px', borderRadius: '12px', backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#059669', fontWeight: 800, fontSize: '1.05rem', marginBottom: '12px' }}>
              04
            </div>
            <h4 style={{ fontSize: '1.0rem', fontWeight: 700, color: '#0F172A' }}>
              Audit Ledger Hash
            </h4>
            <p style={{ fontSize: '0.85rem', color: '#475569', lineHeight: '1.55', marginTop: '6px' }}>
              Generates cryptographic audit ledger entries for compliance officers to prove regulatory due diligence during factory audits.
            </p>
          </div>
        </div>

        {/* Comparison Table Card (With responsive table-scroll-container) */}
        <div
          className="landing-interactive-card"
          style={{
            padding: 'clamp(20px, 3vw, 32px)',
            border: '1px solid #E2E8F0',
          }}
        >
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#0F172A', marginBottom: '16px', textAlign: 'center' }}>
            Why Enterprise Teams Choose BIS SATHI over Generic AI
          </h3>

          <div className="table-scroll-container">
            <table style={{ width: '100%', minWidth: '580px', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #E2E8F0', backgroundColor: '#F8FAFC' }}>
                  <th style={{ padding: '12px 14px', color: '#64748B', fontWeight: 600 }}>Feature Capability</th>
                  <th style={{ padding: '12px 14px', color: '#1D4ED8', fontWeight: 700 }}>BIS SATHI RAG Agent</th>
                  <th style={{ padding: '12px 14px', color: '#64748B', fontWeight: 600 }}>Generic LLMs (ChatGPT / Claude)</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid #E2E8F0' }}>
                  <td style={{ padding: '12px 14px', fontWeight: 600, color: '#0F172A' }}>Standard Code Authenticity</td>
                  <td style={{ padding: '12px 14px', color: '#059669', fontWeight: 600 }}>✓ 100% Verified against official BIS Gazette</td>
                  <td style={{ padding: '12px 14px', color: '#64748B' }}>✗ Prone to inventing fictitious IS numbers</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #E2E8F0' }}>
                  <td style={{ padding: '12px 14px', fontWeight: 600, color: '#0F172A' }}>Mandatory QCO Timelines</td>
                  <td style={{ padding: '12px 14px', color: '#059669', fontWeight: 600 }}>✓ Tracks real-time extension orders & cutoffs</td>
                  <td style={{ padding: '12px 14px', color: '#64748B' }}>✗ Uses obsolete training cutoff dates</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #E2E8F0' }}>
                  <td style={{ padding: '12px 14px', fontWeight: 600, color: '#0F172A' }}>0-Token Response Caching</td>
                  <td style={{ padding: '12px 14px', color: '#059669', fontWeight: 600 }}>✓ Instant &lt; 0.05s response for frequent standards</td>
                  <td style={{ padding: '12px 14px', color: '#64748B' }}>✗ Re-generates each time with recurring token costs</td>
                </tr>
                <tr>
                  <td style={{ padding: '12px 14px', fontWeight: 600, color: '#0F172A' }}>Compliance Audit Ledger</td>
                  <td style={{ padding: '12px 14px', color: '#059669', fontWeight: 600 }}>✓ SHA-256 verifiable query audit logging</td>
                  <td style={{ padding: '12px 14px', color: '#64748B' }}>✗ No statutory audit tracking</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* Interactive Document Readiness Calculator */}
      {/* ------------------------------------------------------------------- */}
      <section
        id="readiness"
        style={{
          maxWidth: '1000px',
          margin: '0 auto',
          padding: 'clamp(40px, 6vw, 60px) clamp(16px, 3vw, 24px) clamp(50px, 6vw, 80px) clamp(16px, 3vw, 24px)',
          width: '100%',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
          <div className="landing-pill-badge" style={{ marginBottom: '12px' }}>
            <FileCheck size={14} color="#059669" />
            <span>Interactive Audit Readiness Tool</span>
          </div>
          <h2 style={{ fontSize: 'clamp(1.8rem, 3.8vw, 2.4rem)', fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em' }}>
            BIS Certification Readiness Score
          </h2>
          <p style={{ fontSize: '0.98rem', color: '#64748B', maxWidth: '620px', margin: '6px auto 0 auto' }}>
            Select your current manufacturing & regulatory documentation status to check your estimated audit readiness.
          </p>
        </div>

        <div
          className="landing-interactive-card"
          style={{
            padding: 'clamp(20px, 4vw, 36px)',
            border: '1px solid #E2E8F0',
          }}
        >
          {/* Progress Bar & Readiness Status */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', flexWrap: 'wrap', gap: '6px' }}>
              <span style={{ fontSize: '0.90rem', fontWeight: 700, color: '#0F172A' }}>
                Application Readiness Level:
              </span>
              <span
                style={{
                  fontSize: 'clamp(1.05rem, 2vw, 1.25rem)',
                  fontWeight: 800,
                  color: readinessPercentage >= 80 ? '#059669' : readinessPercentage >= 50 ? '#D97706' : '#DC2626',
                }}
              >
                {readinessPercentage}% {readinessPercentage >= 80 ? '(Ready)' : readinessPercentage >= 50 ? '(In Progress)' : '(Incomplete)'}
              </span>
            </div>

            {/* Visual Bar with Solid Shades */}
            <div style={{ width: '100%', height: '10px', backgroundColor: '#E2E8F0', borderRadius: '999px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${readinessPercentage}%`,
                  height: '100%',
                  backgroundColor: readinessPercentage >= 80 ? '#059669' : '#2563EB',
                  transition: 'width 0.35s ease',
                }}
              />
            </div>
          </div>

          {/* Checklist Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))', gap: '12px' }}>
            {[
              { id: 'inHouseLab', label: 'In-house test equipment matching Indian Standard specifications' },
              { id: 'calibrationCert', label: 'Valid NABL calibration certificates for all testing instruments' },
              { id: 'airAppointed', label: 'Authorized Indian Representative (AIR) appointed (for foreign plants)' },
              { id: 'form1Filled', label: 'Form I / Form VI application draft prepared with BOM schedule' },
              { id: 'labTestReport', label: 'Sample test report from BIS recognized lab (<90 days old)' },
              { id: 'qualityManual', label: 'Factory Quality Control Manual conforming to Scheme I guidelines' },
            ].map((item) => {
              const isChecked = readinessChecks[item.id];
              return (
                <div
                  key={item.id}
                  onClick={() => toggleCheck(item.id)}
                  style={{
                    padding: '12px 14px',
                    borderRadius: '12px',
                    backgroundColor: isChecked ? '#EFF6FF' : '#F8FAFC',
                    border: `1px solid ${isChecked ? '#3B82F6' : '#E2E8F0'}`,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    transition: 'all 0.2s ease',
                    minHeight: '48px',
                  }}
                >
                  <div
                    style={{
                      width: '22px',
                      height: '22px',
                      borderRadius: '6px',
                      backgroundColor: isChecked ? '#2563EB' : '#FFFFFF',
                      border: isChecked ? 'none' : '1px solid #CBD5E1',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      transition: 'background 0.2s ease',
                    }}
                  >
                    {isChecked && <Check size={14} color="#FFFFFF" />}
                  </div>
                  <span style={{ fontSize: '0.84rem', color: isChecked ? '#0F172A' : '#475569', fontWeight: isChecked ? 600 : 400, lineHeight: '1.4' }}>
                    {item.label}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Action Prompt */}
          <div style={{ marginTop: '20px', padding: '14px', backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
            <span style={{ fontSize: '0.84rem', color: '#475569' }}>
              Need help obtaining missing calibration reports or lab test documentation?
            </span>
            <button
              onClick={onOpenLogin}
              className="btn-glass-outline"
              style={{ padding: '8px 16px', borderRadius: '16px', fontSize: '0.82rem' }}
            >
              Get Guidance in Chat →
            </button>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* FAQ Accordion Section */}
      {/* ------------------------------------------------------------------- */}
      <section
        id="faq"
        style={{
          maxWidth: '880px',
          margin: '0 auto',
          padding: 'clamp(40px, 6vw, 60px) clamp(16px, 3vw, 24px) clamp(50px, 6vw, 80px) clamp(16px, 3vw, 24px)',
          width: '100%',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div className="landing-pill-badge" style={{ marginBottom: '12px' }}>
            <BookOpen size={14} color="#D97706" />
            <span>Answers to Critical Regulatory Questions</span>
          </div>
          <h2 style={{ fontSize: 'clamp(1.8rem, 3.8vw, 2.4rem)', fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em' }}>
            Frequently Asked Questions
          </h2>
          <p style={{ fontSize: '0.98rem', color: '#64748B', margin: '6px auto 0 auto' }}>
            Key statutory clarifications regarding BIS licensing, HUID rules, and AI assistance.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {FAQ_ITEMS.map((item) => {
            const isOpen = expandedFaqId === item.id;
            return (
              <div
                key={item.id}
                style={{
                  backgroundColor: isOpen ? '#F8FAFC' : '#FFFFFF',
                  border: `1px solid ${isOpen ? '#93C5FD' : '#E2E8F0'}`,
                  borderRadius: '14px',
                  overflow: 'hidden',
                  transition: 'all 0.2s ease',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.03)',
                }}
              >
                <button
                  onClick={() => setExpandedFaqId(isOpen ? null : item.id)}
                  style={{
                    width: '100%',
                    padding: 'clamp(14px, 2.5vw, 18px) clamp(16px, 3vw, 22px)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    backgroundColor: 'transparent',
                    border: 'none',
                    color: '#0F172A',
                    fontSize: 'clamp(0.92rem, 1.8vw, 1.02rem)',
                    fontWeight: 600,
                    textAlign: 'left',
                    cursor: 'pointer',
                    gap: '12px',
                  }}
                >
                  <span>{item.question}</span>
                  <ChevronDown
                    size={18}
                    style={{
                      transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.25s ease',
                      flexShrink: 0,
                      color: isOpen ? '#2563EB' : '#64748B',
                    }}
                  />
                </button>
                {isOpen && (
                  <div
                    style={{
                      padding: '0 clamp(16px, 3vw, 22px) clamp(14px, 2.5vw, 20px) clamp(16px, 3vw, 22px)',
                      color: '#475569',
                      fontSize: '0.90rem',
                      lineHeight: '1.65',
                      borderTop: '1px solid #E2E8F0',
                      paddingTop: '12px',
                    }}
                  >
                    {item.answer}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* Pre-Footer Call to Action Banner */}
      {/* ------------------------------------------------------------------- */}
      <section style={{ maxWidth: '1100px', margin: '0 auto clamp(40px, 6vw, 80px) auto', padding: '0 clamp(16px, 3vw, 24px)', width: '100%' }}>
        <div
          style={{
            backgroundColor: '#FFFFFF',
            border: '1px solid #BFDBFE',
            borderRadius: '24px',
            padding: 'clamp(32px, 5vw, 50px) clamp(18px, 4vw, 32px)',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '18px',
            boxShadow: '0 20px 50px rgba(37, 99, 235, 0.08), 0 4px 12px rgba(0, 0, 0, 0.03)',
            background: 'linear-gradient(180deg, #FFFFFF 0%, #F0F7FF 100%)',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 14px',
              borderRadius: '20px',
              backgroundColor: '#EFF6FF',
              border: '1px solid #BFDBFE',
              color: '#1D4ED8',
              fontSize: '0.82rem',
              fontWeight: 600,
            }}
          >
            <Sparkles size={15} color="#2563EB" /> Ready to accelerate your compliance?
          </div>

          <h2
            className="pre-footer-title"
            style={{ fontSize: 'clamp(1.8rem, 4vw, 2.8rem)', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em', maxWidth: '720px' }}
          >
            Cut BIS Certification Delays by up to 70%
          </h2>

          <p style={{ fontSize: 'clamp(0.95rem, 1.8vw, 1.1rem)', color: '#475569', maxWidth: '640px', lineHeight: '1.6' }}>
            Join hundreds of manufacturers, retail jewelers, and compliance attorneys leveraging automated IS standard citations and real-time regulatory intelligence.
          </p>

          <div className="hero-cta-group" style={{ display: 'flex', alignItems: 'center', gap: '14px', marginTop: '6px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <button
              onClick={onOpenSignup}
              className="btn-primary-shade"
              style={{
                padding: '14px 32px',
                borderRadius: '28px',
                fontSize: '1.0rem',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
              }}
            >
              <span>Create Free Account</span>
              <ArrowRight size={18} />
            </button>
            <button
              onClick={onOpenLogin}
              className="btn-glass-outline"
              style={{
                padding: '14px 28px',
                borderRadius: '28px',
                fontSize: '1.0rem',
              }}
            >
              Sign In to Chat
            </button>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* Enterprise Footer */}
      {/* ------------------------------------------------------------------- */}
      <footer
        style={{
          borderTop: '1px solid #E2E8F0',
          padding: 'clamp(32px, 5vw, 48px) clamp(16px, 3vw, 32px) clamp(24px, 4vw, 32px) clamp(16px, 3vw, 32px)',
          backgroundColor: '#F8FAFC',
          fontSize: '0.84rem',
          color: '#64748B',
        }}
      >
        <div
          style={{
            maxWidth: '1180px',
            margin: '0 auto',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))',
            gap: '28px',
            marginBottom: '32px',
          }}
        >
          {/* Brand Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <BisLogo size={30} />
              <span style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A' }}>BIS SATHI</span>
            </div>
            <p style={{ fontSize: '0.80rem', color: '#475569', lineHeight: '1.6' }}>
              AI-Powered Agentic RAG Platform for Bureau of Indian Standards (BIS) compliance, Gold Hallmarking, MeitY CRS, and Foreign Manufacturer Schemes.
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#059669', fontSize: '0.76rem', fontWeight: 600 }}>
              <span style={{ display: 'inline-block', width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#059669' }} />
              <span>Vector Database & Agent Core Online</span>
            </div>
          </div>

          {/* Directory Links */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ color: '#0F172A', fontWeight: 700, fontSize: '0.88rem' }}>Compliance Directives</span>
            <span style={{ color: '#475569', cursor: 'pointer' }}>Gold Hallmarking (IS 1417)</span>
            <span style={{ color: '#475569', cursor: 'pointer' }}>Electronics CRS (IS 13252)</span>
            <span style={{ color: '#475569', cursor: 'pointer' }}>Lithium Batteries (IS 16046)</span>
            <span style={{ color: '#475569', cursor: 'pointer' }}>TMT Steel & Cement QCOs</span>
            <span style={{ color: '#475569', cursor: 'pointer' }}>FMCS Foreign Plants</span>
          </div>

          {/* Testing & Accreditation */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ color: '#0F172A', fontWeight: 700, fontSize: '0.88rem' }}>Official Portals</span>
            <a href="https://www.services.bis.gov.in" target="_blank" rel="noopener noreferrer" style={{ color: '#475569', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>manakonline.in</span>
              <ExternalLink size={12} />
            </a>
            <a href="https://www.crsbis.in" target="_blank" rel="noopener noreferrer" style={{ color: '#475569', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>crsbis.in (MeitY Portal)</span>
              <ExternalLink size={12} />
            </a>
            <a href="https://nabl-india.org" target="_blank" rel="noopener noreferrer" style={{ color: '#475569', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>NABL Lab Directory</span>
              <ExternalLink size={12} />
            </a>
          </div>

          {/* Architecture & Tech */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ color: '#0F172A', fontWeight: 700, fontSize: '0.88rem' }}>Technology & Security</span>
            <span style={{ color: '#475569' }}>FastAPI & Asynchronous Engine</span>
            <span style={{ color: '#475569' }}>Supabase PostgreSQL & Vector Store</span>
            <span style={{ color: '#475569' }}>0-Token Front-Loaded Semantic Cache</span>
            <span style={{ color: '#475569' }}>SHA-256 Audit Trail Encryption</span>
          </div>
        </div>

        {/* Bottom Legal & Disclaimer */}
        <div
          style={{
            maxWidth: '1180px',
            margin: '0 auto',
            paddingTop: '20px',
            borderTop: '1px solid #E2E8F0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '10px',
            fontSize: '0.76rem',
          }}
        >
          <div style={{ color: '#64748B' }}>
            © 2026 BIS SATHI. All Indian Standards trademarks belong to the Bureau of Indian Standards.
          </div>
          <div style={{ color: '#94A3B8' }}>
            Statutory AI Assistant built in conformity with the Bureau of Indian Standards Act, 2016.
          </div>
        </div>
      </footer>

    </div>
  );
};
