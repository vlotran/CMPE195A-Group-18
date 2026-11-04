/**
 * GlassBackground - the light that follows the cursor, behind frosted glass.
 *
 * Two layers behind the page content (styles/glassBackground.css):
 *  1. light: accent glow under the cursor + two slow floating orbs, across the whole screen
 *  2. pane:  frosted glass that only fills its parent (the dashboard's .app-shell widget)
 *
 * Only the --mx / --my variables move (once per frame), so React never re-renders.
 * Touch screens and "reduce motion" keep a still glow.
 *
 * Props:
 *  - soft: dimmer light, for pages with lots of content (the dashboard)
 *  - frosted: false for no glass at all: no pane, no blur, no orbs. Just the
 *    cursor light (the landing page).
 */
import { useEffect, useRef } from "react";
import "../styles/glassBackground.css";

function GlassBackground({ soft = false, frosted = true }) {
    const ref = useRef(null);

    useEffect(() => {
        const el = ref.current;
        const still = window.matchMedia("(hover: none), (prefers-reduced-motion: reduce)");
        if (!el || still.matches) return;

        let frame = 0;
        const onMove = (e) => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
                el.style.setProperty("--mx", `${e.clientX}px`);
                el.style.setProperty("--my", `${e.clientY}px`);
            });
        };
        window.addEventListener("pointermove", onMove);
        return () => {
            window.removeEventListener("pointermove", onMove);
            cancelAnimationFrame(frame);
        };
    }, []);

    return (
        <>
            <div
                ref={ref}
                className={`glass-bg ${soft ? "glass-bg--soft" : ""} ${frosted ? "" : "glass-bg--clear"}`}
                aria-hidden="true"
            >
                <div className="glass-bg-light" />
            </div>
            {frosted && <div className="glass-bg-pane" aria-hidden="true" />}
        </>
    );
}

export default GlassBackground;
