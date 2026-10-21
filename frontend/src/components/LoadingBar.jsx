import { useEffect, useRef, useState } from "react";
import "../styles/loadingBar.css";

const MIN_VISIBLE_MS = 400;

// Indeterminate glowing bar pinned to the top of the page.
// `active` = true while the dashboard is (re)loading.
export default function LoadingBar({ active }) {
    const [visible, setVisible] = useState(active);
    const shownAt = useRef(0);

    useEffect(() => {
        if (active) {
        shownAt.current = Date.now();
        setVisible(true);
        return;
        }
        // Wait out the remaining minimum display time before fading out
        const remaining = MIN_VISIBLE_MS - (Date.now() - shownAt.current);
        const hide = setTimeout(() => setVisible(false), Math.max(0, remaining));
        return () => clearTimeout(hide);
    }, [active]);

    return (
        <div
        className={`loading-bar ${visible ? "is-visible" : ""}`}
        role="progressbar"
        aria-busy={visible}
        aria-hidden={!visible}
        aria-label="Loading dashboard"
        >
        <div className="loading-bar__fill" />
        </div>
    );
}