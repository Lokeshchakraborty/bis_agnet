import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, Copy, ThumbsUp, ThumbsDown, Share2, Plus, Check, Download, FileText, MessageSquare } from 'lucide-react';
import type { ChatMessage, UserProfile } from '../types';
import { BisLogo } from './BisLogo';
import { getApiUrl } from '../config';

export const cleanMessageText = (text: string): string => {
  if (!text) return '';
  let cleaned = text.replace(/\n*\[?i asked (?:the |as )?follow[- ]?up(?: question)?\]?:?.*$/is, '').trimEnd();
  // Strip leaked system integration output fields and metadata
  cleaned = cleaned.replace(/(?:---|___|\*\*\*)*\s*(?:Output Fields\s*(?:\([^)]*\))?|OUTPUT FIELDS:)\s*(?:```[\s\S]*?```|\{[\s\S]*?\})?/gi, '').trimEnd();
  cleaned = cleaned.replace(/(?:---|___|\*\*\*)*\s*```(?:json)?\s*\{[\s\S]*?\"applicable_standards\"[\s\S]*?\}\s*```/gi, '').trimEnd();
  cleaned = cleaned.replace(/(?:---|___|\*\*\*)*\s*Prepared by:[\s\S]*?(?:\*End of Dossier\.?\*|$)/gi, '').trimEnd();
  cleaned = cleaned.replace(/(?:---|___|\*\*\*)*\s*\*End of Dossier\.?\*\s*/gi, '').trimEnd();
  return cleaned;
};


interface ChatWindowProps {
  messages: ChatMessage[];
  onSendMessage: (query: string) => void;
  onOpenVoiceModal: () => void;
  isLoading: boolean;
  onSelectFollowUp: (prompt: string) => void;
  backendStatus?: string;
  currentUser?: UserProfile | null;
  sessionId?: string;
  theme?: 'light' | 'dark';
}

const GEMINI_HOME_CARDS = [
  {
    title: 'Gold Hallmarking HUID',
    subtitle: 'Procedure & IS 1417 purity guidelines for jewellery manufacturers',
    prompt: 'What is the procedure for getting a Gold Hallmarking license under BIS?',
  },
  {
    title: 'CRS Electronics Scheme',
    subtitle: 'Mandatory documentation for MeitY electronics & IT goods',
    prompt: 'What are the required compliance documents for electronics CRS registration?',
  },
  {
    title: 'FMCS Overseas Certification',
    subtitle: 'Foreign Manufacturers Certification Scheme & AIR rules',
    prompt: 'Explain the Foreign Manufacturers Certification Scheme (FMCS) requirements.',
  },
  {
    title: 'Testing Lab Networks',
    subtitle: 'Search BIS & NABL accredited testing laboratory networks',
    prompt: 'How to check BIS recognized testing laboratory networks for steel testing?',
  },
];

const THINKING_STEPS = [
  'Classifying intent & IS standard codes...',
  'Checking 0-Token instant response cache...',
  'Performing BM25 & dense vector retrieval...',
  'Querying Supabase PostgreSQL knowledge base...',
  'Synthesizing compliance report with IS standards...',
];

