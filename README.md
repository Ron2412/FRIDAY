# FRIDAY - Personal AI Assistant

A multimodal FRIDAY desktop assistant built with Python, Gemini 2.5 Flash, MCP-style tool routing, and an async runtime designed for voice-first interaction.

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

### 3. Google Calendar Setup
You need OAuth 2.0 Client credentials to read from your calendar.
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Enable the **Google Calendar API**.
4. Go to **Credentials** -> **Create Credentials** -> **OAuth client ID**.
5. Choose "Desktop app" (or similar).
6. Download the resulting JSON file and save it as `credentials.json` directly inside the `ultron/` folder.
7. The first time you ask FRIDAY to check your calendar, a browser window will pop up asking for your authorization.

### 4. Optional LiveKit Setup
To move beyond the local microphone loop and into a room-based full-duplex setup, define:

```bash
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

The current desktop runtime detects these variables and is structured for LiveKit transport, while still falling back to local audio if room wiring is not yet enabled.

## Voice Model
On first run, FRIDAY will automatically download the Piper TTS voice model (~60MB) from HuggingFace. This is a one-time download. After that, everything runs 100% offline with no internet required.

To change the voice, edit VOICE_MODEL in voice.py and update MODEL_URL/CONFIG_URL to point to your preferred Piper voice from: https://huggingface.co/rhasspy/piper-voices

## Running FRIDAY
Once everything is set up, run:
```bash
python main.py
```

## Running The MCP Tool Server
To expose the FRIDAY tools as a standalone MCP server:

```bash
python mcp_server.py
```

## Architecture Notes
- `main.py` now owns the async orchestration loop and tool execution flow.
- `mcp_server.py` registers `web_research`, `mac_controller`, `schedule_handler`, and `vision_capture`.
- `brain.py` plans tool calls and synthesizes final spoken replies for Gemini.
- `memory_store.py` provides short-term semantic memory and long-term fact memory with ChromaDB, plus an in-memory fallback.
- `vision_agent.py` captures screenshots or webcam frames for multimodal prompts.
- `voice.py` strips markdown, links, and technical debris before speaking, and supports interruption for barge-in.
