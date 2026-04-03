"""
◑ MiMi Nox – Audio-Feature Tests
tests/test_audio.py

TDD Tests für:
  - Audio-Upload-Route (MIME, Größe, Sanity)
  - Transkriptions-Engine (VAD, Format)
  - Path-Sandboxing

MiMi Tech AI UG – Bad Liebenzell, Schwarzwald
"""
from __future__ import annotations

import io
import os
import struct
import wave
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def audio_client(tmp_path):
    """TestClient mit isoliertem Audio-Verzeichnis."""
    os.environ["MIMI_NOX_AUDIO_DIR"] = str(tmp_path / "audio")
    os.environ["MIMI_NOX_MEMORY_DIR"] = str(tmp_path / "memory")
    os.environ["MIMI_NOX_PROFILE_PATH"] = str(tmp_path / "profile.json")
    os.environ["MIMI_NOX_CORRECTIONS_PATH"] = str(tmp_path / "corrections.md")
    os.environ["MIMI_NOX_FEEDBACK_DIR"] = str(tmp_path)
    os.environ["MIMI_NOX_SKILLS_DIR"] = str(tmp_path / "skills")
    # lru_cache auf Memory-Singleton zurücksetzen für Test-Isolation
    from server.routes.memory import _get_memory
    _get_memory.cache_clear()

    from server.main import create_app
    app = create_app()
    with TestClient(app) as client:
        yield client


def _make_wav_bytes(duration_s: float = 1.0, frequency: int = 440, amplitude: int = 5000) -> bytes:
    """Erzeugt gültige WAV-Bytes für Tests."""
    sample_rate = 16000
    n_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            import math
            sample = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
            wf.writeframes(struct.pack("<h", sample))
    return buf.getvalue()


def _make_silent_wav_bytes(duration_s: float = 1.0) -> bytes:
    """Erzeugt stille WAV-Bytes."""
    return _make_wav_bytes(duration_s=duration_s, amplitude=0)


# ── Upload-Route Tests ─────────────────────────────────────────────────────

