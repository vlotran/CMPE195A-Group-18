/**
 * HeroImage - the landing page picture
 *
 * Hover: the same border beam as the member cards
 * Click: the picture grows from its spot on the page to fill the screen
 * Click outside it, or press Escape: it shrinks back to its spot
 *
 * The zoomed copy is rendered in document.body (createPortal) because the
 * picture's floating animation would otherwise stop it covering the whole screen
 * Styles are in LandingPage.css
 *
 * Props: src, alt
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal, flushSync } from "react-dom";

const ZOOM_MS = 350;   // zoom speed

function HeroImage({ src, alt }) {
    const [imageRatio, setImageRatio] = useState(null);   // width / height while zoomed, null when not
    const zoomed = imageRatio !== null;
    const frameRef = useRef(null);
    const thumbRef = useRef(null);
    const zoomRef = useRef(null);
    const zoomImgRef = useRef(null);
    const backdropRef = useRef(null);
    const animationsRef = useRef([]);  
    const closingRef = useRef(false);

    // Plays the zoom in or out: the big image is moved and scaled to sit exactly
    // over the small one, so it looks like the small one is growing.
    const playZoom = useCallback((direction) => {
        const small = thumbRef.current.getBoundingClientRect();
        const big = zoomImgRef.current.getBoundingClientRect();
        const atThumb =
            `translate(${small.left - big.left}px, ${small.top - big.top}px) scale(${small.width / big.width})`;

        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const timing = {
            duration: reduceMotion ? 0 : ZOOM_MS,
            easing: "cubic-bezier(0.22, 0.61, 0.36, 1)",
            fill: "both",
            direction,
        };
        animationsRef.current = [
            zoomImgRef.current.animate([{ transform: atThumb }, { transform: "none" }], timing),
            backdropRef.current.animate([{ opacity: 0 }, { opacity: 1 }], timing),
        ];
    }, []);

    const close = useCallback(() => {
        if (closingRef.current) return;
        closingRef.current = true;

        // Clicked while it was still opening: turn around from where it is
        const stillOpening = animationsRef.current.some((a) => a.playState === "running");
        if (stillOpening) animationsRef.current.forEach((a) => a.reverse());
        else playZoom("reverse");

        animationsRef.current[0].finished.then(() => {
            closingRef.current = false;
            // Show the picture again right away, because hidden elements can't take focus
            flushSync(() => setImageRatio(null));
            frameRef.current?.focus({ preventScroll: true });  
        });
    }, [playZoom]);

    // Starts the zoom in, before the browser paints the big image
    useLayoutEffect(() => {
        if (!zoomed) return;
        playZoom("normal");
        zoomRef.current.focus({ preventScroll: true });
    }, [zoomed, playZoom]);

    // Escape closes. 
    useEffect(() => {
        if (!zoomed) return;
        const onKey = (e) => {
            if (e.key === "Escape") close();
            if (e.key === "Tab") e.preventDefault();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [zoomed, close]);

    return (
        <>
            <button
                type="button"
                ref={frameRef}
                className={`landing-image-frame ${zoomed ? "zoomed" : ""}`}
                onClick={() => setImageRatio(thumbRef.current.naturalWidth / thumbRef.current.naturalHeight)}
                aria-label={`View full image: ${alt}`}
            >
                <span className="member-beam" aria-hidden="true" />
                <img ref={thumbRef} src={src} alt="" className="landing-image" />
            </button>

            {zoomed && createPortal(
                <div
                    ref={zoomRef}
                    className="image-zoom"
                    role="dialog"
                    aria-modal="true"
                    aria-label={alt}
                    tabIndex={-1}
                    onClick={close}
                >
                    <div ref={backdropRef} className="image-zoom-backdrop" />
                    {/* Clicks on the image itself don't close it */}
                    <img
                        ref={zoomImgRef}
                        src={src}
                        alt={alt}
                        className="image-zoom-img"
                        style={{ "--image-ratio": imageRatio }}
                        onClick={(e) => e.stopPropagation()}
                    />
                </div>,
                document.body
            )}
        </>
    );
}

export default HeroImage;
