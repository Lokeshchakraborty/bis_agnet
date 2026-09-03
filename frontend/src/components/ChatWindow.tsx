import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, Sparkles, Zap, ChevronDown, ChevronUp, BookOpen, ArrowRight, Copy, ThumbsUp, ThumbsDown, Share2, Plus, Check } from 'lucide-react';
import type { ChatMessage } from '../types';




interface ChatWindowProps {
  messages: ChatMessage[];
  onSendMessage: (query: string) => void;
  onOpenVoiceModal: () => void;
  isLoading: boolean;
  onSelectFollowUp: (prompt: string) => void;
  backendStatus?: string;
}

const GEMINI_HOME_CARDS = [
  {
    title: 'Gold Hallmarking HUID',
    subtitle: 'Procedure & IS 1417 purity guidelines for jewellery manufacturers',
    prompt: 'What is the procedure for getting a Gold Hallmarking license under BIS?',
    icon: '✨',
  },
  {
    title: 'CRS Electronics Scheme',
    subtitle: 'Mandatory documentation for MeitY electronics & IT goods',
    prompt: 'What are the required compliance documents for electronics CRS registration?',
    icon: '📱',
  },
  {
    title: 'FMCS Overseas Certification',
    subtitle: 'Foreign Manufacturers Certification Scheme & AIR rules',
    prompt: 'Explain the Foreign Manufacturers Certification Scheme (FMCS) requirements.',
    icon: '🌏',
  },
  {
    title: 'Testing Lab Networks',
    subtitle: 'Search BIS & NABL accredited testing laboratory networks',
    prompt: 'How to check BIS recognized testing laboratory networks for steel testing?',
    icon: '🔬',
  },
];

const THINKING_STEPS = [
  '🔍 Classifying intent & IS standard codes...',
  '⚡ Checking 0-Token instant response cache...',
  '📚 Performing BM25 & dense vector retrieval...',
  '🗄️ Querying Supabase PostgreSQL knowledge base...',
  '✦ Synthesizing compliance report with IS standards...',
];

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  onSendMessage,
  onOpenVoiceModal,
  isLoading,
  onSelectFollowUp,
  backendStatus,
}) => {

  const [inputText, setInputText] = useState('');
  const [expandedDetails, setExpandedDetails] = useState<Record<string, boolean>>({});
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);
  const [loadingStepIdx, setLoadingStepIdx] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoading) {
      setLoadingStepIdx(0);
      return;
    }
    const interval = setInterval(() => {
      setLoadingStepIdx((prev) => (prev + 1) % THINKING_STEPS.length);
    }, 1200);
    return () => clearInterval(interval);
  }, [isLoading]);


  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;
    onSendMessage(inputText.trim());
    setInputText('');
  };

  const toggleDetails = (msgId: string) => {
    setExpandedDetails((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const handleCopyText = (msgId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(msgId);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  // Helper to parse basic markdown bold/list items cleanly for Compliance Mode
  const renderFormattedText = (text: string) => {
    const lines = text.split('\n');
    let subCounter = 0;

    return lines.map((line, idx) => {
      const trimmed = line.trim();
      if (line.startsWith('### ')) {
        subCounter = 0;
        return <h3 key={idx} style={{ fontSize: '1.2rem', fontWeight: 700, color: '#FFFFFF', marginTop: '20px', marginBottom: '10px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '4px' }}>{line.replace('### ', '')}</h3>;
      }
      if (line.startsWith('## ')) {
        subCounter = 0;
        return <h2 key={idx} style={{ fontSize: '1.35rem', fontWeight: 700, color: '#FFFFFF', marginTop: '22px', marginBottom: '12px' }}>{line.replace('## ', '')}</h2>;
      }

      // Sub-Bullet Points (Numbered: 1., 2., 3.)
      const isSubBullet = line.startsWith('  ') || line.startsWith('\t');
      const numMatch = trimmed.match(/^(\d+)[\.\)]\s+(.*)/);
      
      if (isSubBullet || (numMatch && !trimmed.startsWith('•') && !trimmed.startsWith('●'))) {
        subCounter += 1;
        const content = numMatch ? numMatch[2] : trimmed.replace(/^[\*\-\•\◦\d\.]+\s+/, '');
        const numberLabel = numMatch ? `${numMatch[1]}.` : `${subCounter}.`;

        return (
          <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginTop: '5px', marginBottom: '5px', paddingLeft: '0px' }}>
            <span style={{ color: '#D1D5DB', fontWeight: 'bold', fontSize: '0.92rem', lineHeight: '1.65', minWidth: '20px' }}>{numberLabel}</span>
            <div style={{ flex: 1, lineHeight: '1.65', color: '#D1D5DB', fontSize: '0.96rem' }}>
              {parseBold(content)}
            </div>
          </div>

        );
      }

      // Parent Level Bullet Points (White Big Solid Circle Bullet: ●)
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ') || trimmed.startsWith('● ')) {
        subCounter = 0;
        const content = trimmed.replace(/^[\-\*\•\●]\s+/, '');
        return (
          <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginTop: '16px', marginBottom: '8px', paddingLeft: '0px' }}>
            <span style={{ color: '#FFFFFF', fontSize: '1.4rem', lineHeight: '1.4', minWidth: '20px' }}>●</span>
            <div style={{ flex: 1, lineHeight: '1.6', color: '#FFFFFF', fontWeight: 700, fontSize: '1.2rem' }}>
              {parseBold(content)}
            </div>
          </div>
        );
      }


      subCounter = 0;
      if (trimmed === '') {
        return <div key={idx} style={{ height: '8px' }} />;
      }
      return (
        <p key={idx} style={{ marginBottom: '10px', lineHeight: '1.7', color: 'var(--text-main)', fontSize: '1.05rem' }}>
          {parseBold(line)}
        </p>
      );
    });
  };


  const parseBold = (str: string) => {
    const parts = str.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} style={{ color: '#FFFFFF', fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--gemini-bg-main)', position: 'relative' }}>
      {/* Gemini Stream Area */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {messages.length === 0 ? (
          <div style={{ margin: 'auto', maxWidth: '840px', width: '100%', padding: '40px 20px', display: 'flex', flexDirection: 'column', gap: '32px' }}>
            {/* Gemini Hero Greeting */}
            <div style={{ textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <h1 className="gemini-gradient-text" style={{ fontSize: '3.2rem', fontWeight: 600, letterSpacing: '-0.03em', lineHeight: '1.1' }}>
                Hello, Compliance Officer
              </h1>
              <h2 style={{ fontSize: '2.5rem', fontWeight: 500, color: 'var(--text-muted)' }}>
                How can I help with BIS standards today?
              </h2>
            </div>

            {/* 4 Gemini Prompt Recommendation Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
              {GEMINI_HOME_CARDS.map((card, idx) => (
                <div
                  key={idx}
                  className="gemini-card"
                  onClick={() => onSendMessage(card.prompt)}
                  style={{
                    padding: '20px',
                    minHeight: '150px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                  }}
                >
                  <p style={{ fontSize: '0.95rem', fontWeight: 500, color: 'var(--text-main)', lineHeight: '1.45' }}>
                    {card.title}
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '12px' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{card.subtitle}</span>
                    <span style={{ fontSize: '1.3rem', padding: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '50%' }}>{card.icon}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.sender === 'user';
            const res = msg.response;
            const isDetailsOpen = expandedDetails[msg.id] || false;

            return (
              <div
                key={msg.id}
                style={{
                  width: '100%',
                  padding: '16px 20px',
                }}
              >
                <div style={{ maxWidth: '820px', margin: '0 auto', display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
                  {isUser ? (
                    /* Google Gemini Style User Message Card on the Right */
                    <div
                      style={{
                        maxWidth: '75%',
                        background: '#282A2C',
                        border: '1px solid var(--glass-border)',
                        borderRadius: '24px 24px 4px 24px',
                        padding: '14px 22px',
                        color: '#FFFFFF',
                        fontSize: '1.05rem',
                        lineHeight: '1.6',
                        boxShadow: '0 4px 15px rgba(0, 0, 0, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                      }}
                    >
                      <span>{msg.text}</span>
                    </div>
                  ) : (
                    /* Gemini Assistant Response Block Aligned Flush with Input Box */
                    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {/* Formatted Markdown Body */}
                      <div className="markdown-body" style={{ fontSize: '1.05rem' }}>
                        {renderFormattedText(msg.text)}
                      </div>



                        {/* Action Toolbar */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '18px', marginTop: '14px', color: 'var(--text-muted)' }}>
                          <button
                            onClick={() => handleCopyText(msg.id, msg.text)}
                            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem' }}
                            title="Copy response"
                          >
                            {copiedMsgId === msg.id ? <Check size={16} color="#10B981" /> : <Copy size={16} />}
                            <span>{copiedMsgId === msg.id ? 'Copied' : ''}</span>
                          </button>

                          <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }} title="Good response">
                            <ThumbsUp size={16} />
                          </button>

                          <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }} title="Bad response">
                            <ThumbsDown size={16} />
                          </button>

                          <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }} title="Share response">
                            <Share2 size={16} />
                          </button>
                        </div>

                        {/* Gemini Expandable Telemetry Accordion */}
                        {res && (
                          <div style={{ marginTop: '10px', paddingTop: '12px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                            <button
                              onClick={() => toggleDetails(msg.id)}
                              style={{
                                background: 'rgba(255, 255, 255, 0.04)',
                                border: '1px solid var(--glass-border)',
                                borderRadius: '18px',
                                color: 'var(--text-subtle)',
                                fontSize: '0.82rem',
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '8px 14px',
                              }}
                            >
                              <Sparkles size={14} color="var(--gemini-purple)" />
                              <span>
                                {res.applicable_standards?.length ? `✦ View ${res.applicable_standards.length} IS Codes & Technical Telemetry` : '✦ View Technical Telemetry'}
                              </span>
                              {isDetailsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </button>

                            {isDetailsOpen && (
                              <div className="animate-fade-in" style={{ marginTop: '12px', padding: '16px', borderRadius: '16px', background: 'var(--gemini-bg-card)', border: '1px solid var(--glass-border)', display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.88rem' }}>
                                {/* Cache Hit Badge */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  {res.cache_hit ? (
                                    <span style={{ color: 'var(--gemini-gold)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                      <Zap size={15} /> ⚡ 0-Token Instant Cache Hit
                                    </span>
                                  ) : (
                                    <span style={{ color: 'var(--gemini-cyan)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                      <Sparkles size={15} /> LangGraph Hybrid RAG ({res.response_time_ms} ms)
                                    </span>
                                  )}
                                </div>

                                {/* Applicable IS Codes */}
                                {res.applicable_standards && res.applicable_standards.length > 0 && (
                                  <div>
                                    <span style={{ color: 'var(--text-muted)' }}>Applicable Standards:</span>
                                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
                                      {res.applicable_standards.map((st, i) => (
                                        <span key={i} style={{ background: 'rgba(6, 182, 212, 0.15)', border: '1px solid rgba(6, 182, 212, 0.3)', color: '#06B6D4', padding: '4px 10px', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 600 }}>
                                          {st}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* Citation */}
                                {res.source_citation && (
                                  <div style={{ color: 'var(--text-subtle)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <BookOpen size={15} color="var(--gemini-cyan)" />
                                    <span>Source Citation: {res.source_citation}</span>
                                  </div>
                                )}

                                {/* Next Step */}
                                {res.next_step && (
                                  <div style={{ color: 'var(--gemini-gold)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <ArrowRight size={15} />
                                    <span>Actionable Next Step: {res.next_step}</span>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Follow-up Prompt Chip */}
                            {res.follow_up_prompt && (
                              <div style={{ marginTop: '12px' }}>
                                <button
                                  onClick={() => onSelectFollowUp(res.follow_up_prompt)}
                                  style={{
                                    padding: '8px 16px',
                                    borderRadius: '20px',
                                    background: 'rgba(155, 81, 224, 0.1)',
                                    border: '1px solid rgba(155, 81, 224, 0.3)',
                                    color: 'var(--gemini-purple)',
                                    fontSize: '0.85rem',
                                    cursor: 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                  }}
                                >
                                  💬 {res.follow_up_prompt}
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                </div>
              </div>
            );
          })
        )}

        {/* Plain White Text Retrieval State with Wave Transition */}
        {isLoading && (
          <div style={{ maxWidth: '820px', margin: '0 auto', width: '100%', padding: '16px 0' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                background: 'transparent',
                border: 'none',
                boxShadow: 'none',
                color: '#FFFFFF',
                fontSize: '1.05rem',
                fontWeight: 500,
              }}
              className="animate-fade-in"
            >
              <span className="gemini-wave-text" style={{ color: '#FFFFFF', fontWeight: 500, letterSpacing: '-0.01em' }}>
                {backendStatus || THINKING_STEPS[loadingStepIdx]}
              </span>
            </div>
          </div>
        )}



        <div ref={messagesEndRef} />
      </div>

      {/* Google Gemini 28px Rounded Pill Input Bar */}
      <div style={{ width: '100%', background: 'var(--gemini-bg-main)', padding: '12px 20px 24px 20px' }}>
        <div style={{ maxWidth: '820px', margin: '0 auto' }}>
          <form
            onSubmit={handleSubmit}
            style={{
              background: 'var(--gemini-bg-input)',
              borderRadius: '28px',
              border: '1px solid var(--glass-border)',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
              display: 'flex',
              alignItems: 'center',
              padding: '10px 18px',
              gap: '12px',
            }}
          >
            {/* Plus Attachment Icon */}
            <button
              type="button"
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              title="Add attachment"
            >
              <Plus size={22} />
            </button>

            <input
              type="text"
              placeholder="Ask Gemini about BIS standards, hallmarking, or CRS compliance..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isLoading}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'var(--text-main)',
                fontSize: '1.05rem',
                padding: '4px 0',
              }}
            />

            {/* Microphone Voice Button */}
            <button
              type="button"
              onClick={onOpenVoiceModal}
              disabled={isLoading}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
              }}
              title="Voice Query (Whisper)"
            >
              <Mic size={22} />
            </button>

            {/* Gemini Submit Sparkle Arrow Button */}
            <button
              type="submit"
              disabled={!inputText.trim() || isLoading}
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: !inputText.trim() || isLoading ? 'rgba(255, 255, 255, 0.08)' : 'var(--gemini-sparkle-gradient)',
                border: 'none',
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: !inputText.trim() || isLoading ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              <Send size={18} />
            </button>
          </form>

          {/* Gemini Footer Disclaimer */}
          <div style={{ textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '10px' }}>
            Gemini / BIS Agentic RAG may display inaccurate info, so double-check official IS standards on Manakonline.
          </div>
        </div>
      </div>
    </div>
  );
};

