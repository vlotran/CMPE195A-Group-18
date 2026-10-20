/**
 * ProfileIndicator
 *
 * Shows which threshold profile the dashboard is using. Sits above the sensor cards.
 *  - Collapsed (default): a button with the profile name
 *  - Click: expands to show every threshold in the profile; click again to collapse
 * Button styling matches "+ New Profile" on the Settings page (default / hover / pressed).
 *
 * Props:
 *  - profile: the active configuration from the backend
 *      {name, description, ph_min, ph_max, temp_min, temp_max, humidity_min, humidity_max,
 *       pressure_min, pressure_max, aqi_min, aqi_max}  (null = no active profile)
 *  - onManage(): optional, opens the Settings tab ("Change profile" link)
 */
import React, { useState } from "react";
import { useTempUnit } from "../contexts/TempUnitContext.jsx";
import { formatTempRange } from "../utils/units.js";
import "../styles/profileIndicator.css";

// "--" when a value is missing (e.g. an older backend without the BME680 fields)
const range = (lo, hi, unit = "") =>
    lo == null || hi == null ? "--" : `${lo} – ${hi}${unit}`;

function ProfileIndicator({ profile, onManage }) {
    const [isOpen, setIsOpen] = useState(false);
    const { tempUnit } = useTempUnit();

    if (!profile) {
        return (
            <div className="profile-indicator">
                <span className="profile-indicator-empty">No active profile</span>
            </div>
        );
    }

    // Temperature is stored in °C; show it in the unit chosen on the Appearance page
    const items = [
        { key: "ph", label: "pH", value: range(profile.ph_min, profile.ph_max) },
        {
            key: "temp", label: "Temperature",
            value: profile.temp_min == null ? "--"
                : formatTempRange(profile.temp_min, profile.temp_max, tempUnit),
        },
        { key: "hum", label: "Humidity", value: range(profile.humidity_min, profile.humidity_max, " %") },
        { key: "pressure", label: "Air Pressure", value: range(profile.pressure_min, profile.pressure_max, " hPa") },
        { key: "aqi", label: "Air Quality",   /* same as the card title; "Score" wrapped on phones */ value: range(profile.aqi_min, profile.aqi_max) },
    ];

    return (
        <div className="profile-indicator">
            <button
                type="button"
                className={`profile-indicator-btn ${isOpen ? "open" : ""}`}
                onClick={() => setIsOpen((o) => !o)}
                aria-expanded={isOpen}
                aria-controls="profile-indicator-details"
                title={isOpen ? "Hide thresholds" : "Show thresholds"}
            >
                <span className="profile-indicator-label">Profile:</span>
                <span className="profile-indicator-name">{profile.name}</span>
                <span className="profile-indicator-caret" aria-hidden="true">▾</span>
            </button>

            {isOpen && (
                <div id="profile-indicator-details" className="profile-indicator-panel">
                    {profile.description && (
                        <p className="profile-indicator-desc">{profile.description}</p>
                    )}

                    <div className="profile-indicator-grid">
                        {items.map((item) => (
                            <div key={item.key} className="profile-indicator-item">
                                <div className="profile-indicator-item-label">{item.label}</div>
                                <div className="profile-indicator-item-value">{item.value}</div>
                            </div>
                        ))}
                    </div>

                    {onManage && (
                        <button type="button" className="profile-indicator-manage" onClick={onManage}>
                            Change profile in Settings →
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}

export default ProfileIndicator;
