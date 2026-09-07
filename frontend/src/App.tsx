import React, { useState, useEffect, useCallback } from 'react';
import { getApiUrl } from './config';
import { Header } from './components/Header';
import { SessionSidebar } from './components/SessionSidebar';
import { ChatWindow } from './components/ChatWindow';
import { VoiceRecorderModal } from './components/VoiceRecorderModal';
import { TelemetryPanel } from './components/TelemetryPanel';
import { AuthModal } from './components/AuthModal';
import { LandingPage } from './components/LandingPage';
import { UserProfileModal } from './components/UserProfileModal';
import { AuditLedgerModal } from './components/AuditLedgerModal';
import type { HealthResponse, ChatMessage, QueryResponse, VoiceQueryResponse, UserProfile } from './types';


export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  // User Auth State
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem('bis_user');
    if (!saved) return null;
    try {
      const u = JSON.parse(saved);
      if (u && (!u.llm_model || u.llm_model.startsWith('gemini-2.5') || u.llm_model.startsWith('gemini-2.0') || u.llm_model.startsWith('gemini-1.5') || u.llm_model.startsWith('gemini-1.0'))) {
        u.llm_model = 'gemini-3.5-flash';
        localStorage.setItem('bis_user', JSON.stringify(u));
      }
      return u;
    } catch {
      return null;
    }
  });
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'signup'>('login');
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [profileModalTab, setProfileModalTab] = useState<'details' | 'model' | 'usage'>('usage');
  const [isAuditLedgerOpen, setIsAuditLedgerOpen] = useState(false);

  // Chatbot Workspace Theme State (Dark / Light)
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('bis_chatbot_theme');
    return saved === 'dark' ? 'dark' : 'light';
  });

  const handleToggleTheme = () => {
    setTheme((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      localStorage.setItem('bis_chatbot_theme', next);
      return next;
    });
  };

  const handleSelectTheme = (newTheme: 'light' | 'dark') => {
    setTheme(newTheme);
    localStorage.setItem('bis_chatbot_theme', newTheme);
  };

  const handleOpenProfileModal = (tab: 'details' | 'model' | 'usage' = 'usage') => {
    setProfileModalTab(tab);
    setIsProfileModalOpen(true);
  };

  const [activeSessionId, setActiveSessionId] = useState<string>(() => `session-${Math.floor(1000 + Math.random() * 9000)}`);
  const [sessions, setSessions] = useState<{ session_id: string; history_turns: number; last_query?: string }[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<QueryResponse | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState(false);
  const [isTelemetryOpen, setIsTelemetryOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);


  // Fetch API Health & Active Sessions
  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(getApiUrl('/health'));
      if (res.ok) {
        const data: HealthResponse = await res.json();
        setHealth(data);
      }
    } catch (err) {
      console.error('Health fetch error:', err);
    }
  }, []);

  const fetchSessions = useCallback(async (targetUserId?: string) => {
    const userId = targetUserId || currentUser?.user_id || 'default_user';
    try {
      const res = await fetch(getApiUrl(`/api/v1/sessions?user_id=${encodeURIComponent(userId)}`));
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (err) {
      console.error('Fetch sessions error:', err);
    }
  }, [currentUser?.user_id]);

  useEffect(() => {
    fetchHealth();
    const userId = currentUser?.user_id || 'default_user';
    setMessages([]);
    setLastResponse(null);
    setActiveSessionId(`session-${Math.floor(1000 + Math.random() * 9000)}`);
    fetchSessions(userId);
  }, [currentUser?.user_id, fetchHealth, fetchSessions]);

  const handleAuthSuccess = (user: UserProfile) => {
    setCurrentUser(user);
    localStorage.setItem('bis_user', JSON.stringify(user));
    setMessages([]);
    setLastResponse(null);
    const newId = `session-${Math.floor(1000 + Math.random() * 9000)}`;
    setActiveSessionId(newId);
    fetchSessions(user.user_id);
  };

  const handleLogout = () => {
    setCurrentUser(null);
    localStorage.removeItem('bis_user');
    setMessages([]);
    setLastResponse(null);
    const newId = `session-${Math.floor(1000 + Math.random() * 9000)}`;
    setActiveSessionId(newId);
    fetchSessions('default_user');
  };

  const [currentBackendStatus, setCurrentBackendStatus] = useState<string>('');

  const handleSendMessage = async (queryText: string) => {
    const userMsgId = Date.now().toString();
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: 'user',
      text: queryText,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setCurrentBackendStatus('Classifying intent & IS standard codes...');

    try {
      const response = await fetch(getApiUrl('/api/v1/query/stream'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          session_id: activeSessionId,
          user_id: currentUser?.user_id || 'default_user',
          llm_provider: currentUser?.llm_provider,
          llm_model: currentUser?.llm_model,
          llm_api_key: currentUser?.llm_api_key,
          llm_base_url: currentUser?.llm_base_url,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const streamingMsgId = (Date.now() + 1).toString();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            try {
              const jsonStr = trimmed.slice(6);
              const data = JSON.parse(jsonStr);
              if (data.type === 'status') {
                setCurrentBackendStatus(data.message);
              } else if (data.type === 'token' && data.token) {
                setCurrentBackendStatus('');
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  if (last && last.sender === 'assistant' && last.id === streamingMsgId) {
                    return [
                      ...prev.slice(0, -1),
                      { ...last, text: last.text + data.token, isStreaming: true },
                    ];
                  } else {
                    const newStreamingMsg: ChatMessage = {
                      id: streamingMsgId,
                      sender: 'assistant',
                      text: data.token,
                      query: queryText,
                      timestamp: new Date().toLocaleTimeString(),
                      isStreaming: true,
                    };
                    return [...prev, newStreamingMsg];
                  }
                });
              } else if (data.type === 'result' && data.payload) {
                const resData: QueryResponse = data.payload;
                setLastResponse(resData);
                setMessages((prev) => {
                  const existingIdx = prev.findIndex((m) => m.id === streamingMsgId);
                  const finalizedMsg: ChatMessage = {
                    id: streamingMsgId,
                    sender: 'assistant',
                    text: resData.core_response,
                    query: queryText,
                    response: resData,
                    timestamp: new Date().toLocaleTimeString(),
                    isStreaming: false,
                  };
                  if (existingIdx !== -1) {
                    const copy = [...prev];
                    copy[existingIdx] = finalizedMsg;
                    return copy;
                  }
                  return [...prev, finalizedMsg];
                });
                fetchSessions();
              } else if (data.type === 'error') {
                throw new Error(data.message || 'Stream processing error');
              }
            } catch (e: any) {
              if (e.message && !e.message.includes('JSON')) throw e;
            }
          }
        }
      }
    } catch (err: any) {
      console.error('Query execution error:', err);
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `⚠️ Error executing turn: ${err.message || 'Server connection failed.'}`,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setCurrentBackendStatus('');
    }
  };


  const handleVoiceSuccess = (voiceResponse: VoiceQueryResponse) => {
    const data = voiceResponse.result;
    setLastResponse(data);

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: `🎤 Voice Query: "${voiceResponse.transcription}"`,
      timestamp: new Date().toLocaleTimeString(),
    };

    const assistantMsg: ChatMessage = {
      id: (Date.now() + 1).toString(),
      sender: 'assistant',
      text: data.core_response,
      response: data,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    fetchSessions();
  };

  const handleSelectSession = async (sessionId: string) => {
    if (window.innerWidth <= 768) {
      setIsSidebarOpen(false);
    }
    setActiveSessionId(sessionId);
    setMessages([]);
    setLastResponse(null);
    const userId = currentUser?.user_id || 'default_user';
    try {
      const res = await fetch(getApiUrl(`/api/v1/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(userId)}`));
      if (res.ok) {
        const data = await res.json();
        if (data.history && Array.isArray(data.history)) {
          const loadedMessages: ChatMessage[] = [];
          data.history.forEach((turn: any, idx: number) => {
            if (turn.user) {
              loadedMessages.push({
                id: `hist-u-${idx}`,
                sender: 'user',
                text: turn.user,
                timestamp: '',
              });
            }
            if (turn.assistant) {
              loadedMessages.push({
                id: `hist-a-${idx}`,
                sender: 'assistant',
                text: turn.assistant,
                timestamp: '',
              });
            }
          });
          setMessages(loadedMessages);
        }
      }
    } catch (err) {
      console.error('Fetch session history error:', err);
    }
  };

  const handleNewSession = () => {
    if (window.innerWidth <= 768) {
      setIsSidebarOpen(false);
    }
    const newId = `session-${Math.floor(1000 + Math.random() * 9000)}`;
    setActiveSessionId(newId);
    setMessages([]);
    setLastResponse(null);
  };

  const handleClearSession = async (sessionIdToClear: string) => {
    // Optimistically filter out deleted session
    setSessions((prev) => prev.filter((s) => s.session_id !== sessionIdToClear));
    const userId = currentUser?.user_id || 'default_user';

    if (sessionIdToClear === activeSessionId) {
      const newId = `session-${Math.floor(1000 + Math.random() * 9000)}`;
      setActiveSessionId(newId);
      setMessages([]);
      setLastResponse(null);
    }

    try {
      await fetch(getApiUrl(`/api/v1/sessions/${encodeURIComponent(sessionIdToClear)}?user_id=${encodeURIComponent(userId)}`), { method: 'DELETE' });
      await fetchSessions();
    } catch (err) {
      console.error('Clear session error:', err);
    }
  };

  const handleClearCache = async () => {
    try {
      await fetch(getApiUrl('/api/v1/cache/clear'), { method: 'POST' });
      alert('Persistent Response Cache purged successfully!');
    } catch (err) {
      console.error('Failed to clear cache:', err);
      alert('Failed to clear cache.');
    }
  };

  // Unauthenticated Visitors See the Landing Page & Auth Gate
  if (!currentUser) {
    return (
      <>
        <LandingPage
          onOpenLogin={() => {
            setAuthModalMode('login');
            setIsAuthModalOpen(true);
          }}
          onOpenSignup={() => {
            setAuthModalMode('signup');
            setIsAuthModalOpen(true);
          }}
        />
        <AuthModal
          isOpen={isAuthModalOpen}
          initialMode={authModalMode}
          onClose={() => setIsAuthModalOpen(false)}
          onAuthSuccess={handleAuthSuccess}
        />
      </>
    );
  }

  // Authenticated Users Access the Full Gemini Chat Workspace
  return (
    <div className={`app-workspace ${theme === 'dark' ? 'workspace-dark' : 'workspace-light'}`} style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      {/* Header Bar */}
      <Header
        health={health}
        currentUser={currentUser}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        onToggleTelemetry={() => setIsTelemetryOpen((prev) => !prev)}
        onOpenAuditLedger={() => setIsAuditLedgerOpen(true)}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        onOpenProfileModal={handleOpenProfileModal}
        onLogout={handleLogout}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
      />


      {/* Main App Workspace */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* Mobile Backdrop for Sidebar Drawer */}
        {isSidebarOpen && window.innerWidth <= 768 && (
          <div className="drawer-backdrop" onClick={() => setIsSidebarOpen(false)} />
        )}

        {/* Sidebar */}
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          currentUser={currentUser}
          theme={theme}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onClearSession={handleClearSession}
          onClearCache={handleClearCache}
          onSelectPrompt={(prompt) => {
            if (window.innerWidth <= 768) setIsSidebarOpen(false);
            handleSendMessage(prompt);
          }}
          onOpenAuthModal={() => setIsAuthModalOpen(true)}
          onOpenProfileModal={() => handleOpenProfileModal('details')}
          onLogout={handleLogout}
          isOpen={isSidebarOpen}
        />

        {/* Chat Window */}
        <ChatWindow
          messages={messages}
          onSendMessage={handleSendMessage}
          onOpenVoiceModal={() => setIsVoiceModalOpen(true)}
          isLoading={isLoading}
          onSelectFollowUp={(prompt) => handleSendMessage(prompt)}
          backendStatus={currentBackendStatus}
          currentUser={currentUser}
          sessionId={activeSessionId}
          theme={theme}
        />

        {/* Mobile Backdrop for Telemetry Drawer */}
        {isTelemetryOpen && window.innerWidth <= 1024 && (
          <div className="drawer-backdrop" onClick={() => setIsTelemetryOpen(false)} />
        )}

        {/* Telemetry Drawer */}
        <TelemetryPanel
          isOpen={isTelemetryOpen}
          onClose={() => setIsTelemetryOpen(false)}
          lastResponse={lastResponse}
          theme={theme}
        />
      </div>

      {/* Modals */}
      <UserProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
        currentUser={currentUser}
        lastResponse={lastResponse}
        initialTab={profileModalTab}
        theme={theme}
        onSelectTheme={handleSelectTheme}
        onUpdateUser={(updated) => setCurrentUser(updated)}
      />

      <AuthModal
        isOpen={isAuthModalOpen}
        initialMode={authModalMode}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthSuccess={handleAuthSuccess}
      />

      <VoiceRecorderModal
        isOpen={isVoiceModalOpen}
        onClose={() => setIsVoiceModalOpen(false)}
        sessionId={activeSessionId}
        onVoiceSuccess={handleVoiceSuccess}
        theme={theme}
      />

      <AuditLedgerModal
        isOpen={isAuditLedgerOpen}
        onClose={() => setIsAuditLedgerOpen(false)}
        theme={theme}
      />
    </div>
  );

};

export default App;

