"""
◑ MiMi Nox – Audio-Transkription
core/transcribe.py

Lokale Speech-to-Text-Verarbeitung via faster-whisper.
100% lokal – kein Cloud-Call, kein API-Key nötig.

Features:
  - Voice Activity Detection (VAD): Stille → kein teurer STT-Call
  - Async-kompatibel via asyncio.to_thread()
  - Cross-Browser Audio-Formate (webm, mp4, wav, m4a)

MiMi Tech AI UG – Bad Liebenzell, Schwarzwald
"""
from __future__ import annotations

import asyncio
import wave
import struct
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Konfiguration ──────────────────────────────────────────────────────────

WHISPER_MODEL = "tiny"  # 'tiny' (39MB, extrem schnell) | 'base' (74MB)
WHISPER_LANGUAGE = "de"
MIN_AUDIO_DURATION_S = 0.5  # Mindestlänge in Sekunden
VAD_SILENCE_THRESHOLD = 300  # RMS-Schwellenwert für Stille-Erkennung


# ── Lazy-Loading des Whisper-Modells ───────────────────────────────────────

_model = None


def _get_model():
    """
    Lazy-Load des faster-whisper Modells.
    Wird nur beim ersten Aufruf geladen, danach gecacht.
    """
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
            logger.info("Lade Whisper-Modell '%s'…", WHISPER_MODEL)
            _model = WhisperModel(
                WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
            )
            logger.info("Whisper-Modell geladen.")
        except ImportError:
            raise RuntimeError(
                "faster-whisper ist nicht installiert. "
                "Installiere mit: pip install faster-whisper"
            )
    return _model


# ── Voice Activity Detection ──────────────────────────────────────────────

def _check_audio_has_voice(audio_path: Path) -> bool:
    """
    Einfacher VAD-Check: Prüft ob die Audio-Datei hörbare Sprache enthält.

    Für WAV-Dateien: berechnet RMS-Lautstärke.
    Für andere Formate: gibt True zurück (konservativ).

    Returns:
        True wenn Sprache erkannt wird, False bei reiner Stille
    """
    if audio_path.suffix.lower() != ".wav":
        # Für nicht-WAV: konservativ True (Whisper macht eigenen VAD)
        return True

    try:
        with wave.open(str(audio_path), "rb") as wf:
            n_frames = wf.getnframes()
            if n_frames == 0:
                return False

            framerate = wf.getframerate()
            duration = n_frames / framerate 
            if duration < MIN_AUDIO_DURATION_S:
                return False

            # RMS-Lautstärke berechnen (Sample aus der Mitte)
            sample_frames = min(n_frames, framerate)  # max 1 Sekunde
            wf.setpos(max(0, n_frames // 2 - sample_frames // 2))
            raw = wf.readframes(sample_frames)

            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()

            if sample_width == 2:
                fmt = f"<{len(raw) // 2}h"
                samples = struct.unpack(fmt, raw)
                # Mono-Mix
                if n_channels == 2:
                    samples = samples[::2]
                rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                return rms > VAD_SILENCE_THRESHOLD

        return True  # Fallback: annehmen es ist OK
    except Exception:
        return True  # Im Zweifel: transkribieren


# ── Transkription ──────────────────────────────────────────────────────────

def _transcribe_sync(audio_path: Path) -> str:
    """
    Synchrone Transkription einer Audio-Datei.
    Wird via asyncio.to_thread() aufgerufen um die Event-Loop nicht zu blockieren.

    Returns:
        Transkribierter Text oder leerer String bei Stille/Fehler
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio-Datei nicht gefunden: {audio_path}")

    # VAD-Check: Stille überspringen
    if not _check_audio_has_voice(audio_path):
        logger.info("VAD: Keine Sprache erkannt in %s", audio_path.name)
        return ""

    model = _get_model()

    segments, info = model.transcribe(
        str(audio_path),
        language=WHISPER_LANGUAGE,
        beam_size=5,
        vad_filter=True,  # Whisper-eigener VAD-Filter
    )

    text_parts = []
    for segment in segments:
        text_parts.append(segment.text.strip())

    result = " ".join(text_parts).strip()
    logger.info(
        "Transkription (%s, %.1fs): '%s'",
        audio_path.name,
        info.duration,
        result[:80] + "…" if len(result) > 80 else result,
    )
    return result


async def transcribe(audio_path: Path) -> str:
    """
    Asynchrone Transkription einer Audio-Datei.

    Läuft in asyncio.to_thread() um die Event-Loop nicht zu blockieren.
    Inkl. VAD-Prüfung: Bei reiner Stille wird kein STT-Call gemacht.

    Args:
        audio_path: Pfad zur Audio-Datei (.wav, .webm, .mp4, .m4a)

    Returns:
        Transkribierter Text oder leerer String

    Raises:
        FileNotFoundError: Audio-Datei existiert nicht
        RuntimeError: faster-whisper nicht installiert
    """
    return await asyncio.to_thread(_transcribe_sync, audio_path)


def is_whisper_available() -> bool:
    """Prüft ob faster-whisper installiert und nutzbar ist."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
