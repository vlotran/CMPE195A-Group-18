/**
 * The theme values and the hook components use to read them
 * Kept apart from ThemeProvider (ThemeContext.jsx) so that file only exports a
 * component, which is what Vite's Fast Refresh needs to update it in place
 */

import { createContext, useContext } from "react";

export const DARK = "dark";
export const LIGHT = "light";

export const ThemeContext = createContext({
    theme: DARK,
    setTheme: () => {},
    toggleTheme: () => {},
});

export function useTheme() {
    return useContext(ThemeContext);
}
