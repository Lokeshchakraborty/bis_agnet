import React, { useState, useRef } from 'react';
import { Mic, Square, X, Send, Loader2, Volume2 } from 'lucide-react';
import type { VoiceQueryResponse } from '../types';


interface VoiceRecorderModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
  onVoiceSuccess: (voiceResponse: VoiceQueryResponse) => void;
}

export const VoiceRecorderModal: React.FC<VoiceRecorderModalProps> = ({
  isOpen,
  onClose,
  sessionId,
  onVoiceSuccess,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingBlob, setRecordingBlob] = useState<Blob | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<number | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  if (!isOpen) return null;

  const startRecording = async () => {
    try {
      setErrorMessage('');
      setRecordingBlob(null);
      audioChunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setRecordingBlob(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      timerRef.current = window.setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      setErrorMessage('Microphone access denied or unsupported browser.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleSendVoiceQuery = async () => {
    if (!recordingBlob) return;
    setIsUploading(true);
    setErrorMessage('');

    try {
      const formData = new FormData();
      formData.append('file', recordingBlob, 'recording.webm');
      formData.append('session_id', sessionId);

      const response = await fetch('/api/v1/voice-query', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Voice processing error');
      }

      const data: VoiceQueryResponse = await response.json();
      onVoiceSuccess(data);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to submit voice query.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(7, 9, 19, 0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
        {/* Modal Container */}
        <div style={{ background: 'var(--gemini-bg-card)', border: '1px solid var(--glass-border)', borderRadius: '24px', width: '420px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', position: 'relative' }}>
          {/* Close Button */}
          <button
            onClick={onClose}
            style={{ position: 'absolute', top: '16px', right: '16px', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>

          {/* Modal Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ padding: '10px', borderRadius: '50%', background: 'rgba(155, 81, 224, 0.15)', color: 'var(--gemini-purple)' }}>
              <Volume2 size={22} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#FFFFFF' }}>Gemini Voice RAG</h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Speak your query. Whisper Speech-to-Text will transcribe and query RAG.
              </p>
            </div>
          </div>

          {/* Visual Recording Wave Animation */}
          <div style={{ height: '100px', background: 'rgba(0, 0, 0, 0.3)', borderRadius: '16px', border: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '0 24px' }}>
            {isRecording ? (
              Array.from({ length: 12 }).map((_, idx) => (
                <div
                  key={idx}
                  className="gemini-pulse"
                  style={{
                    width: '6px',
                    height: '50px',
                    borderRadius: '999px',
                    background: 'var(--gemini-sparkle-gradient)',
                    animationDelay: `${(idx % 4) * 0.2}s`,
                  }}
                />
              ))
            ) : (
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {recordingBlob ? 'Recording ready to submit!' : 'Click Microphone to start recording'}
              </span>
            )}
          </div>

          {/* Timer */}
          {isRecording && (
            <div style={{ textAlign: 'center', fontSize: '1.2rem', fontWeight: 700, color: 'var(--gemini-purple)' }} className="mono">
              00:{recordingTime < 10 ? `0${recordingTime}` : recordingTime}
            </div>
          )}

          {errorMessage && (
            <div style={{ color: '#EF4444', fontSize: '0.78rem', textAlign: 'center' }}>
              {errorMessage}
            </div>
          )}

          {/* Controls */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
            {!isRecording ? (
              <button
                onClick={startRecording}
                style={{
                  width: '60px',
                  height: '60px',
                  borderRadius: '50%',
                  background: 'var(--gemini-sparkle-gradient)',
                  border: 'none',
                  color: '#FFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  boxShadow: '0 0 20px rgba(155, 81, 224, 0.4)',
                }}
              >
                <Mic size={26} />
              </button>
            ) : (
              <button
                onClick={stopRecording}
                style={{
                  width: '60px',
                  height: '60px',
                  borderRadius: '50%',
                  background: '#EF4444',
                  border: 'none',
                  color: '#FFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  boxShadow: '0 0 20px rgba(239, 68, 68, 0.4)',
                }}
              >
                <Square size={24} />
              </button>
            )}

            {recordingBlob && !isRecording && (
              <button
                onClick={handleSendVoiceQuery}
                disabled={isUploading}
                style={{
                  padding: '12px 24px',
                  borderRadius: '24px',
                  background: 'var(--gemini-sparkle-gradient)',
                  border: 'none',
                  color: '#FFF',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                {isUploading ? <Loader2 size={18} className="gemini-pulse" /> : <Send size={18} />}
                {isUploading ? 'Transcribing...' : 'Submit Voice Query'}
              </button>
            )}
          </div>
        </div>
    </div>
  );
};
