import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from brain import FridayBrain
from ears import AudioInput
from gui import UltronGUI
from mcp_server import MCPToolServer
from memory_store import MemoryStore
from voice import SpeechEngine


load_dotenv()


class FridayWorker(QThread):
    state_changed = pyqtSignal(str)
    user_spoke = pyqtSignal(str)
    ultron_responded = pyqtSignal(str)
    audio_level = pyqtSignal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = True
        self.history: list[dict[str, str]] = []
        self.brain = FridayBrain()
        self.ears = AudioInput()
        self.voice = SpeechEngine()
        self.memory = MemoryStore(str(Path(__file__).parent / "memory_db"))
        self.tools = MCPToolServer(root_dir=Path(__file__).parent)
        self._livekit_enabled = bool(os.getenv("LIVEKIT_URL") and os.getenv("LIVEKIT_API_KEY"))
        self._loop: asyncio.AbstractEventLoop | None = None

    def stop(self) -> None:
        self._running = False
        self.ears.stop()

    def run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        self._loop = asyncio.get_running_loop()
        if not os.getenv("GEMINI_API_KEY"):
            warning = "Missing GEMINI_API_KEY in .env. Please add it and restart."
            self.ultron_responded.emit(warning)
            self.state_changed.emit("idle")
            return

        await self.memory.initialize_async()
        await self.ears.calibrate_async()

        greeting = "FRIDAY Mark 3 online. Ready when you are, boss."
        self.state_changed.emit("speaking")
        self.ultron_responded.emit(greeting)
        await self.voice.speak(greeting)
        self.state_changed.emit("idle")

        while self._running:
            try:
                await self._run_single_turn()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[ Worker Error ] {exc}")
                self.state_changed.emit("idle")
                await asyncio.sleep(0.5)

        await self.voice.stop()

    async def _run_single_turn(self) -> None:
        if self._livekit_enabled:
            self.state_changed.emit("thinking")
            status = (
                "LiveKit credentials detected, boss, but this desktop build is using the "
                "local audio fallback until the room transport is configured."
            )
            self.ultron_responded.emit(status)
            await self.voice.speak(status)
            self._livekit_enabled = False
            self.state_changed.emit("idle")
            return

        def on_speech_start() -> None:
            if self._loop is None:
                return
            self._loop.call_soon_threadsafe(asyncio.create_task, self.voice.stop())

        self.state_changed.emit("listening")
        user_text = await self.ears.listen_async(
            on_audio_level=self.audio_level.emit,
            on_speech_start=on_speech_start,
        )

        if not self._running or not user_text or len(user_text.strip()) < 2:
            self.state_changed.emit("idle")
            return

        self.user_spoke.emit(user_text)
        text_lower = user_text.lower()
        if "shutdown friday" in text_lower or "exit assistant" in text_lower:
            goodbye = "Shutting down. Take care, boss."
            self.state_changed.emit("speaking")
            self.ultron_responded.emit(goodbye)
            await self.voice.speak(goodbye)
            self._running = False
            return

        self.state_changed.emit("thinking")
        memory_hits = await self.memory.recall_async(user_text)
        latest_vision = self.tools.vision.latest()
        plan = await self.brain.plan_turn(
            user_input=user_text,
            history=self.history,
            tool_catalog=self.tools.list_tools(),
            memory_hits=memory_hits,
            vision=latest_vision,
        )

        if plan.tool_calls and plan.spoken_preface:
            self.state_changed.emit("speaking")
            self.ultron_responded.emit(plan.spoken_preface)
            await self.voice.speak(plan.spoken_preface)
            self.state_changed.emit("thinking")

        tool_results: list[dict[str, object]] = []
        for call in plan.tool_calls:
            result = await self.tools.execute_tool(call.tool, call.arguments)
            tool_results.append({"tool": call.tool, "arguments": call.arguments, "result": result})
            await self.memory.remember_short_term_async(
                f"Tool {call.tool} called with {call.arguments} and returned {result}",
                metadata={"kind": "tool_result"},
            )
            if call.tool == "vision_capture" and result.get("ok"):
                latest_vision = self.tools.vision.latest()

        if tool_results:
            final_text = await self.brain.respond(
                user_input=user_text,
                history=self.history,
                tool_results=tool_results,
                memory_hits=memory_hits,
                vision=latest_vision,
            )
        else:
            final_text = plan.final_answer or "I need another pass at that, boss."

        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": final_text})
        self.history = self.history[-12:]

        await self.memory.remember_short_term_async(
            f"User said: {user_text}\nAssistant replied: {final_text}",
            metadata={"kind": "conversation"},
        )
        if any(token in text_lower for token in ["remember", "favorite", "prefer", "my name is", "i like"]):
            await self.memory.remember_long_term_async(
                user_text,
                metadata={"kind": "user_fact"},
            )

        self.ultron_responded.emit(final_text)
        self.state_changed.emit("speaking")
        await self.voice.speak(final_text)
        self.state_changed.emit("idle")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = UltronGUI()
    worker = FridayWorker()

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
