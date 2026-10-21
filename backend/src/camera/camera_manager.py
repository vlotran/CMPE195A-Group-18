"""Small Raspberry Pi camera service used by the dashboard.

Picamera2 is imported lazily so the backend can still run with mock sensors on
development machines that do not have a Raspberry Pi camera attached.
"""

from __future__ import annotations

import secrets
import time
from threading import Condition, Lock

try:  # Raspberry Pi only; deliberately optional for local development.
    from picamera2 import Picamera2
    from picamera2.encoders import JpegEncoder
    from picamera2.outputs import FileOutput
except ImportError:  # pragma: no cover - exercised only off the Pi
    Picamera2 = None
    JpegEncoder = None
    FileOutput = None


class StreamingOutput:
    """Receives JPEG frames from Picamera2 and makes them available to clients."""

    def __init__(self) -> None:
        self.condition = Condition()
        self.frame: bytes | None = None

    def write(self, buf: bytes) -> int:
        # JpegEncoder writes one complete JPEG frame at a time.
        if buf.startswith(b"\xff\xd8"):
            with self.condition:
                self.frame = buf
                self.condition.notify_all()
        return len(buf)

    def frames(self):
        """Yield frames in multipart format until the client disconnects."""
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.frame is not None)
                frame = self.frame

            if frame is None:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: "
                + str(len(frame)).encode("ascii")
                + b"\r\n\r\n"
                + frame
                + b"\r\n"
            )


class CameraManager:
    """Owns one shared camera stream for all dashboard viewers."""

    def __init__(self) -> None:
        self._camera = None
        self._output: StreamingOutput | None = None
        self._started = False
        self._stream_tokens: dict[str, float] = {}
        self._lifecycle_lock = Lock()

    @property
    def available(self) -> bool:
        return Picamera2 is not None

    @property
    def running(self) -> bool:
        return self._started

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._started or not self.available:
                return

            camera = Picamera2()
            output = StreamingOutput()
            try:
                configuration = camera.create_video_configuration(
                    main={"size": (640, 480), "format": "RGB888"},
                    controls={"FrameRate": 15},
                )
                camera.configure(configuration)
                camera.start_recording(JpegEncoder(q=80), FileOutput(output))
            except Exception:
                try:
                    camera.close()
                except Exception:
                    pass
                raise

            self._camera = camera
            self._output = output
            self._started = True

    def stop(self) -> None:
        with self._lifecycle_lock:
            if not self._started:
                return

            camera = self._camera
            try:
                camera.stop_recording()
            finally:
                try:
                    camera.close()
                finally:
                    self._camera = None
                    self._output = None
                    self._started = False

    def issue_stream_token(self, lifetime_seconds: int = 600) -> str:
        """Create a short-lived token suitable for an image-stream URL."""
        now = time.monotonic()
        self._stream_tokens = {
            token: expiry
            for token, expiry in self._stream_tokens.items()
            if expiry > now
        }
        token = secrets.token_urlsafe(32)
        self._stream_tokens[token] = now + lifetime_seconds
        return token

    def validate_stream_token(self, token: str) -> bool:
        expiry = self._stream_tokens.get(token)
        if expiry is None:
            return False
        if expiry <= time.monotonic():
            self._stream_tokens.pop(token, None)
            return False
        return True

    def frames(self):
        if not self.available:
            raise RuntimeError("Picamera2 is not installed on this system")

        self.start()
        if self._output is None:
            raise RuntimeError("Camera stream could not be initialized")

        yield from self._output.frames()


camera_manager = CameraManager()
