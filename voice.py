import subprocess
import tempfile
import os
import re
import urllib.request
import wave
from pathlib import Path
from piper import PiperVoice

# Model configuration
# Recommended: en_US-lessac-high (60MB)
# Others: en_US-ljspeech-high, en_GB-alba-medium, en_US-amy-medium
VOICE_MODEL = "en_US-lessac-high.onnx"
MODEL_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/{VOICE_MODEL}"
CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/{VOICE_MODEL}.json"

MODEL_PATH = (Path(__file__).parent / "models" / VOICE_MODEL).resolve()
CONFIG_PATH = (Path(__file__).parent / "models" / f"{VOICE_MODEL}.json").resolve()

def _ensure_model():
    """Download the Piper voice model if not already present."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MODEL_PATH.exists() or not CONFIG_PATH.exists():
        print(f"[ FRIDAY ] Downloading voice model: {VOICE_MODEL} (~60MB, one-time only)...")
        # Ensure partial files don't block download
        if MODEL_PATH.exists(): MODEL_PATH.unlink()
        if CONFIG_PATH.exists(): CONFIG_PATH.unlink()
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        urllib.request.urlretrieve(CONFIG_URL, CONFIG_PATH)
        print("[ FRIDAY ] Voice model ready.")

# Load model once at import time
_ensure_model()
try:
    _voice = PiperVoice.load(str(MODEL_PATH), config_path=str(CONFIG_PATH), use_cuda=False)
except Exception as e:
    print(f"[ FRIDAY ] Failed to load Piper model: {e}")
    print("[ FRIDAY ] Attempting to redownload...")
    if MODEL_PATH.exists(): MODEL_PATH.unlink()
    if CONFIG_PATH.exists(): CONFIG_PATH.unlink()
    _ensure_model()
    _voice = PiperVoice.load(str(MODEL_PATH), config_path=str(CONFIG_PATH), use_cuda=False)

def speak(text: str):
    """Synthesize text to speech using Piper and play it locally."""
    if not text or not text.strip():
        return
    
    # Strip markdown and clean text
    text = re.sub(r'[*#`_]', '', text).strip()
    
    # Synthesize to temp WAV and play
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
        # Use wave.open to ensure correct WAV header
        with wave.open(tmp_path, "wb") as wav_file:
            _voice.synthesize_wav(text, wav_file)
            
    try:
        # Playing audio on macOS
        subprocess.run(["afplay", tmp_path], check=True)
    except Exception as e:
        print(f"[ FRIDAY ] Audio playback error: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
