"""Camera status and live-stream endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.src.camera import camera_manager
from backend.src.api.routes.auth import get_current_user

router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/status")
async def camera_status(user: dict = Depends(get_current_user)):
    """Report whether the Raspberry Pi camera service is available."""
    return {
        "available": camera_manager.available,
        "streaming": camera_manager.running,
        "resolution": {"width": 640, "height": 480},
        "frame_rate": 15,
    }


@router.post("/stream-token")
async def create_stream_token(user: dict = Depends(get_current_user)):
    """Issue a short-lived token for the browser's MJPEG image request."""
    return {
        "token": camera_manager.issue_stream_token(),
        "expires_in_seconds": 600,
    }


@router.get("/stream")
def camera_stream(token: str = Query(..., min_length=20)):
    """Return a shared MJPEG stream for the dashboard camera widget.

    The short-lived query token is used because an HTML <img> request cannot
    attach the frontend's Authorization header. The normal login token is
    never placed in the stream URL.
    """
    if not camera_manager.validate_stream_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired camera token")

    if not camera_manager.available:
        raise HTTPException(
            status_code=503,
            detail="Camera unavailable: install Picamera2 and connect a camera",
        )

    return StreamingResponse(
        camera_manager.frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
