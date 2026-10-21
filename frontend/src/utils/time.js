/**
 * Backend timestamps are UTC but arrive WITHOUT a time zone marker
 * parseUtc marks them as UTC first. Same idea as parseUtc in SensorChart.jsx.
 */
export function parseUtc(ts) {
    if (!ts) return null;
    const iso = String(ts).trim().replace(" ", "T");
    const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso);   
    return new Date(hasZone ? iso : `${iso}Z`);
}

// Same zone the charts use, so every time on the dashboard matches
export const DISPLAY_TIME_ZONE = "America/Los_Angeles";

export function formatDateTime(ts) {
    const d = parseUtc(ts);
    if (!d || Number.isNaN(d.getTime())) return "";
    return d.toLocaleString("en-US", {
        timeZone: DISPLAY_TIME_ZONE,
        month: "short", day: "numeric",
        hour: "numeric", minute: "2-digit",
    });
}