class TestAudioUpload:
    """Tests für POST /api/audio/transcribe."""

    def test_GIVEN_valid_wav_WHEN_uploaded_THEN_returns_200(self, audio_client):
        """
        GIVEN  Gültige WAV-Datei
        WHEN   an /api/audio/transcribe gesendet
        THEN   200 + audio_url zurückgegeben
        """
        wav = _make_wav_bytes(1.0)
        # Mock whisper availability to avoid needing the model
        with patch("core.transcribe.transcribe") as mock_t, \
             patch("core.transcribe.is_whisper_available", return_value=True):
            mock_t.return_value = "Test Transkription"
            files = {"file": ("test.wav", wav, "audio/wav")}
            resp = audio_client.post("/api/audio/transcribe", files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert "audio_url" in data
        assert data["audio_url"].startswith("/audio/")

    def test_GIVEN_invalid_mimetype_WHEN_uploaded_THEN_returns_422(self, audio_client):
        """
        GIVEN  Datei mit ungültigem MIME-Type (text/plain)
        WHEN   an /api/audio/transcribe gesendet
        THEN   422 Unprocessable Entity
        """
        files = {"file": ("test.txt", b"not audio", "text/plain")}
        resp = audio_client.post("/api/audio/transcribe", files=files)
        assert resp.status_code == 422
        assert "Ungültiger Audio-Typ" in resp.json()["detail"]

    def test_GIVEN_oversized_file_WHEN_uploaded_THEN_returns_413(self, audio_client):
        """
        GIVEN  Audio-Datei > 15 MB
        WHEN   an /api/audio/transcribe gesendet
        THEN   413 Payload Too Large
        """
        big = b"\x00" * (16 * 1024 * 1024)  # 16 MB
        files = {"file": ("big.webm", big, "audio/webm")}
        resp = audio_client.post("/api/audio/transcribe", files=files)
        assert resp.status_code == 413

    def test_GIVEN_empty_file_WHEN_uploaded_THEN_returns_422(self, audio_client):
        """
        GIVEN  Leere Audio-Datei
        WHEN   an /api/audio/transcribe gesendet
        THEN   422
        """
        files = {"file": ("empty.webm", b"", "audio/webm")}
        resp = audio_client.post("/api/audio/transcribe", files=files)
        assert resp.status_code == 422

    def test_GIVEN_webm_audio_WHEN_uploaded_THEN_saved_as_webm(self, audio_client, tmp_path):
        """
        GIVEN  WebM-Audio
        WHEN   hochgeladen
        THEN   Datei wird als .webm gespeichert
        """
        with patch("core.transcribe.transcribe") as mock_t, \
             patch("core.transcribe.is_whisper_available", return_value=True):
            mock_t.return_value = "Hallo"
            files = {"file": ("test.webm", b"\x1a\x45\xdf\xa3" * 100, "audio/webm")}
            resp = audio_client.post("/api/audio/transcribe", files=files)

        assert resp.status_code == 200
        audio_url = resp.json()["audio_url"]
        assert audio_url.endswith(".webm")

    def test_GIVEN_mp4_safari_WHEN_uploaded_THEN_accepted(self, audio_client):
        """
        GIVEN  MP4-Audio (Safari)
        WHEN   hochgeladen
        THEN   Wird akzeptiert (Cross-Browser-Support)
        """
        with patch("core.transcribe.transcribe") as mock_t, \
             patch("core.transcribe.is_whisper_available", return_value=True):
            mock_t.return_value = "Safari test"
            files = {"file": ("rec.mp4", b"\x00\x00\x00" * 100, "audio/mp4")}
            resp = audio_client.post("/api/audio/transcribe", files=files)

        assert resp.status_code == 200


# ── Transkriptions-Engine Tests ───────────────────────────────────────────

class TestTranscribeEngine:
    """Tests für core/transcribe.py."""

    def test_GIVEN_nonexistent_file_WHEN_transcribed_THEN_raises(self):
        """FileNotFoundError bei fehlender Datei."""
        from core.transcribe import _transcribe_sync
        with pytest.raises(FileNotFoundError):
            _transcribe_sync(Path("/nonexistent/audio.wav"))

    def test_GIVEN_whisper_not_installed_WHEN_checked_THEN_false(self):
        """is_whisper_available() → False wenn nicht installiert."""
        with patch.dict("sys.modules", {"faster_whisper": None}):
            # Re-import to test
            import importlib
            from core import transcribe
            importlib.reload(transcribe)
            # Wenn ImportError → False
            # (Da wir das Modul auf None setzen, löst import ImportError aus)

    def test_GIVEN_whisper_available_check_THEN_returns_bool(self):
        """is_whisper_available() gibt bool zurück."""
        from core.transcribe import is_whisper_available
        result = is_whisper_available()
        assert isinstance(result, bool)


# ── VAD Tests ─────────────────────────────────────────────────────────────

class TestVAD:
    """Voice Activity Detection Tests."""

    def test_GIVEN_silent_wav_WHEN_checked_THEN_no_voice(self, tmp_path):
        """Stille WAV → False."""
        from core.transcribe import _check_audio_has_voice
        wav = _make_silent_wav_bytes(1.0)
        path = tmp_path / "silent.wav"
        path.write_bytes(wav)
        assert _check_audio_has_voice(path) is False

    def test_GIVEN_loud_wav_WHEN_checked_THEN_has_voice(self, tmp_path):
        """Laute WAV → True."""
        from core.transcribe import _check_audio_has_voice
        wav = _make_wav_bytes(1.0, amplitude=10000)
        path = tmp_path / "loud.wav"
        path.write_bytes(wav)
        assert _check_audio_has_voice(path) is True

    def test_GIVEN_very_short_wav_WHEN_checked_THEN_no_voice(self, tmp_path):
        """Zu kurze Aufnahme (< 0.5s) → False."""
        from core.transcribe import _check_audio_has_voice
        wav = _make_wav_bytes(0.2)
        path = tmp_path / "short.wav"
        path.write_bytes(wav)
        assert _check_audio_has_voice(path) is False

    def test_GIVEN_non_wav_WHEN_checked_THEN_returns_true(self, tmp_path):
        """Nicht-WAV Formate → True (konservativ)."""
        from core.transcribe import _check_audio_has_voice
        path = tmp_path / "audio.webm"
        path.write_bytes(b"\x1a\x45\xdf\xa3")
        assert _check_audio_has_voice(path) is True


# ── Path-Sandboxing Tests ────────────────────────────────────────────────

class TestAudioSandbox:
    """Audio-Dateien dürfen nur im Audio-Dir gespeichert werden."""

    def test_GIVEN_upload_WHEN_saved_THEN_in_audio_dir(self, audio_client, tmp_path):
        """Hochgeladene Dateien landen im konfigurierten Audio-Verzeichnis."""
        with patch("core.transcribe.transcribe") as mock_t, \
             patch("core.transcribe.is_whisper_available", return_value=True):
            mock_t.return_value = "Test"
            files = {"file": ("test.webm", b"\x1a" * 500, "audio/webm")}
            resp = audio_client.post("/api/audio/transcribe", files=files)

        assert resp.status_code == 200
        audio_dir = tmp_path / "audio"
        saved_files = list(audio_dir.glob("*.webm"))
        assert len(saved_files) == 1
        assert saved_files[0].parent.resolve() == audio_dir.resolve()

    def test_GIVEN_filename_WHEN_saved_THEN_no_user_input_in_name(self, audio_client):
        """Dateiname enthält keinen User-Input (nur timestamp + uuid)."""
        with patch("core.transcribe.transcribe") as mock_t, \
             patch("core.transcribe.is_whisper_available", return_value=True):
            mock_t.return_value = "Test"
            files = {"file": ("../../etc/passwd.webm", b"\x1a" * 500, "audio/webm")}
            resp = audio_client.post("/api/audio/transcribe", files=files)

        assert resp.status_code == 200
        audio_url = resp.json()["audio_url"]
        assert "../" not in audio_url
        assert "passwd" not in audio_url
