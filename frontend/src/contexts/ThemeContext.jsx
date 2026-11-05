/**
 * Dark / Light theme, shared across the app (same pattern as TempUnitContext)
 *
 * Sets <html data-theme="dark|light">. styles/theme.css defines the color
 * variables for each value, so every component re-colors automatically
 * Choice is saved in localStorage so it survives a refresh
 *
 * toggleTheme(event) reveals the new theme in a circle that spreads from the
 * click (View Transitions API). The rest of the circle's styles are in theme.css
 * Browsers without that API, and "reduce motion", switch instantly
 */

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

export const DARK = "dark";
export const LIGHT = "light";
const STORAGE_KEY = "theme";
const REVEAL_MS = 700;  
const ThemeContext = createContext({
    theme: DARK,
    setTheme: () => {},
    toggleTheme: () => {},
});

export function ThemeProvider({ children }) {
    const [theme, setTheme] = useState(() => {
        // read storage once on mount; default is dark
        let saved = DARK;
        try {
            saved = localStorage.getItem(STORAGE_KEY) === LIGHT ? LIGHT : DARK;
        } catch {
            // storage blocked - keep dark
        }
        // apply before first paint so a saved light theme doesn't flash dark
        document.documentElement.dataset.theme = saved;
        return saved;
    });

    // The theme we're heading to. A second quick click arrives before the first
    // one's change has run, so `theme` alone would still say the old value
    const targetRef = useRef(theme);

    useEffect(() => {
        targetRef.current = theme;
        document.documentElement.dataset.theme = theme;
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch {
            // non-fatal
        }
    }, [theme]);

    const toggleTheme = (event) => {
        const next = targetRef.current === DARK ? LIGHT : DARK;
        targetRef.current = next;
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        if (!document.startViewTransition || reduceMotion) {
            setTheme(next);
            return;
        }

        // The circle's center: the click, or the button's middle when it was pressed
        // with the keyboard (those clicks report position 0, 0)
        let x = window.innerWidth / 2;
        let y = window.innerHeight / 2;
        if (event?.detail > 0) {
            x = event.clientX;
            y = event.clientY;
        } else if (event?.currentTarget) {
            const box = event.currentTarget.getBoundingClientRect();
            x = box.left + box.width / 2;
            y = box.top + box.height / 2;
        }

        // The circle must end past the screen corner that's farthest from its center
        const radius = Math.hypot(
            Math.max(x, window.innerWidth - x),
            Math.max(y, window.innerHeight - y)
        );

        // The browser snapshots the old theme, runs this, then shows the new theme live.
        const transition = document.startViewTransition(() => {
            document.documentElement.dataset.theme = next;
            flushSync(() => setTheme(next));
        });

        transition.ready.then(() => {
            document.documentElement.animate(
                {
                    clipPath: [
                        `circle(0px at ${x}px ${y}px)`,
                        `circle(${radius}px at ${x}px ${y}px)`,
                    ],
                },
                {
                    duration: REVEAL_MS,
                    easing: "ease-in-out",
                    pseudoElement: "::view-transition-new(root)",
                }
            );
        }).catch(() => {
            // A quick second click cancels this reveal
        });
    };

    return (
        <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

// The hook lives next to its Provider on purpose
export function useTheme() {
    return useContext(ThemeContext);
}