import { useState } from "react";
import "../styles/actuatorControls.css";

const ACTUATORS = [
    { id: "fan", label: "Fan" },
    { id: "humidifier", label: "Humidifier" },
];

function LightScheduleForm({
    state,
    hardwareEnabled,
    busy,
    onSetOutput,
    onSaveSchedule,
}) {
    const [start, setStart] = useState(state?.light_start || "");
    const [end, setEnd] = useState(state?.light_end || "");
    const [scheduleEnabled, setScheduleEnabled] = useState(
        Boolean(state?.light_schedule_enabled),
    );
    const growLightOn = Boolean(state?.grow_light_on);

    return (
        <div className="light-schedule">
            <div className="grow-light-heading">
                <strong>Grow light</strong>
                <span className={`actuator-state ${growLightOn ? "on" : ""}`}>
                    {growLightOn ? "ON" : "OFF"}
                </span>
                <div className="actuator-actions">
                    <button
                        type="button"
                        onClick={() => onSetOutput("grow_light", true)}
                        disabled={!hardwareEnabled || busy || growLightOn}
                    >
                        ON
                    </button>
                    <button
                        type="button"
                        onClick={() => onSetOutput("grow_light", false)}
                        disabled={!hardwareEnabled || busy || !growLightOn}
                    >
                        OFF
                    </button>
                </div>
            </div>
            <label>
                <input
                    type="checkbox"
                    checked={scheduleEnabled}
                    disabled={
                        !hardwareEnabled
                        || busy
                        || (!scheduleEnabled && (!start || !end))
                    }
                    onChange={(event) => {
                        const enabled = event.target.checked;
                        setScheduleEnabled(enabled);
                        onSaveSchedule({
                            enabled,
                            start: start || null,
                            end: end || null,
                        });
                    }}
                />
                Enable daily schedule
            </label>
            <label>
                Start
                <input
                    type="time"
                    value={start}
                    disabled={busy}
                    onChange={(event) => {
                        const nextStart = event.target.value;
                        const enabled = scheduleEnabled && Boolean(nextStart && end);
                        setStart(nextStart);
                        setScheduleEnabled(enabled);
                        onSaveSchedule({
                            enabled,
                            start: nextStart || null,
                            end: end || null,
                        });
                    }}
                />
            </label>
            <label>
                End
                <input
                    type="time"
                    value={end}
                    disabled={busy}
                    onChange={(event) => {
                        const nextEnd = event.target.value;
                        const enabled = scheduleEnabled && Boolean(start && nextEnd);
                        setEnd(nextEnd);
                        setScheduleEnabled(enabled);
                        onSaveSchedule({
                            enabled,
                            start: start || null,
                            end: nextEnd || null,
                        });
                    }}
                />
            </label>
        </div>
    );
}

function ActuatorControls({
    state,
    error,
    busy,
    onSetOutput,
    onSaveSchedule,
    onSetAutomatic,
}) {

    const hardwareEnabled = Boolean(state?.hardware_enabled);

    return (
        <section className="actuator-panel" aria-label="Shared Raspberry Pi controls">
            <div className="actuator-panel-heading">
                <h2>Controls</h2>
                {error && (
                    <span className="actuator-error" role="alert">
                        Controls are unavailable right now. Please try again later.
                    </span>
                )}
            </div>
            <div className="actuator-list">
                {ACTUATORS.map(({ id, label }) => {
                    const isOn = Boolean(state?.[`${id}_on`]);
                    return (
                        <div className="actuator-row" key={id}>
                            <div>
                                <strong>{label}</strong>
                            </div>
                            <span className={`actuator-state ${isOn ? "on" : ""}`}>
                                {isOn ? "ON" : "OFF"}
                            </span>
                            <div className="actuator-actions">
                                <button
                                    type="button"
                                    onClick={() => onSetOutput(id, true)}
                                    disabled={!hardwareEnabled || busy || isOn}
                                >
                                    ON
                                </button>
                                <button
                                    type="button"
                                    onClick={() => onSetOutput(id, false)}
                                    disabled={!hardwareEnabled || busy || !isOn}
                                >
                                    OFF
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>

            <LightScheduleForm
                key={`${state?.light_start || ""}|${state?.light_end || ""}|${Boolean(state?.light_schedule_enabled)}`}
                state={state}
                hardwareEnabled={hardwareEnabled}
                busy={busy}
                onSetOutput={onSetOutput}
                onSaveSchedule={onSaveSchedule}
            />

            <div className="automatic-control">
                <div>
                    <strong>Automatic temperature and humidity control</strong>
                </div>
                <button
                    type="button"
                    disabled={!state?.automatic_available || busy}
                    onClick={() => onSetAutomatic(!state?.automatic_enabled)}
                    title={state?.automatic_block_reason || ""}
                >
                    {state?.automatic_enabled ? "Disable automatic" : "Enable automatic"}
                </button>
            </div>

        </section>
    );
}

export default ActuatorControls;
