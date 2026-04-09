import whisper
import pyaudio
import wave
import time
import os
import struct
import math

# Load the base model once when module is imported
print("[ FRIDAY ] Loading Whisper model (base)... This may take a moment on first run.")
try:
    model = whisper.load_model("base")
except Exception as e:
    print(f"[Error] Failed to load Whisper model: {e}")
    model = None

# Audio Configuration
RATE = 16000
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

# Timing Constants
SILENCE_DURATION = 1.5       # seconds of silence to stop recording
MIN_SPEECH_DURATION = 0.4    # ignore clips shorter than this
MAX_SPEECH_DURATION = 15.0   # max length of a single recording

# Dynamic Thresholds (Updated by calibrate)
SILENCE_THRESHOLD = 500
SPEECH_THRESHOLD = 800

def get_rms(data):
    """Calculate Root Mean Square (RMS) energy of an audio chunk."""
    try:
        count = len(data) // 2
        samples = struct.unpack(f'{count}h', data)
        rms = math.sqrt(sum(s * s for s in samples) / count)
        return rms
    except Exception:
        return 0.0

def calibrate():
    """Records ambient noise for 1.5 seconds and sets baseline RMS thresholds."""
    global SPEECH_THRESHOLD, SILENCE_THRESHOLD
    print("[ FRIDAY ] Calibrating microphone... Please remain silent.")
    
    p = pyaudio.PyAudio()
    try:
        dev_info = p.get_default_input_device_info()
        dev_index = dev_info['index']
    except Exception:
        dev_index = None

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=dev_index,
                    frames_per_buffer=CHUNK)
    
    ambient_readings = []
    end_time = time.time() + 1.5
    try:
        while time.time() < end_time:
            data = stream.read(CHUNK, exception_on_overflow=False)
            ambient_readings.append(get_rms(data))
    except Exception as e:
        print(f"[Calibration Error] {e}")
    finally:
        if stream.is_active():
            stream.stop_stream()
        stream.close()
        p.terminate()

    if ambient_readings:
        ambient_rms = sum(ambient_readings) / len(ambient_readings)
        # Fallback to defaults if perfectly silent
        if ambient_rms < 10: 
            ambient_rms = 100
        SPEECH_THRESHOLD = ambient_rms * 4.0
        SILENCE_THRESHOLD = ambient_rms * 2.0
    
    print(f"[ FRIDAY ] Calibrated. Ambient: {ambient_rms:.0f}, Speech threshold: {SPEECH_THRESHOLD:.0f}")

def listen(on_audio_level=None) -> str:
    """
    Opens PyAudio stream, blocks until speech is detected, records until silence,
    closes stream, transcribes, and returns the text.
    Returns "" if aborted or noise.
    """
    if model is None:
        return ""

    p = pyaudio.PyAudio()
    try:
        dev_info = p.get_default_input_device_info()
        dev_index = dev_info['index']
    except Exception:
        dev_index = None

    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=dev_index,
                        frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"[Microphone Error] Could not open PyAudio stream: {e}")
        p.terminate()
        return ""

    print("[ FRIDAY ] Ready...")
    
    frames = []
    recording = False
    silence_frames = 0
    speech_start_time = None
    
    # Pre-record buffer to avoid cutting off first split second of sound
    pre_buffer = []
    pre_buffer_size = int((RATE / CHUNK) * 0.4) # 400ms

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = get_rms(data)
            
            # Send float 0.0 - 1.0 to GUI (scaled for visibility)
            if on_audio_level:
                # Map typical RMS ranges into 0.0-1.0 visually
                disp_val = min(1.0, rms / (SPEECH_THRESHOLD * 3.0))
                on_audio_level(disp_val)

            if not recording:
                if rms > SPEECH_THRESHOLD:
                    print("[ FRIDAY ] Hearing you...")
                    recording = True
                    speech_start_time = time.time()
                    frames.extend(pre_buffer)
                    frames.append(data)
                    silence_frames = 0
                else:
                    pre_buffer.append(data)
                    if len(pre_buffer) > pre_buffer_size:
                        pre_buffer.pop(0)
            else:
                frames.append(data)
                
                # Check for silence block
                if rms < SILENCE_THRESHOLD:
                    silence_frames += 1
                else:
                    silence_frames = 0
                
                # Exit condition: sustained silence
                if silence_frames > int((RATE / CHUNK) * SILENCE_DURATION):
                    break
                
                # Hard limit duration
                if time.time() - speech_start_time > MAX_SPEECH_DURATION:
                    break

    except Exception as e:
        print(f"[Recording Error] {e}")
        return ""
    finally:
        # Zero out GUI amplitude before deep closing
        if on_audio_level:
            on_audio_level(0.0)
            
        try:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
        except:
            pass
        p.terminate()

    if not recording:
        return ""

    # Ensure recording met minimum time requirement
    duration = len(frames) * CHUNK / RATE
    if duration < MIN_SPEECH_DURATION:
        # Detected as noise/click
        return ""
        
    temp_wav = "temp_audio.wav"
    try:
        p_tmp = pyaudio.PyAudio()
        sample_width = p_tmp.get_sample_size(FORMAT)
        p_tmp.terminate()
        
        with wave.open(temp_wav, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(sample_width)
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            
        result = model.transcribe(temp_wav, fp16=False)
        text = result["text"].strip()
        return text
    except Exception as e:
        print(f"[Transcription Error] {e}")
        return ""
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass
