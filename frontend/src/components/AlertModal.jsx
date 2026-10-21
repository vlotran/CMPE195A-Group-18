/**
 * Modal shown when any sensor enters DANGER.
 * CHANGED: "Close" marks the alerts as read on the backend (App.jsx), so they
 * don't come back after a reload or on another device.
 */
import React from "react";
import "../styles/alertModal.css";   
import { formatDateTime } from "../utils/time.js"; 
import { formatAlertMessage } from "../utils/alerts.js"; 

function AlertModal({ alerts, onClose }) {
    if (!alerts.length) return null;

    return (
        <div className="alert-modal-backdrop" onClick={onClose}>
            <div
                className="alert-modal"
                role="alertdialog"
                aria-labelledby="alert-modal-title"
                onClick={(e) => e.stopPropagation()}   // don't close on inner clicks
            >
                <h2 id="alert-modal-title" className="alert-modal-title">
                    Danger{alerts.length > 1 ? ` (${alerts.length})` : ""}
                </h2>

                <ul className="alert-modal-list">
                    {alerts.map((a) => (
                        <li key={a.id} className="alert-modal-item">
                            <p className="alert-modal-message">{formatAlertMessage(a.message)}</p>
                            <time className="alert-modal-time" dateTime={a.created_at}>
                                {formatDateTime(a.created_at)}
                            </time>
                        </li>
                    ))}
                </ul>

                <button className="alert-modal-close" onClick={onClose} autoFocus>
                    Close
                </button>
            </div>
        </div>
    );
}

export default AlertModal;