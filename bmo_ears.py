"""
bmo_ears.py
───────────
Pucky listens.

Uses pw-record (PipeWire) to capture audio from the Jabra mic, then
faster-whisper (offline) to transcribe speech. Calls on_speech_fn
with the recognised text.

Written with love by Loki for Iðunn.
"""

import subprocess
import threading
import tempfile
import time
import os
import numpy as np
import soundfile as sf
from pathlib import Path
from faster_whisper import WhisperModel

SAMPLE_RATE  = 16000
CHUNK_SECS   = 0.5          # how often we sample for speech onset
MAX_PHRASE   = 12.0         # max seconds to collect before forcing transcription
SILENCE_SECS = 0.9          # silence after speech that ends a phrase
SPEECH_RMS   = 0.002        # RMS threshold — below this is silence
MODEL_SIZE   = "tiny"


class PuckyEars:

    def __init__(self, on_speech_fn, mute_fn=None):
        """
        on_speech_fn(text) — called with recognised text in a background thread.
        mute_fn()          — optional callable that returns True while Pucky is speaking
                             (prevents feedback loop).
        """
        self._on_speech = on_speech_fn
        self._mute_fn   = mute_fn
        self._model     = None
        self._running   = False
        self._thread    = None
        self.muted      = False

    # ─────────────────────────────────────────
    #  PUBLIC
    # ─────────────────────────────────────────

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._boot, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    # ─────────────────────────────────────────
    #  INTERNAL
    # ─────────────────────────────────────────

    def _boot(self):
        print("👂 Ears: loading Whisper model...")
        try:
            self._model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
            print("👂 Ears: listening.")
        except Exception as e:
            print(f"  ⚠️  Ears: model load failed: {e}")
            return
        self._listen_loop()

    def _record_chunk(self, secs: float) -> np.ndarray | None:
        """Record `secs` seconds from the mic, return float32 array or None."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            r = subprocess.run(
                ["timeout", str(secs),
                 "pw-record",
                 "--rate", str(SAMPLE_RATE),
                 "--channels", "1",
                 "--format", "s16",
                 path],
                capture_output=True, timeout=secs + 3
            )
            # timeout exits with 124; pw-record exits 0 on clean stop — both fine
            if r.returncode not in (0, 124):
                return None
            data, _ = sf.read(path, dtype="float32")
            return data
        except Exception:
            return None
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def _rms(self, data: np.ndarray) -> float:
        return float(np.sqrt(np.mean(data ** 2))) if len(data) else 0.0

    def _transcribe(self, audio: np.ndarray) -> str:
        """Transcribe an audio array, return stripped text."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            sf.write(path, audio, SAMPLE_RATE)
            segments, _ = self._model.transcribe(
                path,
                language="en",
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
            text = " ".join(s.text for s in segments).strip()
            # filter out Whisper tiny hallucinations on silence/noise
            _HALLUCINATIONS = {
                "", "you", "yes", "yeah", "yep", "no", "nope",
                "okay", "ok", "um", "uh", "hmm", "mm", "mmm",
                "thank you.", "thank you", "thanks", "thanks for watching.",
                "please", "hello", "bye", "goodbye",
                "music", "music playing", "background music",
                "[ music ]", "[music]", "(music)", "♪",
            }
            if text.lower().strip(".,!? ") in _HALLUCINATIONS or text.lower() in _HALLUCINATIONS:
                return ""
            return text
        except Exception as e:
            print(f"  ⚠️  Ears: transcribe error: {e}")
            return ""
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def _is_muted(self) -> bool:
        if self.muted:
            return True
        if self._mute_fn:
            try:
                return bool(self._mute_fn())
            except Exception:
                pass
        return False

    def _listen_loop(self):
        chunks      = []   # accumulated speech chunks
        silence_run = 0.0  # seconds of consecutive silence after speech onset
        speaking    = False

        while self._running:
            if self._is_muted():
                time.sleep(0.2)
                continue

            chunk = self._record_chunk(CHUNK_SECS)
            if chunk is None:
                time.sleep(0.2)
                continue

            rms = self._rms(chunk)

            if rms >= SPEECH_RMS:
                speaking     = True
                silence_run  = 0.0
                chunks.append(chunk)
            elif speaking:
                silence_run += CHUNK_SECS
                chunks.append(chunk)   # include the trailing silence for context

                total_secs = len(chunks) * CHUNK_SECS
                if silence_run >= SILENCE_SECS or total_secs >= MAX_PHRASE:
                    audio = np.concatenate(chunks)
                    chunks      = []
                    silence_run = 0.0
                    speaking    = False

                    text = self._transcribe(audio)
                    if text:
                        print(f"👂 heard: {text}")
                        try:
                            self._on_speech(text)
                        except Exception as e:
                            print(f"  ⚠️  Ears: on_speech error: {e}")
