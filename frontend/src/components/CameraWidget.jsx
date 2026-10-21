import { useEffect, useState } from "react";
import { fetchCameraStatus, fetchCameraStreamToken } from "../services/api.js";
import "../styles/cameraWidget.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function CameraWidget() {
    const [status, setStatus] = useState("checking");
    const [streamUrl, setStreamUrl] = useState(null);

    useEffect(() => {
        let cancelled = false;

        const loadStream = async () => {
            try {
                const camera = await fetchCameraStatus();
                if (!camera.available) throw new Error("Camera unavailable");

                const stream = await fetchCameraStreamToken();
                if (!cancelled) {
                    setStreamUrl(`${API_BASE_URL}/api/camera/stream?token=${encodeURIComponent(stream.token)}`);
                    setStatus("ready");
                }
            } catch {
                if (!cancelled) {
                    setStreamUrl(null);
                    setStatus("unavailable");
                }
            }
        };

        loadStream();
        // Refresh the short-lived URL before its token expires.
        const refreshId = setInterval(loadStream, 8 * 60 * 1000);

        return () => {
            cancelled = true;
            clearInterval(refreshId);
        };
    }, []);

    const handleStreamError = () => {
        setStreamUrl(null);
        setStatus("unavailable");
    };

    return (
        <section className="camera-widget" aria-label="Live camera view">
            <div className="camera-widget-header">
                <h2>Live Camera</h2>
                <span className={`camera-status ${status}`}>
                    {status === "ready" ? "Online" : status === "checking" ? "Checking..." : "Unavailable"}
                </span>
            </div>

            {streamUrl ? (
                <img
                    className="camera-stream"
                    src={streamUrl}
                    alt="Live view of the hydroponic garden"
                    onError={handleStreamError}
                />
            ) : (
                <div className="camera-placeholder">
                    {status === "checking"
                        ? "Checking camera connection..."
                        : "Camera stream is unavailable."}
                </div>
            )}
        </section>
    );
}

export default CameraWidget;
