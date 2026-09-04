import React, { useState, useEffect } from 'react';
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
    return saved ? JSON.parse(saved) : null;
  });
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'signup'>('login');
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [profileModalTab, setProfileModalTab] = useState<'details' | 'model' | 'usage'>('usage');
  const [isAuditLedgerOpen, setIsAuditLedgerOpen] = useState(false);

  const handleOpenProfileModal = (tab: 'details' | 'model' | 'usage' = 'usage') => {
    setProfileModalTab(tab);
    setIsProfileModalOpen(true);
  };

  const [activeSessionId, setActiveSessionId] = useState<string>('default');
  const [sessions, setSessions] = useState<{ session_id: string; history_turns: number; last_query?: string }[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<QueryResponse | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState(false);
  const [isTelemetryOpen, setIsTelemetryOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);


  // Fetch API Health & Active Sessions
  const fetchHealth = async () => {
    try {
      const res = await fetch(getApiUrl('/health'));
      if (res.ok) {
        const data: HealthResponse = await res.json();
        setHealth(data);
      }
    } catch (err) {
      console.error('Health fetch error:', err);
    }
  };


  const fetchSessions = async (targetUserId?: string) => {
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
  };

  useEffect(() => {
    fetchHealth();
    fetchSessions();
  }, [currentUser]);

  const handleAuthSuccess = (user: UserProfile) => {
    setCurrentUser(user);
    localStorage.setItem('bis_user', JSON.stringify(user));
    fetchSessions(user.user_id);
  };

  const handleLogout = () => {
    setCurrentUser(null);
    localStorage.removeItem('bis_user');
    setMessages([]);
    setLastResponse(null);
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
              } else if (data.type === 'result' && data.payload) {
                const resData: QueryResponse = data.payload;
                setLastResponse(resData);
                const assistantMsg: ChatMessage = {
                  id: (Date.now() + 1).toString(),
                  sender: 'assistant',
                  text: resData.core_response,
                  response: resData,
                  timestamp: new Date().toLocaleTimeString(),
                };
                setMessages((prev) => [...prev, assistantMsg]);
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
    setActiveSessionId(sessionId);
    setMessages([]);
    setLastResponse(null);
    try {
      const res = await fetch(getApiUrl(`/api/v1/sessions/${encodeURIComponent(sessionId)}`));
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
    const newId = `session-${Math.floor(1000 + Math.random() * 9000)}`;
    setActiveSessionId(newId);
    setMessages([]);
    setLastResponse(null);
  };

  const handleClearSession = async (sessionIdToClear: string) => {
    // Optimistically filter out deleted session
    setSessions((prev) => prev.filter((s) => s.session_id !== sessionIdToClear));

    if (sessionIdToClear === activeSessionId) {
      const newId = `session-${Math.floor(1000 + Math.random() * 9000)}`;
      setActiveSessionId(newId);
      setMessages([]);
      setLastResponse(null);
    }

    try {
      await fetch(getApiUrl(`/api/v1/sessions/${encodeURIComponent(sessionIdToClear)}`), { method: 'DELETE' });
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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      {/* Header Bar */}
      <Header
        health={health}
        currentUser={currentUser}
        onToggleTelemetry={() => setIsTelemetryOpen((prev) => !prev)}
        onOpenAuditLedger={() => setIsAuditLedgerOpen(true)}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        onOpenProfileModal={handleOpenProfileModal}
        onLogout={handleLogout}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
      />


      {/* Main App Workspace */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Sidebar */}
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          currentUser={currentUser}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onClearSession={handleClearSession}
          onClearCache={handleClearCache}
          onSelectPrompt={(prompt) => handleSendMessage(prompt)}
          onOpenAuthModal={() => setIsAuthModalOpen(true)}
          onOpenProfileModal={() => handleOpenProfileModal('usage')}
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
        />


        {/* Telemetry Drawer */}
        <TelemetryPanel
          isOpen={isTelemetryOpen}
          onClose={() => setIsTelemetryOpen(false)}
          lastResponse={lastResponse}
        />
      </div>

      {/* Modals */}
      <UserProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
        currentUser={currentUser}
        lastResponse={lastResponse}
        initialTab={profileModalTab}
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
      />

      <AuditLedgerModal
        isOpen={isAuditLedgerOpen}
        onClose={() => setIsAuditLedgerOpen(false)}
      />
    </div>
  );

};

export default App;

