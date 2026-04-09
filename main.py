import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal

from gui import UltronGUI
from memory import Memory
import voice  # Load Piper first
import ears   # Load Whisper second
from brain import think
import calendar_tool
import memory_store
import fact_extractor
import chromadb


# ═══════════════════════════════════════════════════════════════════════════
#  UltronWorker — runs the assistant loop in a background QThread
# ═══════════════════════════════════════════════════════════════════════════
class UltronWorker(QThread):
    """Background thread that runs the ULTRON conversation loop."""

    # Signals for thread-safe GUI updates
    state_changed    = pyqtSignal(str)
    user_spoke       = pyqtSignal(str)
    ultron_responded = pyqtSignal(str)
    audio_level      = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def stop(self):
        """Request the worker to stop gracefully."""
        self._running = False

    def run(self):
        mem = Memory(capacity=30)

        # Calibrate RMS thresholds using ambient room noise
        ears.calibrate()

        # Report persistent memory stats
        count = memory_store.get_memory_count()
        print(f"[ FRIDAY ] Memory loaded. {count} past exchanges remembered.")

        self.state_changed.emit("speaking")
        if count == 0:
            voice.speak("Memory banks empty, boss. This is our first conversation.")
        else:
            voice.speak(f"Memory online. I remember {count} past exchanges, boss.")

        while self._running:
            try:
                # 1. Listen
                self.state_changed.emit("listening")
                
                # Blocks until speech completes -> mic is fully closed inside
                user_text = ears.listen(on_audio_level=self.audio_level.emit)

                if not self._running:
                    break

                if not user_text or len(user_text.strip()) < 2:
                    continue  # Ignore empty or microscopic clips

                print(f"[ YOU ] {user_text}")
                self.user_spoke.emit(user_text)

                # Memory-clear voice command
                if "clear your memory" in user_text.lower() or "forget everything" in user_text.lower():
                    client = chromadb.PersistentClient(path=str(memory_store.DB_PATH))
                    client.delete_collection("conversations")
                    client.delete_collection("user_facts")
                    response_text = "Memory wiped clean, boss. Starting fresh."
                    print(f"[ FRIDAY ] {response_text}")
                    self.ultron_responded.emit(response_text)
                    self.state_changed.emit("speaking")
                    voice.speak(response_text)
                    self.state_changed.emit("idle")
                    time.sleep(1.5)
                    continue

                if "shutdown friday" in user_text.lower() or "shutdown ultron" in user_text.lower():
                    self.state_changed.emit("speaking")
                    voice.speak("Shutting down. Take care, boss.")
                    self.ultron_responded.emit("Shutting down. Take care, boss.")
                    self._running = False
                    break

                # Extract and save any facts the user just shared
                facts = fact_extractor.extract_facts(user_text)
                for key, value in facts:
                    memory_store.save_fact(key, value)
                    print(f"[ FRIDAY ] Learned: {key} = {value}")

                # Retrieve semantically relevant past context
                from memory import get_relevant_context
                long_term_context = get_relevant_context(user_text)

                # 3. Calendar Check
                context = ""
                if any(w in user_text.lower() for w in ["calendar", "schedule", "today", "meeting"]):
                    self.state_changed.emit("thinking")
                    context = calendar_tool.get_today_events()

                # 4. Think 
                self.state_changed.emit("thinking")
                response_text = think(user_text, mem.get_history(), context=context, long_term_context=long_term_context)

                if not self._running:
                    break

                if not response_text or not response_text.strip():
                    print("[ WARN ] Got empty response after retries, skipping")
                    self.state_changed.emit("idle")
                    time.sleep(0.5)
                    continue


                mem.add_interaction("user", user_text)
                mem.add_interaction("assistant", response_text)
                from memory import persist_exchange
                persist_exchange(user_text, response_text)  # save to ChromaDB
                print(f"[ FRIDAY ] {response_text}")
                self.ultron_responded.emit(response_text)

                # 5. Speak (mic is NOT open)
                self.state_changed.emit("speaking")
                voice.speak(response_text)

                # 6. Cooldown
                self.state_changed.emit("idle")
                time.sleep(1.5)

            except Exception as e:
                print(f"[ Worker Error ] {e}")
                time.sleep(0.5)
                continue


# ═══════════════════════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = UltronGUI()
    worker = UltronWorker()

    worker.state_changed.connect(window.on_state_changed)
    worker.user_spoke.connect(window.on_user_spoke)
    worker.ultron_responded.connect(window.on_ultron_responded)
    worker.audio_level.connect(window.on_audio_level)

    window.set_worker(worker)
    window.show()
    worker.start()

    exit_code = app.exec()

    if worker.isRunning():
        worker.stop()
        worker.wait(5000)

    sys.exit(exit_code)
