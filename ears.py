import asyncio
import math
import os
import struct
import time
import wave
from threading import Event
from typing import Callable

import pyaudio
import whisper


print("[ FRIDAY ] Loading Whisper model (base)... This may take a moment on first run.")
try:
    _MODEL = whisper.load_model("base")
except Exception as exc:
    print(f"[Error] Failed to load Whisper model: {exc}")
    _MODEL = None


RATE = 16000
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
SILENCE_DURATION = 1.5
MIN_SPEECH_DURATION = 0.4
MAX_SPEECH_DURATION = 15.0


def get_rms(data: bytes) -> float:
    try:
        count = len(data) // 2
        samples = struct.unpack(f"{count}h", data)
        return math.sqrt(sum(sample * sample for sample in samples) / max(count, 1))
    except Exception:
        return 0.0


class AudioInput:
    def __init__(self) -> None:
        self.speech_threshold = 800.0
        self.silence_threshold = 500.0
        self._stop_flag = Event()

    def stop(self) -> None:
        self._stop_flag.set()

    def reset(self) -> None:
        self._stop_flag.clear()

    def _default_input_index(self, p: pyaudio.PyAudio) -> int | None:
        try:
            return p.get_default_input_device_info()["index"]
        except Exception:
            return None

    def _transcribe(self, frames: list[bytes]) -> str:
        if _MODEL is None or not frames:
            return ""

        temp_wav = "temp_audio.wav"
        try:
            p_tmp = pyaudio.PyAudio()
            sample_width = p_tmp.get_sample_size(FORMAT)
            p_tmp.terminate()

            with wave.open(temp_wav, "wb") as wav_file:
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(RATE)
                wav_file.writeframes(b"".join(frames))

            result = _MODEL.transcribe(temp_wav, fp16=False)
            return result["text"].strip()
        except Exception as exc:
            print(f"[Transcription Error] {exc}")
            return ""
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass

    def calibrate(self) -> None:
        print("[ FRIDAY ] Calibrating microphone... Please remain silent.")
        p = pyaudio.PyAudio()
        ambient_readings: list[float] = []
        stream = None

        try:
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=self._default_input_index(p),
                frames_per_buffer=CHUNK,
            )
            end_time = time.time() + 1.5
            while time.time() < end_time and not self._stop_flag.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                ambient_readings.append(get_rms(data))
        finally:
            if stream is not None:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            p.terminate()

        ambient_rms = sum(ambient_readings) / len(ambient_readings) if ambient_readings else 100.0
        if ambient_rms < 10:
            ambient_rms = 100.0
        self.speech_threshold = ambient_rms * 4.0
        self.silence_threshold = ambient_rms * 2.0
        print(
            f"[ FRIDAY ] Calibrated. Ambient: {ambient_rms:.0f}, "
            f"Speech threshold: {self.speech_threshold:.0f}"
        )

    async def calibrate_async(self) -> None:
        self.reset()
        await asyncio.to_thread(self.calibrate)

    def listen(
        self,
        on_audio_level: Callable[[float], None] | None = None,
        on_speech_start: Callable[[], None] | None = None,
    ) -> str:
        if _MODEL is None:
            return ""

        p = pyaudio.PyAudio()
        stream = None
        frames: list[bytes] = []
        pre_buffer: list[bytes] = []
        pre_buffer_size = int((RATE / CHUNK) * 0.4)
        recording = False
        silence_frames = 0
        speech_start_time: float | None = None

        try:
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=self._default_input_index(p),
                frames_per_buffer=CHUNK,
            )
            print("[ FRIDAY ] Ready...")

            while not self._stop_flag.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                rms = get_rms(data)

                if on_audio_level:
                    on_audio_level(min(1.0, rms / max(self.speech_threshold * 3.0, 1.0)))

                if not recording:
                    if rms > self.speech_threshold:
                        recording = True
                        speech_start_time = time.time()
                        frames.extend(pre_buffer)
                        frames.append(data)
                        silence_frames = 0
                        if on_speech_start:
                            on_speech_start()
                    else:
                        pre_buffer.append(data)
                        if len(pre_buffer) > pre_buffer_size:
                            pre_buffer.pop(0)
                    continue

                frames.append(data)
                if rms < self.silence_threshold:
                    silence_frames += 1
                else:
                    silence_frames = 0

                if silence_frames > int((RATE / CHUNK) * SILENCE_DURATION):
                    break

                if speech_start_time and time.time() - speech_start_time > MAX_SPEECH_DURATION:
                    break

        except Exception as exc:
            print(f"[Recording Error] {exc}")
            return ""
        finally:
            if on_audio_level:
                on_audio_level(0.0)
            if stream is not None:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            p.terminate()

        if not recording:
            return ""

        duration = len(frames) * CHUNK / RATE
        if duration < MIN_SPEECH_DURATION:
            return ""

        return self._transcribe(frames)

    async def listen_async(
        self,
        on_audio_level: Callable[[float], None] | None = None,
        on_speech_start: Callable[[], None] | None = None,
    ) -> str:
        self.reset()
        return await asyncio.to_thread(self.listen, on_audio_level, on_speech_start)