const cleanStatusText = (status: string) => {
  return status.replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]|🔍|⚡|📚|🗄️|✦|📄|📑|💬|⚠️|🎤/gu, '').trim();
};

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  onSendMessage,
  onOpenVoiceModal,
  isLoading,
  onSelectFollowUp,
  backendStatus,
  currentUser,
  sessionId,
  theme = 'light',
}) => {
  const isDark = theme === 'dark';

  const [inputText, setInputText] = useState('');
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);
  const [downloadingMsgId, setDownloadingMsgId] = useState<string | null>(null);
  const [loadingStepIdx, setLoadingStepIdx] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleDownloadPdf = async (msg: ChatMessage) => {
    setDownloadingMsgId(msg.id);
    try {
      const sanitizedCurrentText = cleanMessageText(msg.text);
      const wholeConversationRe = /\b(?:whole|entire|complete|full)\b.*\b(?:conversation|history)\b/i;
      const isWholeConversationRequest =
        wholeConversationRe.test(msg.query || '') ||
        wholeConversationRe.test(sanitizedCurrentText) ||
        /master pdf|consultation summary/i.test(sanitizedCurrentText);

      let effectiveQuery = msg.query || (sanitizedCurrentText.length > 60 ? sanitizedCurrentText.substring(0, 60) + '...' : sanitizedCurrentText);
      let effectiveCoreResponse = cleanMessageText(msg.response?.core_response || msg.text);
      let effectiveStandards = msg.response?.applicable_standards || [];
      let effectiveNextStep = msg.response?.next_step || '';

      if (isWholeConversationRequest) {
        // Compile all conversational turns into a unified consultation dossier
        const sections: string[] = [];
        const standardsSet = new Set<string>();
        let turnCounter = 1;

        for (let i = 0; i < messages.length; i++) {
          const current = messages[i];
          if (current.sender === 'user') {
            const nextAssistant = messages[i + 1];
            if (nextAssistant && nextAssistant.sender === 'assistant') {
              const userPrompt = current.text.trim();
              const assistantContent = cleanMessageText(nextAssistant.response?.core_response || nextAssistant.text).trim();

              // Skip meta-requests that are just brief download confirmations
              const isMetaQuery = /^(?:give me (?:the )?pdf|download pdf|export pdf|no\s*,?\s*give me (?:the )?pdf)/i.test(userPrompt);
              if (isMetaQuery && assistantContent.length < 250) {
                continue;
              }

              sections.push(`## Topic ${turnCounter}: ${userPrompt}\n\n${assistantContent}`);
              turnCounter++;

              if (nextAssistant.response?.applicable_standards) {
                nextAssistant.response.applicable_standards.forEach(std => standardsSet.add(std));
              }
              if (nextAssistant.response?.next_step) {
                effectiveNextStep = nextAssistant.response.next_step;
              }
            }
          }
        }

        if (sections.length > 0) {
          effectiveQuery = 'Comprehensive BIS Consultation Dossier (Full Session)';
          effectiveCoreResponse = sections.join('\n\n---\n\n');
          effectiveStandards = Array.from(standardsSet);
        }
      } else if (effectiveCoreResponse.length < 250 && /pdf|dossier|compiled|download/i.test(effectiveCoreResponse)) {
        // If current message is just a download acknowledgement, find the preceding substantive assistant response
        for (let i = messages.length - 1; i >= 0; i--) {
          const prev = messages[i];
          if (prev.sender === 'assistant' && prev.id !== msg.id) {
            const prevText = cleanMessageText(prev.response?.core_response || prev.text);
            if (prevText.length >= 250) {
              effectiveCoreResponse = prevText;
              effectiveQuery = prev.query || prev.text.substring(0, 60);
              if (prev.response?.applicable_standards?.length) {
                effectiveStandards = prev.response.applicable_standards;
              }
              if (prev.response?.next_step) {
                effectiveNextStep = prev.response.next_step;
              }
              break;
            }
          }
        }
      }

      const payload = {
        query: effectiveQuery,
        core_response: effectiveCoreResponse,
        applicable_standards: effectiveStandards,
        next_step: effectiveNextStep,
        intent: isWholeConversationRequest ? 'full_session_dossier' : (msg.response?.intent || 'compliance'),
        user_name: currentUser?.full_name || 'Compliance Applicant',
        session_id: sessionId || 'default',
      };

      const res = await fetch(getApiUrl('/api/v1/export/pdf'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`PDF Export failed with HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      const disposition = res.headers.get('Content-Disposition');
      let filename = 'BIS_Compliance_Research_Dossier.pdf';
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) filename = match[1];
      }
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        if (document.body.contains(a)) {
          document.body.removeChild(a);
        }
      }, 2000);
    } catch (err) {
      console.error('PDF download error:', err);
      alert('Unable to generate PDF dossier. Please check backend connectivity.');
    } finally {
      setDownloadingMsgId(null);
    }
  };

  useEffect(() => {
    if (!isLoading) {
      setLoadingStepIdx(0);
      setElapsedSeconds(0);
      return;
    }
    const startTime = Date.now();
    const timerInterval = setInterval(() => {
      setElapsedSeconds(Math.round(((Date.now() - startTime) / 1000) * 10) / 10);
    }, 100);
    const stepInterval = setInterval(() => {
      setLoadingStepIdx((prev) => (prev + 1) % THINKING_STEPS.length);
    }, 1600);
    return () => {
      clearInterval(timerInterval);
      clearInterval(stepInterval);
    };
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

  const handleCopyText = (msgId: string, text: string) => {
    navigator.clipboard.writeText(cleanMessageText(text));
    setCopiedMsgId(msgId);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  // Helper to parse basic markdown bold/list items and tables cleanly for Compliance Mode
  const renderFormattedText = (text: string) => {
    // Pre-process text: strip follow-up tags, ensure collapsed tables and inline bullet lists have proper newlines
    let processedText = cleanMessageText(text);
    if (processedText.includes('|')) {
      // 1. Heal orphan pipe lines created by bad splits: e.g. '\n|\n|' -> '\n|'
      processedText = processedText.replace(/\n\s*\|\s*\n\s*\|/g, '\n|');
      processedText = processedText.replace(/\n\s*\|\s*$/g, '');

      // 2. Heal unclosed table rows (lines starting with '|' that have >= 2 pipes but no closing '|')
      processedText = processedText
        .split('\n')
        .map((l) => {
          const s = l.trim();
          if (s.startsWith('|') && (s.match(/\|/g) || []).length >= 2 && !s.endsWith('|')) {
            return s + ' |';
          }
          return l;
        })
        .join('\n');

      // 3. Collapse blank lines between adjacent table rows
      processedText = processedText.replace(/(\|\s*)\n\s*\n\s*(\|)/g, '$1\n$2');

      // 4. Separate table end from subsequent headers or text
      processedText = processedText.replace(/\|\s+([A-Z][A-Za-z0-9\s&]+:\s*[•●\-*])/g, '|\n\n$1');
      processedText = processedText.replace(
        /\|\s+(Key Takeaways|Important|Note|Recommendation|Actionable|Next Steps)/gi,
        '|\n\n### $1'
      );
    }
    // Expand collapsed inline bullets onto their own lines
    processedText = processedText.replace(/(?<=[^\n])\s+([•●])\s+/g, '\n$1 ');

    const lines = processedText.split('\n');
    let subCounter = 0;
    const isDark = theme === 'dark';
    const elements: React.ReactNode[] = [];
    let i = 0;

    const isTableRow = (l: string) => {
      const t = l.trim();
      if (!t) return false;
      const pipeCount = (t.match(/\|/g) || []).length;
      if (t.startsWith('|') && pipeCount >= 1 && t.length > 2) return true;
      return pipeCount >= 2;
    };

    const isTableDivider = (l: string) => {
      const t = l.trim();
      if (!isTableRow(t)) return false;
      const inner = t.replace(/^\|/, '').replace(/\|$/, '');
      const cells = inner.split('|');
      return cells.length >= 2 && cells.every((c) => /^[\s\-:]+$/.test(c) && c.includes('-'));
    };

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      // Check for Code Block (```lang ... ```)
      if (trimmed.startsWith('```')) {
        const lang = trimmed.slice(3).trim();
        const codeLines: string[] = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          codeLines.push(lines[i]);
          i++;
        }
        if (i < lines.length && lines[i].trim().startsWith('```')) {
          i++;
        }
        elements.push(
          <div
            key={`code-${i}`}
            style={{
              margin: '16px 0',
              borderRadius: '8px',
              overflow: 'hidden',
              border: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid #E2E8F0',
              background: isDark ? '#18191B' : '#F8FAFC',
            }}
          >
            {lang && (
              <div
                style={{
                  padding: '6px 14px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: isDark ? '#94A3B8' : '#64748B',
                  background: isDark ? 'rgba(255,255,255,0.04)' : '#F1F5F9',
                  borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #E2E8F0',
                }}
              >
                {lang}
              </div>
            )}
            <pre
              style={{
                margin: 0,
                padding: '12px 16px',
                overflowX: 'auto',
                fontSize: '0.86rem',
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                lineHeight: 1.5,
                color: isDark ? '#E2E8F0' : '#1E293B',
              }}
            >
              <code>{codeLines.join('\n')}</code>
            </pre>
          </div>
        );
        continue;
      }

      // Check for Markdown Table Block
      if (isTableRow(trimmed)) {
        const tableStartIndex = i;
        const tableLines: string[] = [];
        while (i < lines.length) {
          const curTrim = lines[i].trim();
          if (isTableRow(curTrim)) {
            tableLines.push(curTrim);
            i++;
          } else if (curTrim === '' && i + 1 < lines.length && isTableRow(lines[i + 1].trim())) {
            // Tolerate accidental blank line between rows inside a table
            i++;
          } else {
            break;
          }
        }

        if (tableLines.length >= 2) {
          const headerRow = tableLines[0];
          const hasDivider = isTableDivider(tableLines[1]);
          const dataRowStart = hasDivider ? 2 : 1;

          const parseCells = (rowStr: string) => {
            let raw = rowStr.trim();
            if (raw.startsWith('|')) raw = raw.slice(1);
            if (raw.endsWith('|')) raw = raw.slice(0, -1);
            return raw.split('|').map((c) => c.trim());
          };

          const headers = parseCells(headerRow);
          const bodyRows = tableLines.slice(dataRowStart).map(parseCells);

          elements.push(
            <div
              key={`table-${i}`}
              style={{
                overflowX: 'auto',
                marginTop: '18px',
                marginBottom: '20px',
                width: '100%',
                borderRadius: '12px',
                border: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid #E2E8F0',
                boxShadow: isDark ? '0 4px 14px rgba(0, 0, 0, 0.35)' : '0 2px 8px rgba(0, 0, 0, 0.06)',
              }}
            >
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'separate',
                  borderSpacing: 0,
                  fontSize: '0.90rem',
                  background: isDark ? '#1E1F20' : '#FFFFFF',
                }}
              >
                <thead style={{ background: isDark ? '#282A2C' : '#F8FAFC' }}>
                  <tr>
                    {headers.map((h, hIdx) => (
                      <th
                        key={hIdx}
                        style={{
                          padding: '12px 16px',
                          textAlign: 'left',
                          fontWeight: 600,
                          fontSize: '0.85rem',
                          color: isDark ? '#F8FAFC' : '#0F172A',
                          borderBottom: isDark ? '2px solid rgba(255, 255, 255, 0.14)' : '2px solid #CBD5E1',
                          letterSpacing: '0.01em',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {parseBold(h)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {bodyRows.map((r, rIdx) => (
                    <tr
                      key={rIdx}
                      style={{
                        background:
                          rIdx % 2 === 1
                            ? isDark
                              ? 'rgba(255, 255, 255, 0.025)'
                              : '#F8FAFC'
                            : 'transparent',
                        transition: 'background 0.15s ease',
                      }}
                    >
                      {r.map((c, cIdx) => (
                        <td
                          key={cIdx}
                          style={{
                            padding: '11px 16px',
                            color: isDark ? '#CBD5E1' : '#334155',
                            borderBottom:
                              rIdx === bodyRows.length - 1
                                ? 'none'
                                : isDark
                                  ? '1px solid rgba(255, 255, 255, 0.06)'
                                  : '1px solid #F1F5F9',
                            lineHeight: '1.58',
                            fontSize: '0.92rem',
                            verticalAlign: 'top',
                          }}
                        >
                          {parseBold(c)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
          continue;
        } else {
          i = tableStartIndex;
        }
      }

      // Headers
      if (line.startsWith('### ')) {
        subCounter = 0;
        elements.push(
          <h3
            key={i}
            style={{
              fontSize: '1.2rem',
              fontWeight: 700,
              color: isDark ? '#FFFFFF' : '#0F172A',
              marginTop: '20px',
              marginBottom: '10px',
              borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid #E2E8F0',
              paddingBottom: '4px',
            }}
          >
            {line.replace('### ', '')}
          </h3>
        );
        i++;
        continue;
      }
      if (line.startsWith('## ')) {
        subCounter = 0;
        elements.push(
          <h2
            key={i}
            style={{
              fontSize: '1.35rem',
              fontWeight: 700,
              color: isDark ? '#FFFFFF' : '#0F172A',
              marginTop: '22px',
              marginBottom: '12px',
            }}
          >
            {line.replace('## ', '')}
          </h2>
        );
        i++;
        continue;
      }

      // Sub-Bullet Points (Numbered: 1., 2., 3.)
      const isSubBullet = line.startsWith('  ') || line.startsWith('\t');
      const numMatch = trimmed.match(/^(\d+)[.)]\s+(.*)/);

      if (isSubBullet || (numMatch && !trimmed.startsWith('•') && !trimmed.startsWith('●'))) {
        subCounter += 1;
        const content = numMatch ? numMatch[2] : trimmed.replace(/^[*•◦\d.-]+\s+/, '');
        const numberLabel = numMatch ? `${numMatch[1]}.` : `${subCounter}.`;

        elements.push(
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              marginTop: '5px',
              marginBottom: '5px',
              paddingLeft: '0px',
            }}
          >
            <span
              style={{
                color: isDark ? '#94A3B8' : '#475569',
                fontWeight: 'bold',
                fontSize: '0.92rem',
                lineHeight: '1.65',
                minWidth: '20px',
              }}
            >
              {numberLabel}
            </span>
            <div
              style={{
                flex: 1,
                lineHeight: '1.65',
                color: isDark ? '#E2E8F0' : '#334155',
                fontSize: '0.96rem',
              }}
            >
              {parseBold(content)}
            </div>
          </div>
        );
        i++;
        continue;
      }

      // Parent Level Bullet Points (Blue Solid Circle Bullet: ●)
      if (
        trimmed.startsWith('- ') ||
        trimmed.startsWith('* ') ||
        trimmed.startsWith('• ') ||
        trimmed.startsWith('● ')
      ) {
        subCounter = 0;
        const content = trimmed.replace(/^[-*•●]\s+/, '');
        elements.push(
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              marginTop: '16px',
              marginBottom: '8px',
              paddingLeft: '0px',
            }}
          >
            <span
              style={{
                color: isDark ? '#60A5FA' : '#2563EB',
                fontSize: '1.3rem',
                lineHeight: '1.4',
                minWidth: '20px',
              }}
            >
              ●
            </span>
            <div
              style={{
                flex: 1,
                lineHeight: '1.6',
                color: isDark ? '#FFFFFF' : '#0F172A',
                fontWeight: 700,
                fontSize: '1.15rem',
              }}
            >
              {parseBold(content)}
            </div>
          </div>
        );
        i++;
        continue;
      }

      subCounter = 0;
      if (trimmed === '') {
        elements.push(<div key={i} style={{ height: '8px' }} />);
      } else {
        elements.push(
          <p
            key={i}
            style={{
              marginBottom: '10px',
              lineHeight: '1.7',
              color: 'var(--text-main)',
              fontSize: '1.05rem',
            }}
          >
            {parseBold(line)}
          </p>
        );
      }
      i++;
    }

    return elements;
  };


  const parseBold = (str: string) => {
    const isDark = theme === 'dark';
    // Match bold **text**, markdown links [text](url), or raw http(s) urls
    const regex = /(\*\*.*?\*\*|\[.*?\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s)\]]+)/g;
    const parts = str.split(regex);
    return parts.map((part, i) => {
      if (!part) return null;
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={i} style={{ color: isDark ? '#FFFFFF' : '#0F172A', fontWeight: 600 }}>
            {part.slice(2, -2)}
          </strong>
        );
      }
      const mdLinkMatch = part.match(/^\[(.*?)\]\((https?:\/\/[^\s)]+)\)$/);
      if (mdLinkMatch) {
        return (
          <a
            key={i}
            href={mdLinkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: isDark ? '#60A5FA' : '#2563EB',
              textDecoration: 'underline',
              textUnderlineOffset: '2px',
              wordBreak: 'break-all',
            }}
          >
            {mdLinkMatch[1]}
          </a>
        );
      }
      if (part.startsWith('http://') || part.startsWith('https://')) {
        return (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: isDark ? '#60A5FA' : '#2563EB',
              textDecoration: 'underline',
              textUnderlineOffset: '2px',
              wordBreak: 'break-all',
            }}
          >
            {part}
          </a>
        );
      }
      return part;
    });
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--gemini-bg-main)', position: 'relative' }}>
      {/* Gemini Stream Area */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {messages.length === 0 ? (
          <div style={{ margin: 'auto', maxWidth: '840px', width: '100%', padding: '30px 16px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Gemini Hero Greeting */}
            <div style={{ textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <h1 className="gemini-gradient-text chat-hero-title" style={{ fontSize: '3.2rem', fontWeight: 600, letterSpacing: '-0.03em', lineHeight: '1.1' }}>
                Hello, Compliance Officer
              </h1>
              <h2 className="chat-hero-subtitle" style={{ fontSize: '2.2rem', fontWeight: 500, color: 'var(--text-muted)' }}>
                How can I help with BIS standards today?
              </h2>
            </div>

            {/* 4 Gemini Prompt Recommendation Cards */}
            <div className="chat-home-cards-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
              {GEMINI_HOME_CARDS.map((card, idx) => (
                <div
                  key={idx}
                  className="gemini-card"
                  onClick={() => onSendMessage(card.prompt)}
                  style={{
                    padding: '18px',
                    minHeight: '130px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                  }}
                >
                  <p style={{ fontSize: '0.92rem', fontWeight: 500, color: 'var(--text-main)', lineHeight: '1.45' }}>
                    {card.title}
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '12px' }}>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{card.subtitle}</span>
                    <span style={{ padding: '5px', background: 'rgba(0,0,0,0.04)', borderRadius: '50%', display: 'flex', alignItems: 'center' }}><BisLogo size={16} /></span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isUser = msg.sender === 'user';
            const res = msg.response;

            // Check if user specifically requested PDF, full compliance, or full research
            const prevUserText = (idx > 0 && messages[idx - 1].sender === 'user' ? messages[idx - 1].text : '').toLowerCase();
            const currentQueryText = (msg.query || '').toLowerCase();
            const assistantText = (res?.next_step || res?.core_response || '').toLowerCase();
            const combinedInquiry = `${prevUserText} ${currentQueryText}`;

            const isPdfRequested =
              combinedInquiry.includes('pdf') ||
              combinedInquiry.includes('full compliance') ||
              combinedInquiry.includes('complete compliance') ||
              combinedInquiry.includes('full research') ||
              combinedInquiry.includes('complete research') ||
              combinedInquiry.includes('full dossier') ||
              combinedInquiry.includes('compliance dossier') ||
              combinedInquiry.includes('research dossier') ||
              combinedInquiry.includes('download pdf') ||
              combinedInquiry.includes('give me a pdf') ||
              assistantText.includes('pdf dossier') ||
              assistantText.includes('download research pdf');

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
                        background: theme === 'dark' ? '#282A2C' : '#EFF6FF',
                        border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid #BFDBFE',
                        borderRadius: '24px 24px 4px 24px',
                        padding: '14px 22px',
                        color: theme === 'dark' ? '#FFFFFF' : '#0F172A',
                        fontSize: '1.05rem',
                        lineHeight: '1.6',
                        boxShadow: theme === 'dark' ? '0 4px 15px rgba(0, 0, 0, 0.3)' : '0 2px 10px rgba(37, 99, 235, 0.08)',
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
                      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginTop: '14px', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                        <button
                          onClick={() => handleCopyText(msg.id, msg.text)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem' }}
                          title="Copy response"
                        >
                          {copiedMsgId === msg.id ? <Check size={16} color="#10B981" /> : <Copy size={16} />}
                          <span>{copiedMsgId === msg.id ? 'Copied' : 'Copy'}</span>
                        </button>

                        {/* Dedicated Export Research PDF Button (ONLY when user requested PDF, full compliance, or full research) */}
                        {isPdfRequested && (
                          <button
                            onClick={() => handleDownloadPdf(msg)}
                            disabled={downloadingMsgId === msg.id}
                            style={{
                              background: '#FEF3C7',
                              border: '1px solid #FDE68A',
                              color: '#B45309',
                              borderRadius: '16px',
                              padding: '5px 12px',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              fontSize: '0.82rem',
                              fontWeight: 600,
                              transition: 'all 0.2s ease',
                            }}
                            title="Download official BIS Compliance Research Dossier (PDF)"
                          >
                            {downloadingMsgId === msg.id ? <Download size={14} className="animate-spin" /> : <FileText size={14} />}
                            <span>{downloadingMsgId === msg.id ? 'Generating PDF...' : 'Export Research PDF'}</span>
                          </button>
                        )}

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

                      {/* Interactive Full Research PDF Dossier Card (ONLY if user asked for PDF, full compliance, or full research) */}
                      {res && isPdfRequested && (
                        <div
                          style={{
                            marginTop: '14px',
                            padding: '12px 16px',
                            borderRadius: '12px',
                            background: '#FEF3C7',
                            border: '1px solid #FCD34D',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '12px',
                            flexWrap: 'wrap',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <BisLogo size={24} />
                            <div>
                              <div style={{ fontWeight: 600, color: '#B45309', fontSize: '0.88rem' }}>
                                Official BIS Compliance Research Dossier (PDF)
                              </div>
                              <div style={{ fontSize: '0.78rem', color: '#78350F' }}>
                                Includes authoritative IS standard titles, technical limits, licensing roadmap & SHA-256 audit hash.
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={() => handleDownloadPdf(msg)}
                            disabled={downloadingMsgId === msg.id}
                            style={{
                              background: '#D97706',
                              color: '#FFFFFF',
                              border: 'none',
                              borderRadius: '20px',
                              padding: '6px 16px',
                              fontWeight: 700,
                              fontSize: '0.82rem',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              boxShadow: '0 2px 8px rgba(217, 119, 6, 0.25)',
                              transition: 'transform 0.15s ease',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-1px)')}
                            onMouseLeave={(e) => (e.currentTarget.style.transform = 'none')}
                          >
                            <Download size={14} />
                            <span>{downloadingMsgId === msg.id ? 'Compiling Dossier...' : 'Download PDF'}</span>
                          </button>
                        </div>
                      )}

                      {/* Follow-up Prompt Chip */}
                      {res?.follow_up_prompt && (
                        <div style={{ marginTop: '12px' }}>
                          <button
                            onClick={() => onSelectFollowUp(res.follow_up_prompt)}
                            style={{
                              padding: '8px 16px',
                              borderRadius: '20px',
                              background: theme === 'dark' ? 'rgba(124, 58, 237, 0.18)' : '#F5F3FF',
                              border: theme === 'dark' ? '1px solid rgba(124, 58, 237, 0.4)' : '1px solid #DDD6FE',
                              color: theme === 'dark' ? '#C4B5FD' : '#7C3AED',
                              fontSize: '0.85rem',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '8px',
                            }}
                          >
                            <MessageSquare size={14} />
                            <span>{res.follow_up_prompt}</span>
                          </button>
                        </div>
                      )}
                    </div>
                  )
                  }

                </div>
              </div>
            );
          })
        )}

        {/* Clean Realistic AI Retrieval State Indicator */}
        {isLoading && (
          <div style={{ maxWidth: '820px', margin: '0 auto', width: '100%', padding: '6px 20px 12px 20px' }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '10px',
                background: 'transparent',
                border: 'none',
                boxShadow: 'none',
                padding: '0',
                fontSize: '0.92rem',
                fontWeight: 500,
              }}
            >
              {/* Clean static logo - no animation */}
              <BisLogo size={18} />

              {/* Clean solid text - no gradient */}
              <span
                style={{
                  color: isDark ? '#94A3B8' : '#475569',
                  fontWeight: 500,
                  letterSpacing: '-0.01em',
                }}
              >
                {cleanStatusText(backendStatus || THINKING_STEPS[loadingStepIdx])}
              </span>

              {/* 3 Real-time Subtle Pulsing Wave Dots */}
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', marginLeft: '2px' }}>
                <span
                  className="retrieval-dot retrieval-dot-1"
                  style={{ background: isDark ? '#94A3B8' : '#64748B' }}
                />
                <span
                  className="retrieval-dot retrieval-dot-2"
                  style={{ background: isDark ? '#94A3B8' : '#64748B' }}
                />
                <span
                  className="retrieval-dot retrieval-dot-3"
                  style={{ background: isDark ? '#94A3B8' : '#64748B' }}
                />
              </div>

              {/* Subtle elapsed time in muted text */}
              {elapsedSeconds > 0 && (
                <span style={{ fontSize: '0.76rem', color: isDark ? '#64748B' : '#94A3B8', fontWeight: 500, marginLeft: '4px' }}>
                  ({elapsedSeconds.toFixed(1)}s)
                </span>
              )}
            </div>
          </div>
        )}



        <div ref={messagesEndRef} />
      </div >

      {/* Google Gemini 28px Rounded Pill Input Bar */}
      < div className="chat-input-bar-container" style={{ width: '100%', background: 'var(--gemini-bg-main)', padding: '12px 20px 24px 20px' }}>
        <div style={{ maxWidth: '820px', margin: '0 auto' }}>
          <form
            onSubmit={handleSubmit}
            style={{
              background: theme === 'dark' ? '#1E1F20' : '#FFFFFF',
              borderRadius: '28px',
              border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.15)' : '1px solid var(--glass-border)',
              boxShadow: theme === 'dark' ? '0 4px 20px rgba(0, 0, 0, 0.4)' : '0 4px 20px rgba(0, 0, 0, 0.08)',
              display: 'flex',
              alignItems: 'center',
              padding: '10px 18px',
              gap: '12px',
            }}
          >
            {/* Plus Attachment Icon */}
            <button
              type="button"
              onClick={() => alert('📄 Document & Standard PDF attachment support is coming in the next BIS SATHI update.')}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', transition: 'color 0.2s ease' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#2563EB')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
              title="Attach standard document / specification (Coming soon)"
            >
              <Plus size={22} />
            </button>

            <input
              type="text"
              placeholder="Ask BIS SATHI about BIS standards, hallmarking, or CRS compliance..."
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
                background: !inputText.trim() || isLoading ? 'rgba(0, 0, 0, 0.06)' : 'var(--gemini-sparkle-gradient)',
                border: 'none',
                color: !inputText.trim() || isLoading ? '#94A3B8' : '#FFFFFF',
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
            BIS Agentic RAG may display inaccurate info, so double-check official IS standards on Manakonline.
          </div>
        </div>
      </div >
    </div >
  );
};

