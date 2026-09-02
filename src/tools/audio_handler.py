import os
import queue
import numpy as np
import sounddevice as sd
import soundfile as sf
import whisper
import warnings

# Suppress whisper FP16 warnings on CPU
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

class LocalAudioHandler:
    def __init__(self, model_size="base"):
        print(f"[dim]Loading Whisper '{model_size}' model locally (this takes a moment)...[/dim]")
        # 'base' or 'small' models are best for local CPU execution. 
        # They naturally handle code-switching like Hinglish.
        self.model = whisper.load_model(model_size)
        self.fs = 16000  # Whisper expects 16kHz audio

    def record_audio(self, filename="temp_query.wav"):
        """Records audio from the microphone until the user presses Enter."""
        q = queue.Queue()
        
        def callback(indata, frames, time, status):
            if status:
                print(status, flush=True)
            q.put(indata.copy())

        print("\n🎤 [bold red]Recording... Speak your query (Hinglish/English).[/bold red]")
        print("[dim]Press [ENTER] to stop recording...[/dim]", end="", flush=True)
        
        # Start microphone stream
        stream = sd.InputStream(samplerate=self.fs, channels=1, callback=callback)
        with stream:
            input()  # Block execution until user presses Enter
            
        print("✅ [dim]Recording saved. Processing...[/dim]")
        
        # Compile audio chunks
        audio_data = []
        while not q.empty():
            audio_data.append(q.get())
        
        audio_array = np.concatenate(audio_data, axis=0)
        
        # Save to WAV file
        sf.write(filename, audio_array, self.fs)
        return filename

    def transcribe(self, filename="temp_query.wav") -> str:
        """Transcribes the saved audio file to text."""
        try:
            # task="translate" forces English output. 
            # task="transcribe" keeps original Hinglish/Hindi text. 
            # We use transcribe because Gemini handles raw Hinglish perfectly.
            result = self.model.transcribe(filename, task="transcribe")
            text = result["text"].strip()
            
            # Clean up temp file
            if os.path.exists(filename):
                os.remove(filename)
                
            return text
        except Exception as e:
            return f"Audio Error: {str(e)}"

    def speak_text(self, text: str) -> None:
        """Speaks the response text aloud using local TTS engine."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)  # Natural speaking rate
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            warnings.warn(f"Audio playback warning: {exc}", stacklevel=2)