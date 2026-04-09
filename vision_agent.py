import asyncio
import base64
import io
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageGrab


@dataclass
class VisionPayload:
    source: str
    image: Image.Image | None
    mime_type: str
    base64_data: str | None
    width: int
    height: int


class VisionAgent:
    def __init__(self) -> None:
        self._last_capture: VisionPayload | None = None

    def _capture_screen(self) -> VisionPayload:
        image = ImageGrab.grab()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        payload = VisionPayload(
            source="screen",
            image=image,
            mime_type="image/png",
            base64_data=encoded,
            width=image.width,
            height=image.height,
        )
        self._last_capture = payload
        return payload

    def _capture_webcam(self) -> VisionPayload:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV is required for webcam capture.") from exc

        camera = cv2.VideoCapture(0)
        ok, frame = camera.read()
        camera.release()
        if not ok:
            raise RuntimeError("Could not capture a webcam frame.")

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=92)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        payload = VisionPayload(
            source="webcam",
            image=image,
            mime_type="image/jpeg",
            base64_data=encoded,
            width=image.width,
            height=image.height,
        )
        self._last_capture = payload
        return payload

    async def capture(self, source: str = "screen") -> VisionPayload:
        normalized = source.lower().strip()
        if normalized == "webcam":
            return await asyncio.to_thread(self._capture_webcam)
        return await asyncio.to_thread(self._capture_screen)

    def latest(self) -> VisionPayload | None:
        return self._last_capture

    def as_tool_result(self, payload: VisionPayload) -> dict[str, Any]:
        return {
            "source": payload.source,
            "mime_type": payload.mime_type,
            "width": payload.width,
            "height": payload.height,
            "base64_data": payload.base64_data,
        }
