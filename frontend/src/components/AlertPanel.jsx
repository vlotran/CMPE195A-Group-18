/**
 * AlertPanel: alert history in a side panel.
 *
 * Opened from the "Alerts" button on the Dashboard. Shows the newest alerts
 * (danger, warning, and recoveries back to normal), newest first, with a filter
 * and "Mark all as read". The DANGER popup (AlertModal) still handles urgent ones.
 *
 * Props:
 *  - open: boolean
 *  - onClose(): close the panel
 *  - onChanged(): called after alerts are marked read, so App can refresh the badge
 *
 * Data comes straight from the backend each time the panel opens:
 *   GET /api/alerts/?limit=50   and   PATCH /api/alerts/{id}/read
 */
import React, { useCallback, useEffect, useState } from "react";
import { getAlerts, markAlertRead } from "../services/api.js";
import { formatDateTime } from "../utils/time.js";
import { formatAlertMessage } from "../utils/alerts.js";
import "../styles/alertPanel.css";

const HISTORY_LIMIT = 50;

// Backend severity -> label + CSS modifier
const SEVERITY = {
    danger:  { label: "Danger",    cls: "danger" },
    warning: { label: "Warning",   cls: "warning" },
    normal:  { label: "Recovered", cls: "normal" },
};

const FILTERS = [
    { key: "all",     label: "All" },
    { key: "danger",  label: "Danger" },
    { key: "warning", label: "Warning" },
    { key: "normal",  label: "Recovered" },
];

function AlertPanel({ open, onClose, onChanged }) {
    const [alerts, setAlerts] = useState([]);
    const [filter, setFilter] = useState("all");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            setAlerts(await getAlerts({ limit: HISTORY_LIMIT }));
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    // Fresh list every time the panel opens
    useEffect(() => {
        if (open) load();
    }, [open, load]);

    // Escape closes the panel
    useEffect(() => {
        if (!open) return;
        const onKey = (e) => e.key === "Escape" && onClose();
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    if (!open) return null;

    const shown = filter === "all" ? alerts : alerts.filter((a) => a.severity === filter);
    const unread = alerts.filter((a) => !a.is_read);

    const markAllRead = async () => {
        // No bulk endpoint, so one PATCH per alert (at most HISTORY_LIMIT)
        await Promise.allSettled(unread.map((a) => markAlertRead(a.id)));
        await load();
        onChanged?.();
    };

    return (
        <div className="alert-panel-backdrop" onClick={onClose}>
            <aside
                className="alert-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby="alert-panel-title"
                onClick={(e) => e.stopPropagation()}
            >
                <header className="alert-panel-header">
                    <h2 id="alert-panel-title">Alerts</h2>
                    <button type="button" className="alert-panel-x" onClick={onClose} aria-label="Close alerts">
                        ×
                    </button>
                </header>

                <div className="alert-panel-toolbar">
                    <div className="alert-panel-filters" role="tablist" aria-label="Filter alerts">
                        {FILTERS.map((f) => (
                            <button
                                key={f.key}
                                type="button"
                                role="tab"
                                aria-selected={filter === f.key}
                                className={`alert-filter ${filter === f.key ? "active" : ""}`}
                                onClick={() => setFilter(f.key)}
                            >
                                {f.label}
                            </button>
                        ))}
                    </div>
                    <button
                        type="button"
                        className="alert-panel-markall"
                        onClick={markAllRead}
                        disabled={!unread.length}
                    >
                        Mark all as read
                    </button>
                </div>

                <div className="alert-panel-body">
                    {loading && !alerts.length && <p className="alert-panel-empty">Loading alerts…</p>}
                    {error && <p className="alert-panel-empty alert-panel-error">Couldn't load alerts: {error}</p>}
                    {!loading && !error && !shown.length && (
                        <p className="alert-panel-empty">
                            {filter === "all" ? "No alerts yet. All readings have stayed in range." : "No alerts of this type."}
                        </p>
                    )}

                    <ul className="alert-panel-list">
                        {shown.map((a) => {
                            const sev = SEVERITY[a.severity] ?? { label: a.severity, cls: "normal" };
                            return (
                                <li key={a.id} className={`alert-row ${a.is_read ? "" : "unread"}`}>
                                    <span className={`alert-sev ${sev.cls}`}>{sev.label}</span>
                                    <div className="alert-row-text">
                                        <p className="alert-row-message">{formatAlertMessage(a.message)}</p>
                                        <time className="alert-row-time" dateTime={a.created_at}>
                                            {formatDateTime(a.created_at)}
                                        </time>
                                    </div>
                                    {!a.is_read && <span className="alert-row-dot" title="Unread" />}
                                </li>
                            );
                        })}
                    </ul>
                </div>

                <footer className="alert-panel-footer">
                    Showing the latest {Math.min(alerts.length, HISTORY_LIMIT)} alerts
                </footer>
            </aside>
        </div>
    );
}

export default AlertPanel;