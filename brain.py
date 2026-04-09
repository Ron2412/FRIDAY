import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

from memory_store import MemoryHit
from vision_agent import VisionPayload


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("[ ERROR ] GEMINI_API_KEY not found in .env file.")


@dataclass
class ToolCall:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainPlan:
    spoken_preface: str
    tool_calls: list[ToolCall]
    final_answer: str | None = None


class FridayBrain:
    def __init__(self) -> None:
        self._model = None

    def _ensure_model(self):
        if not API_KEY:
            raise RuntimeError("Missing GEMINI_API_KEY.")
        if self._model is None:
            self._model = genai.GenerativeModel(model_name=MODEL_NAME)
        return self._model

    @staticmethod
    def system_prompt() -> str:
        return (
            "You are FRIDAY, a high-agency multimodal personal assistant. "
            "You are witty, sharp, and polished, and you call the user boss. "
            "Be natural and concise, never use markdown, and keep speech-friendly phrasing. "
            "When tools are useful, choose them decisively. "
            "When visual context is available, use it. "
            "Avoid citations, bracketed notes, and raw URLs in spoken replies."
        )

    @staticmethod
    def _history_block(history: list[dict[str, str]]) -> str:
        if not history:
            return "No prior conversation."
        trimmed = history[-10:]
        return "\n".join(f"{item['role']}: {item['content']}" for item in trimmed)

    @staticmethod
    def _memory_block(memory_hits: list[MemoryHit]) -> str:
        if not memory_hits:
            return "No relevant memory."
        return "\n".join(f"- {hit.text}" for hit in memory_hits[:6])

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"[*#`_]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _generate_content(self, parts: list[Any]):
        model = self._ensure_model()
        return model.generate_content(parts)

    async def plan_turn(
        self,
        user_input: str,
        history: list[dict[str, str]],
        tool_catalog: list[dict[str, Any]],
        memory_hits: list[MemoryHit] | None = None,
        vision: VisionPayload | None = None,
    ) -> BrainPlan:
        today = datetime.now().strftime("%A, %B %d, %Y")
        planning_prompt = f"""
System:
{self.system_prompt()}

Today is {today}.

Available tools:
{json.dumps(tool_catalog, indent=2)}

Conversation history:
{self._history_block(history)}

Relevant memory:
{self._memory_block(memory_hits or [])}

Return strict JSON with this schema:
{{
  "spoken_preface": "brief voice-safe acknowledgement for the user",
  "tool_calls": [{{"tool": "tool_name", "arguments": {{}}}}],
  "final_answer": "optional direct answer when no tools are needed"
}}

Rules:
- Use tool_calls when fresh data, device actions, scheduling, or vision is needed.
- Keep spoken_preface under 14 words.
- If no tool is needed, return an empty tool_calls array and fill final_answer.
- Never wrap JSON in markdown.

User request:
{user_input}
""".strip()

        parts: list[Any] = [planning_prompt]
        if vision and vision.image is not None:
            parts.append(vision.image)

        response = await asyncio.to_thread(self._generate_content, parts)
        raw = getattr(response, "text", "") or ""

        try:
            payload = json.loads(raw.strip())
        except json.JSONDecodeError:
            payload = {"spoken_preface": "Working on it, boss.", "tool_calls": [], "final_answer": raw.strip()}

        tool_calls = [
            ToolCall(tool=item.get("tool", ""), arguments=item.get("arguments", {}) or {})
            for item in payload.get("tool_calls", [])
            if item.get("tool")
        ]
        final_answer = payload.get("final_answer")
        if final_answer:
            final_answer = self._clean_text(final_answer)

        return BrainPlan(
            spoken_preface=self._clean_text(payload.get("spoken_preface", "On it, boss.")),
            tool_calls=tool_calls,
            final_answer=final_answer,
        )

    async def respond(
        self,
        user_input: str,
        history: list[dict[str, str]],
        tool_results: list[dict[str, Any]],
        memory_hits: list[MemoryHit] | None = None,
        vision: VisionPayload | None = None,
    ) -> str:
        today = datetime.now().strftime("%A, %B %d, %Y")
        response_prompt = f"""
System:
{self.system_prompt()}

Today is {today}.

Conversation history:
{self._history_block(history)}

Relevant memory:
{self._memory_block(memory_hits or [])}

Tool results:
{json.dumps(tool_results, indent=2)}

User request:
{user_input}

Give a polished final answer in 1 to 3 sentences. Speak naturally, address the user as boss when it fits,
and summarize tool results clearly without markdown, citations, or URLs.
""".strip()

        parts: list[Any] = [response_prompt]
        if vision and vision.image is not None:
            parts.append(vision.image)

        response = await asyncio.to_thread(self._generate_content, parts)
        content = getattr(response, "text", "") or ""
        content = self._clean_text(content)
        return content or "Something went sideways on my end. Run that by me again, boss."
