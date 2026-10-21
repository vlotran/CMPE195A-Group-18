/**
 * AlertsButton (NEW): opens the alert history panel.
 * Same look as "+ New Profile" / the profile indicator; a red badge shows how
 * many warning/danger alerts are still unread.
 *
 * Props:
 *  - count: unread warning + danger alerts
 *  - onClick(): open the panel
 */
import React from "react";
import "../styles/alertPanel.css";

function AlertsButton({ count = 0, onClick }) {
    const label = count > 0 ? `Alerts, ${count} unread` : "Alerts";
    return (
        <button type="button" className="alerts-btn" onClick={onClick} aria-label={label} title={label}>
            Alerts
            {count > 0 && (
                <span className="alerts-badge" aria-hidden="true">{count > 99 ? "99+" : count}</span>
            )}
        </button>
    );
}

export default AlertsButton;