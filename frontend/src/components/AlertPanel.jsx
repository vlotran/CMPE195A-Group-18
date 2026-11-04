/**
 * AlertPanel: alert history in a side panel.
 *
 * Opened from the "Alerts" button on the Dashboard. Shows the newest alerts
 * (danger, warning, and recoveries back to normal), newest first, with a filter
 * dropdown, "Mark all as read" and "Clear all". Hovering a row shows Read / Delete.
 * The DANGER popup (AlertModal) still handles urgent ones.
 *
 * Props:
 *  - open: boolean
 *  - onClose(): close the panel
 *  - onChanged(): called after alerts are read or deleted, so App can refresh the badge
 *
 * Data comes straight from the backend each time the panel opens:
 *   GET /api/alerts/?limit=50, PATCH /api/alerts/{id}/read,
 *   PATCH /api/alerts/{id}/dismiss and PATCH /api/alerts/dismiss
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { dismissAlert, dismissAlerts, getAlerts, markAlertRead } from "../services/api.js";
import { formatDateTime } from "../utils/time.js";
import { formatAlertMessage } from "../utils/alerts.js";
import ConfirmDialog from "./ConfirmDialog.jsx";
import closeIcon from "../assets/icons/close.png"; 
import downArrowIcon from "../assets/icons/down-arrow.png"; 
import "../styles/profileIndicator.css";
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
    const [actionError, setActionError] = useState(null);   // a read/delete/clear that failed
    const [menuOpen, setMenuOpen] = useState(false);        // filter dropdown
    const [confirmClear, setConfirmClear] = useState(false); // "Clear all" dialog
    const filterRef = useRef(null);

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
        if (!open) return;
        setActionError(null);
        setMenuOpen(false);
        setConfirmClear(false);
        load();
    }, [open, load]);

    // Escape closes whatever is on top: the dialog, then the dropdown, then the panel
    useEffect(() => {
        if (!open) return;
        const onKey = (e) => {
            if (e.key !== "Escape") return;
            if (confirmClear) setConfirmClear(false);
            else if (menuOpen) setMenuOpen(false);
            else onClose();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose, confirmClear, menuOpen]);

    // clicking anywhere outside the dropdown closes it
    useEffect(() => {
        if (!menuOpen) return;
        const onPointerDown = (e) => {
            if (!filterRef.current?.contains(e.target)) setMenuOpen(false);
        };
        document.addEventListener("pointerdown", onPointerDown);
        return () => document.removeEventListener("pointerdown", onPointerDown);
    }, [menuOpen]);

    if (!open) return null;

    const shown = filter === "all" ? alerts : alerts.filter((a) => a.severity === filter);
    const unread = alerts.filter((a) => !a.is_read);
    const filterLabel = FILTERS.find((f) => f.key === filter).label;
    const clearLabel = filter === "all" ? "Clear all" : `Clear ${filterLabel}`;

    // run a read/delete/clear, then refresh the list and the badge
    const applyChange = async (change) => {
        setActionError(null);
        try {
            await change();
        } catch (e) {
            setActionError(e.message);
        }
        await load();
        onChanged?.();
    };

    const markAllRead = () =>
        // No bulk endpoint, so one PATCH per alert (at most HISTORY_LIMIT)
        applyChange(() => Promise.allSettled(unread.map((a) => markAlertRead(a.id))));

    // follows the dropdown, and also covers older alerts past HISTORY_LIMIT,
    // so they don't appear in the list after the clear
    const clearShown = () => {
        setConfirmClear(false);
        applyChange(() =>
            dismissAlerts({
                severity: filter === "all" ? undefined : filter,
                maxId: Math.max(...alerts.map((a) => a.id)),
            })
        );
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
                    {/* CHANGED: close.png as a mask, same as the login / signup close button */}
                    <button type="button" className="alert-panel-x" onClick={onClose} aria-label="Close alerts">
                        <span
                            className="alert-panel-x-icon"
                            style={{ "--icon": `url(${closeIcon})` }}
                            aria-hidden="true"
                        />
                    </button>
                </header>

                <div className="alert-panel-toolbar">
                    {/*filter is a dropdown, using the profile indicator's button + arrow */}
                    <div className="alert-filter-menu" ref={filterRef}>
                        <button
                            type="button"
                            className={`profile-indicator-btn ${menuOpen ? "open" : ""}`}
                            onClick={() => setMenuOpen((o) => !o)}
                            aria-expanded={menuOpen}
                            aria-controls="alert-filter-options"
                        >
                            <span className="profile-indicator-label">Filter:</span>
                            <span className="profile-indicator-name">{filterLabel}</span>
                            <span
                                className="profile-indicator-caret"
                                style={{ "--icon": `url(${downArrowIcon})` }}
                                aria-hidden="true"
                            />
                        </button>

                        {menuOpen && (
                            <div id="alert-filter-options" className="alert-filter-options">
                                {FILTERS.map((f) => (
                                    <button
                                        key={f.key}
                                        type="button"
                                        aria-pressed={filter === f.key}
                                        className={`alert-filter-option ${filter === f.key ? "active" : ""}`}
                                        onClick={() => {
                                            setFilter(f.key);
                                            setMenuOpen(false);
                                        }}
                                    >
                                        {f.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="alert-panel-actions">
                        <button
                            type="button"
                            className="alert-panel-markall"
                            onClick={markAllRead}
                            disabled={!unread.length}
                        >
                            Mark all as read
                        </button>
                        {/* NEW: asks first, because it removes the whole list */}
                        <button
                            type="button"
                            className="alert-panel-clear"
                            onClick={() => setConfirmClear(true)}
                            disabled={!shown.length}
                        >
                            {clearLabel}
                        </button>
                    </div>
                </div>

                <div className="alert-panel-body">
                    {loading && !alerts.length && <p className="alert-panel-empty">Loading alerts…</p>}
                    {error && <p className="alert-panel-empty alert-panel-error">Couldn't load alerts: {error}</p>}
                    {actionError && (
                        <p className="alert-panel-empty alert-panel-error" role="alert">
                            Couldn't update alerts: {actionError}
                        </p>
                    )}
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

                                    {/* NEW: slides in from the right on hover or keyboard focus.
                                        Read only shows on unread alerts. */}
                                    <div className="alert-row-actions">
                                        {!a.is_read && (
                                            <button
                                                type="button"
                                                className="alert-row-btn"
                                                onClick={() => applyChange(() => markAlertRead(a.id))}
                                                aria-label={`Mark as read: ${formatAlertMessage(a.message)}`}
                                            >
                                                Read
                                            </button>
                                        )}
                                        <button
                                            type="button"
                                            className="alert-row-btn delete"
                                            onClick={() => applyChange(() => dismissAlert(a.id))}
                                            aria-label={`Delete: ${formatAlertMessage(a.message)}`}
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                </div>

                <footer className="alert-panel-footer">
                    Showing the latest {Math.min(alerts.length, HISTORY_LIMIT)} alerts
                </footer>
            </aside>

            {/* inside the backdrop so it sits above the panel.
                stopPropagation: clicking the dialog's overlay must not close the panel too */}
            {confirmClear && (
                <div onClick={(e) => e.stopPropagation()}>
                    <ConfirmDialog
                        title={filter === "all" ? "Clear all alerts?" : `Clear all ${filterLabel} alerts?`}
                        message={
                            filter === "all"
                                ? "Every alert will be removed from your list."
                                : `Every ${filterLabel} alert will be removed from your list. Other alerts stay.`
                        }
                        confirmLabel="Clear"
                        onConfirm={clearShown}
                        onCancel={() => setConfirmClear(false)}
                    />
                </div>
            )}
        </div>
    );
}

export default AlertPanel;