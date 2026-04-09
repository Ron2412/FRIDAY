import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

from vision_agent import VisionAgent


try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    Request = Credentials = InstalledAppFlow = build = None

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None


SCOPES = ["https://www.googleapis.com/auth/calendar"]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class MCPToolServer:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path(__file__).parent
        self.vision = VisionAgent()
        self.tools: dict[str, ToolSpec] = {}
        self._fastmcp = FastMCP("friday") if FastMCP else None
        self._register_builtin_tools()

    def _register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        spec = ToolSpec(name=name, description=description, input_schema=input_schema, handler=handler)
        self.tools[name] = spec

        if self._fastmcp is not None:
            async def dynamic_tool(arguments: dict[str, Any]) -> dict[str, Any]:
                return await handler(arguments)

            dynamic_tool.__name__ = name
            dynamic_tool.__doc__ = description
            self._fastmcp.tool(name=name, description=description)(dynamic_tool)

    def _register_builtin_tools(self) -> None:
        self._register_tool(
            name="web_research",
            description="Search the web with DuckDuckGo and return concise result summaries.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            handler=self._web_research,
        )
        self._register_tool(
            name="mac_controller",
            description="Open apps, change system volume, or run safe shell tasks on macOS.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "target": {"type": "string"},
                    "value": {"type": "integer"},
                    "command": {"type": "string"},
                },
                "required": ["action"],
            },
            handler=self._mac_controller,
        )
        self._register_tool(
            name="schedule_handler",
            description="Read or write events in Google Calendar.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "calendar_id": {"type": "string", "default": "primary"},
                    "time_min": {"type": "string"},
                    "time_max": {"type": "string"},
                    "summary": {"type": "string"},
                    "description": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                },
                "required": ["action"],
            },
            handler=self._schedule_handler,
        )
        self._register_tool(
            name="vision_capture",
            description="Capture a screenshot or webcam frame for multimodal reasoning.",
            input_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "default": "screen"},
                },
            },
            handler=self._vision_capture,
        )

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self.tools.values()
        ]

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.tools:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            return await self.tools[name].handler(arguments)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _web_research(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if DDGS is None:
            return {"ok": False, "error": "ddgs is not installed."}

        query = arguments.get("query", "").strip()
        limit = int(arguments.get("max_results", 5))
        if not query:
            return {"ok": False, "error": "A search query is required."}

        def run_search() -> list[dict[str, Any]]:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=limit))
            return [
                {
                    "title": item.get("title"),
                    "snippet": item.get("body"),
                    "url": item.get("href"),
                }
                for item in results
            ]

        return {"ok": True, "query": query, "results": await asyncio.to_thread(run_search)}

    async def _mac_controller(self, arguments: dict[str, Any]) -> dict[str, Any]:
        action = str(arguments.get("action", "")).strip().lower()

        if action == "open_app":
            target = arguments.get("target")
            if not target:
                return {"ok": False, "error": "target is required for open_app."}
            process = await asyncio.create_subprocess_exec("open", "-a", str(target))
            await process.wait()
            return {"ok": process.returncode == 0, "action": action, "target": target}

        if action == "set_volume":
            value = max(0, min(int(arguments.get("value", 50)), 100))
            process = await asyncio.create_subprocess_exec(
                "osascript",
                "-e",
                f"set volume output volume {value}",
            )
            await process.wait()
            return {"ok": process.returncode == 0, "action": action, "value": value}

        if action == "run_command":
            command = str(arguments.get("command", "")).strip()
            if not command:
                return {"ok": False, "error": "command is required for run_command."}
            allowed_prefixes = ("pwd", "ls", "date", "whoami", "open ", "say ", "osascript ")
            if not command.startswith(allowed_prefixes):
                return {"ok": False, "error": "Command is outside the safe allow-list."}
            completed = await asyncio.to_thread(
                subprocess.run,
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.root_dir,
            )
            return {
                "ok": completed.returncode == 0,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "returncode": completed.returncode,
            }

        return {"ok": False, "error": f"Unsupported mac_controller action: {action}"}

    def _calendar_service(self):
        if not all([Request, Credentials, InstalledAppFlow, build]):
            raise RuntimeError("Google Calendar dependencies are not installed.")

        token_path = self.root_dir / "token.json"
        credentials_path = self.root_dir / "credentials.json"
        creds = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    raise RuntimeError("credentials.json not found for Google Calendar.")
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    async def _schedule_handler(self, arguments: dict[str, Any]) -> dict[str, Any]:
        action = str(arguments.get("action", "")).strip().lower()
        calendar_id = arguments.get("calendar_id", "primary")

        if action == "list_events":
            time_min = arguments.get("time_min") or datetime.utcnow().isoformat() + "Z"
            time_max = arguments.get("time_max") or (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

            def list_events() -> list[dict[str, Any]]:
                service = self._calendar_service()
                response = (
                    service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
                return response.get("items", [])

            items = await asyncio.to_thread(list_events)
            return {"ok": True, "events": items}

        if action == "create_event":
            required = ["summary", "start", "end"]
            missing = [field for field in required if not arguments.get(field)]
            if missing:
                return {"ok": False, "error": f"Missing fields: {', '.join(missing)}"}

            event_body = {
                "summary": arguments["summary"],
                "description": arguments.get("description", ""),
                "start": {"dateTime": arguments["start"]},
                "end": {"dateTime": arguments["end"]},
            }

            def create_event() -> dict[str, Any]:
                service = self._calendar_service()
                return service.events().insert(calendarId=calendar_id, body=event_body).execute()

            created = await asyncio.to_thread(create_event)
            return {"ok": True, "event": created}

        return {"ok": False, "error": f"Unsupported schedule_handler action: {action}"}

    async def _vision_capture(self, arguments: dict[str, Any]) -> dict[str, Any]:
        source = arguments.get("source", "screen")
        payload = await self.vision.capture(source=source)
        return {"ok": True, "capture": self.vision.as_tool_result(payload)}

    def mcp_app(self):
        return self._fastmcp

    def describe_tools_for_prompt(self) -> str:
        return json.dumps(self.list_tools(), indent=2)


if __name__ == "__main__":
    server = MCPToolServer(root_dir=Path(__file__).parent)
    app = server.mcp_app()
    if app is None:
        raise SystemExit("mcp is not installed. Add the MCP SDK to run the standalone tool server.")
    app.run()
