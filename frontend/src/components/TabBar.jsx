/**
 * Tab switcher to switch between Dashboard, Settings, Appearance and Account
 * 
 * Props:
 *  - activeTab: "dashboard" | "settings" | "appearance" | "account"
 *  - onTabChange: function(tabName)
 */

import React from "react";
import "../styles/tabBar.css";

function TabBar({ activeTab, onTabChange }) {
    return (
        <nav className="tab-bar">
            {/* Dashboard Tab */}
            <button
                className={`tab-btn ${activeTab === "dashboard" ? "active" : ""}`}
                onClick={() => onTabChange("dashboard")}
            >
                Dashboard
            </button>

            {/* SettingsTab */}
            <button
                className={`tab-btn ${activeTab === "settings" ? "active" : ""}`}
                onClick={() => onTabChange("settings")}
            >
                Settings
            </button>

            {/* Appearance Tab - theme + temperature unit */}
            <button
                className={`tab-btn ${activeTab === "appearance" ? "active" : ""}`}
                onClick={() => onTabChange("appearance")}
            >
                Appearance
            </button>

            {/* NEW: Account Tab - name, email, password, delete account */}
            <button
                className={`tab-btn ${activeTab === "account" ? "active" : ""}`}
                onClick={() => onTabChange("account")}
            >
                Account
            </button>
        </nav>
    );
}

export default TabBar;
