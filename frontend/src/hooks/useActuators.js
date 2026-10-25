import { useCallback, useEffect, useState } from "react";
import {
    fetchActuatorState,
    saveLightSchedule,
    setAutomaticControl,
    setActuatorState,
} from "../services/api.js";

export default function useActuators() {
    const [state, setState] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    const refresh = useCallback(async () => {
        try {
            const nextState = await fetchActuatorState();
            setState(nextState);
            setError("");
        } catch (err) {
            setError(err.message);
        }
    }, []);

    useEffect(() => {
        refresh();
        const intervalId = setInterval(refresh, 5000);
        return () => clearInterval(intervalId);
    }, [refresh]);

    const runAction = useCallback(async (action) => {
        setBusy(true);
        setError("");
        try {
            const nextState = await action();
            setState(nextState);
            return true;
        } catch (err) {
            setError(err.message);
            return false;
        } finally {
            setBusy(false);
        }
    }, []);

    const setOutput = useCallback(
        (actuator, on) => runAction(() => setActuatorState(actuator, on)),
        [runAction],
    );
    const updateLightSchedule = useCallback(
        (schedule) => runAction(() => saveLightSchedule(schedule)),
        [runAction],
    );
    const setAutomatic = useCallback(
        (enabled) => runAction(() => setAutomaticControl(enabled)),
        [runAction],
    );

    return { state, error, busy, setOutput, updateLightSchedule, setAutomatic };
}
