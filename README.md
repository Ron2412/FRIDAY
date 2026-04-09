# FRIDAY - Personal AI Assistant

A fully local (except for Google Calendar and initial STT model checks), voice-first AI assistant built with python.

## Prerequisites & System Setup

Since FRIDAY uses hardware audio devices and external transcription binaries, some system-level libraries are required.

### 1. Install System Dependencies (macOS)
You need `ffmpeg` for Whisper, and `portaudio` for `pyaudio` microphone access.
```bash
brew install portaudio ffmpeg
```

### 2. Install Python Dependencies
It is highly recommended to use a virtual environment.
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Ollama Setup
You mentioned Ollama is already installed on your Mac. You simply need to ensure the right model is pulled and running.
FRIDAY is configured to use `llama3.2:3b`.
```bash
ollama pull llama3.2:3b
# Ensure Ollama is running in the background (usually the desktop app takes care of this).
```

### 4. OpenWakeWord Engine
FRIDAY uses [OpenWakeWord](https://github.com/dscripka/openWakeWord) to detect a wake word. 
We use the built-in `hey_jarvis` model. 
No API keys or cloud accounts are required as it runs completely locally!

*Note: You can trigger the assistant by saying "Hey Jarvis".*

### 5. Google Calendar Setup
You need OAuth 2.0 Client credentials to read from your calendar.
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Enable the **Google Calendar API**.
4. Go to **Credentials** -> **Create Credentials** -> **OAuth client ID**.
5. Choose "Desktop app" (or similar).
6. Download the resulting JSON file and save it as `credentials.json` directly inside the `ultron/` folder.
7. The first time you ask FRIDAY to check your calendar, a browser window will pop up asking for your authorization.

## Voice Model
On first run, FRIDAY will automatically download the Piper TTS voice model (~60MB) from HuggingFace. This is a one-time download. After that, everything runs 100% offline with no internet required.

To change the voice, edit VOICE_MODEL in voice.py and update MODEL_URL/CONFIG_URL to point to your preferred Piper voice from: https://huggingface.co/rhasspy/piper-voices

## Running FRIDAY
Once everything is set up, run:
```bash
python main.py
```
