/**
 * Dashboard.jsx so that it can be used in both App.jsx and AppdDemo.jsx without duplication
 *
 * Displays sensor cards (Air Temperature, Air Humidity, Air Quality, Water pH)
 * and their historical charts. Air Quality comes from the BME680.
 * Extracted from App.jsx so each page has its own component
 */

import React from "react";
import SensorCard from "../components/SensorCard.jsx";
import SensorChart from "../components/SensorChart.jsx";
import ProfileIndicator from "../components/ProfileIndicator.jsx";
import CameraWidget from "../components/CameraWidget.jsx";
import AlertsButton from "../components/AlertsButton.jsx";   // NEW
import ActuatorControls from "../components/ActuatorControls.jsx";
import "../styles/dashboardEnter.css";   // NEW: fade-in / slide-up when the dashboard appears

// NEW props: profile (active threshold profile), onManageProfiles (opens Settings)
// NEW props: alertCount (unread warning/danger), onOpenAlerts (opens alert history)

function Dashboard({
    current,
    thresholds,
    charts,
    profile,
    onManageProfiles,
    alertCount,
    onOpenAlerts,
    actuatorState,
    actuatorError,
    actuatorBusy,
    onSetActuator,
    onSaveLightSchedule,
    onSetAutomatic,
}) {

    //"dashboard-enter" = fade-in / slide-up entrance (styles/dashboardEnter.css)
    return (
        <main className="dashboard dashboard-enter">
            {/* NEW: toolbar row: active profile on the left, alert history on the right */}
            <div className="dashboard-toolbar">
                <ProfileIndicator profile={profile} onManage={onManageProfiles} />
                {onOpenAlerts && <AlertsButton count={alertCount} onClick={onOpenAlerts} />}
            </div>

            <section className="camera-actuator-layout" aria-label="Camera and actuator controls">
                <CameraWidget />
                <ActuatorControls
                    state={actuatorState}
                    error={actuatorError}
                    busy={actuatorBusy}
                    onSetOutput={onSetActuator}
                    onSaveSchedule={onSaveLightSchedule}
                    onSetAutomatic={onSetAutomatic}
                />
            </section>

            {/* Sensor Cards */}
            <section className="card-grid">
                <SensorCard
                    title="Air Temperature"
                    metric="temperature"
                    value={current?.temperature ?? 0}
                    min={thresholds?.temperature?.min ?? 0}
                    max={thresholds?.temperature?.max ?? 0}
                />
                <SensorCard
                    title="Air Humidity"
                    metric="humidity"
                    value={current?.humidity ?? 0}
                    min={thresholds?.humidity?.min ?? 0}
                    max={thresholds?.humidity?.max ?? 0}
                />
                {/* Title shortened from "Air Quality Score": the full name wraps
                    to two lines on the 150px card and breaks the row alignment */}
                <SensorCard
                    title="Air Quality"
                    metric="aqi_score"
                    value={current?.aqi_score ?? 0}
                    min={thresholds?.aqi_score?.min ?? 0}
                    max={thresholds?.aqi_score?.max ?? 0}
                />
                <SensorCard
                    title="Water pH"
                    metric="ph"
                    value={current?.ph ?? 0}
                    min={thresholds?.ph?.min ?? 0}
                    max={thresholds?.ph?.max ?? 0}
                />
            </section>

            <section className="sensor-chart-grid" style={{ marginTop: "40px" }}>
                <SensorChart
                    title="Air Temperature Chart"
                    metric="temperature"
                    data={charts?.temperature?.data ?? []}
                    timestamps={charts?.temperature?.timestamps ?? []}
                />
                <SensorChart
                    title="Air Humidity Chart"
                    metric="humidity"
                    data={charts?.humidity?.data ?? []}
                    timestamps={charts?.humidity?.timestamps ?? []}
                />
                <SensorChart
                    title="Air Quality Chart"
                    metric="aqi_score"
                    data={charts?.aqi_score?.data ?? []}
                    timestamps={charts?.aqi_score?.timestamps ?? []}
                />
                <SensorChart
                    title="Water pH Chart"
                    metric="ph"
                    data={charts?.ph?.data ?? []}
                    timestamps={charts?.ph?.timestamps ?? []}
                />
            </section>
        </main>
    );
}

export default Dashboard;