import asyncio
import os
import re
import urllib.request
import wave
from pathlib import Path
from tempfile import NamedTemporaryFile

from piper import PiperVoice


VOICE_MODEL = "en_US-lessac-high.onnx"
MODEL_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    f"en/en_US/lessac/high/{VOICE_MODEL}"
)
CONFIG_URL = f"{MODEL_URL}.json"

MODEL_PATH = (Path(__file__).parent / "models" / VOICE_MODEL).resolve()
CONFIG_PATH = (Path(__file__).parent / "models" / f"{VOICE_MODEL}.json").resolve()


def _strip_for_voice(text: str) -> str:
    cleaned = re.sub(r"https?://\S+", "", text)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\([^)]+://[^)]+\)", "", cleaned)
    cleaned = re.sub(r"[*#`_>{}|~]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _ensure_model() -> None:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists() and CONFIG_PATH.exists():
        return

    print(f"[ FRIDAY ] Downloading voice model: {VOICE_MODEL} (~60MB, one-time only)...")
    if MODEL_PATH.exists():
        MODEL_PATH.unlink()
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    urllib.request.urlretrieve(CONFIG_URL, CONFIG_PATH)
    print("[ FRIDAY ] Voice model ready.")


_ensure_model()

try:
    _VOICE = PiperVoice.load(str(MODEL_PATH), config_path=str(CONFIG_PATH), use_cuda=False)
except Exception as exc:
    print(f"[ FRIDAY ] Failed to load Piper model: {exc}")
    if MODEL_PATH.exists():
        MODEL_PATH.unlink()
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
    _ensure_model()
    _VOICE = PiperVoice.load(str(MODEL_PATH), config_path=str(CONFIG_PATH), use_cuda=False)


class SpeechEngine:
    def __init__(self) -> None:
        self._playback: asyncio.subprocess.Process | None = None
        self._playback_lock = asyncio.Lock()
        self._current_tmp_path: str | None = None

    @staticmethod
    def sanitize(text: str) -> str:
        return _strip_for_voice(text)

    def _synthesize_to_wav(self, text: str) -> str:
        with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        with wave.open(tmp_path, "wb") as wav_file:
            _VOICE.synthesize_wav(text, wav_file)

        return tmp_path

    async def stop(self) -> None:
        async with self._playback_lock:
            if self._playback and self._playback.returncode is None:
                self._playback.terminate()
                try:
                    await asyncio.wait_for(self._playback.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    self._playback.kill()
                    await self._playback.wait()

            self._playback = None
            if self._current_tmp_path and os.path.exists(self._current_tmp_path):
                os.unlink(self._current_tmp_path)
            self._current_tmp_path = None

    async def speak(self, text: str) -> None:
        spoken = self.sanitize(text)
        if not spoken:
            return

        wav_path = await asyncio.to_thread(self._synthesize_to_wav, spoken)

        async with self._playback_lock:
            if self._playback and self._playback.returncode is None:
                self._playback.terminate()
                await self._playback.wait()

            self._current_tmp_path = wav_path
            self._playback = await asyncio.create_subprocess_exec("afplay", wav_path)
            playback = self._playback

        try:
            await playback.wait()
        finally:
            async with self._playback_lock:
                if self._current_tmp_path and os.path.exists(self._current_tmp_path):
                    os.unlink(self._current_tmp_path)
                self._current_tmp_path = None
                if self._playback is playback:
                    self._playback = None


default_engine = SpeechEngine()
