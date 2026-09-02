"""
Local Audio Processing (Whisper STT + Pyttsx3 Offline TTS)
===========================================================
Handles voice input capture, offline speech-to-text transcription with Whisper,
and offline text-to-speech audio feedback.
"""
from __future__ import annotations

import logging
import os
import queue
import warnings
from typing import Optional

import numpy as np

# Suppress whisper FP16 warnings on CPU
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

logger = logging.getLogger("bis_audio")


class LocalAudioHandler:
    """Offline voice recorder, Whisper speech-to-text transcriber, and TTS speaker."""

    def __init__(self, model_size: str = "base", sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.model_size = model_size
        self._model = None

    @property
    def model(self):
        """Lazy loader for Whisper model."""
        if self._model is None:
            import whisper
            logger.info("Loading Whisper '%s' model...", self.model_size)
            self._model = whisper.load_model(self.model_size)
        return self._model

    def record_audio(self, filename: str = "temp_query.wav") -> str:
        """Record audio from microphone until user presses Enter."""
        import sounddevice as sd
        import soundfile as sf

        q: queue.Queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                logger.warning("Audio recording status: %s", status)
            q.put(indata.copy())

        print("\n🎤 Recording... Speak your question (English / Hindi / Hinglish).")
        print("Press [ENTER] to stop recording...", end="", flush=True)

        stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=callback)
        with stream:
            input()

        print("✅ Recording saved. Processing audio...")

        audio_chunks = []
        while not q.empty():
            audio_chunks.append(q.get())

        if not audio_chunks:
            return ""

        audio_array = np.concatenate(audio_chunks, axis=0)
        sf.write(filename, audio_array, self.sample_rate)
        return filename

    def transcribe(self, filename: str = "temp_query.wav") -> str:
        """Transcribe WAV audio file into text using Whisper."""
        if not filename or not os.path.exists(filename):
            return ""

        try:
            # task='transcribe' keeps original Hinglish/Hindi text without forced translation
            result = self.model.transcribe(filename, task="transcribe")
            text = result.get("text", "").strip()
            return text
        except Exception as exc:
            logger.error("Audio transcription failed: %s", exc)
            return f"Audio Error: {exc}"
        finally:
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass

    def speak_text(self, text: str, rate: int = 175) -> None:
        """Speak response aloud using local pyttsx3 engine."""
        if not text:
            return
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            logger.warning("Audio playback warning: %s", exc)
