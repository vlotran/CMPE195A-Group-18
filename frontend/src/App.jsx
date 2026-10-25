import { useState, useEffect, useRef } from "react";
import {
    getAlerts,
    markAlertRead, 
    getToken,
    fetchCurrentUser,
    logoutUser,
    AUTH_EXPIRED_EVENT,
} from "./services/api.js";

import "./styles/App.css";

import Navbar from "./components/Navbar.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Settings from "./pages/Settings.jsx";
import Appearance from "./pages/Appearance.jsx";
import AlertModal from "./components/AlertModal.jsx";
import AlertPanel from "./components/AlertPanel.jsx"; 
import LandingPage from "./pages/LandingPage.jsx";
import LoadingBar from "./components/LoadingBar.jsx";
import GlassBackground from "./components/GlassBackground.jsx"; 

import useDashboardData from "./hooks/useDashboardData.js";
import useActuators from "./hooks/useActuators.js";

/**
 * App is now the sign-in gate.
 * - Shows LandingPage until someone signs in.
 * - On refresh, a saved token is checked with GET /api/auth/me, so a
 *   remembered user goes straight back to the dashboard.
 * - Goes back to LandingPage on logout, or when the backend rejects the token
 *   (api.js fires AUTH_EXPIRED_EVENT, e.g. after the 6-hour session ends).
 * The dashboard itself (data polling, settings, alerts) lives in AuthedApp
 * below, so nothing is fetched before login and each user starts fresh.
 */
function App() {
    const [user, setUser] = useState(null);
    // Only "checking" when there is a saved token to verify; avoids flashing
    // the landing page for a remembered user
    const [checking, setChecking] = useState(() => Boolean(getToken()));

    // Restore a saved login once, on first load
    useEffect(() => {
        if (!getToken()) return;
        fetchCurrentUser()
            .then(setUser)
            .catch(() => setUser(null)) 
            .finally(() => setChecking(false));
    }, []);

    // Backend said the token is no longer valid -> back to the landing page
    useEffect(() => {
        const onExpired = () => setUser(null);
        window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
        return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
    }, []);

    const handleLogout = async () => {
        try {
            await logoutUser();
        } catch (e) {
            console.error("Logout request failed:", e);   // token is cleared anyway
        }
        setUser(null);
    };

    if (checking) {
        return <p className="dashboard">Loading...</p>;
    }

    // Show Landing Page before entering Dashboard
    if (!user) {
        return <LandingPage onLogin={setUser} />;
    }

    // key: switching accounts remounts the dashboard with fresh state
    return (
        <>
            <GlassBackground soft />
            <AuthedApp key={user.id} user={user} onLogout={handleLogout} />
        </>
    );
}

/**
 * The dashboard for a signed-in user.
 * this was the body of App; it now only mounts after login.
 */
function AuthedApp({ user, onLogout }) {
    const {
        device, current, thresholds, charts,
        activeProfile, refreshProfile, 
        loading, error,
    } = useDashboardData();
    const {
        state: actuatorState,
        error: actuatorError,
        busy: actuatorBusy,
        setOutput: setActuatorOutput,
        updateLightSchedule,
        setAutomatic: setAutomaticControl,
    } = useActuators();
    
    // "dashboard" = show sensor cards and charts
    // "settings"  = show threshold profile management
    // "appearance" = show theme + temperature unit buttons
    const [activeTab, setActiveTab] = useState("dashboard");
    // all unread alerts (one poll feeds the DANGER popup AND the Alerts badge)
    const [unreadAlerts, setUnreadAlerts] = useState([]);
    const [alertsOpen, setAlertsOpen] = useState(false);   // history panel
    // Per-session dismissals, intentionally not persisted, so a refresh re-shows
    const [dismissed, setDismissed] = useState(() => new Set());

    // Appearance page doesn't need sensor data, so it renders the same
    // way in the loading, error, and normal states
    const appearancePage = (
        <main className="dashboard">
            <Appearance />
        </main>
    );

    // fetch ALL unread alerts (not just danger) every 15 s.
    // DANGER ones drive the popup; danger + warning drive the Alerts badge.
    // Unread only, so alerts the user already closed stay closed.
    // Bumping alertsVersion re-runs the poll right away (e.g. after "Mark all as read")
    const [alertsVersion, setAlertsVersion] = useState(0);
    useEffect(() => {
        let cancelled = false;
        const poll = async () => {
            try {
                const alerts = await getAlerts({ limit: 50, unreadOnly: true });
                if (!cancelled) setUnreadAlerts(alerts);
            } catch (e) {
                console.error("Alert poll failed:", e);   // don't break the dashboard
            }
        };
        poll();
        const id = setInterval(poll, 15000);
        return () => { cancelled = true; clearInterval(id); };
    }, [alertsVersion]);


    // re-read the active profile whenever the Dashboard tab is shown, so a profile
    // changed in Settings shows up on the indicator AND the card thresholds right away.
    const seenDashboard = useRef(false);
    useEffect(() => {
        if (activeTab !== "dashboard" || loading) return;
        if (seenDashboard.current) refreshProfile();
        seenDashboard.current = true;
    }, [activeTab, loading, refreshProfile]);

    const dangerAlerts = unreadAlerts.filter((a) => a.severity === "danger");
    const visible = dangerAlerts.filter((a) => !dismissed.has(a.id));
    // badge count = unread warning + danger. Skips ones just closed in the popup,
    // so the badge drops immediately instead of at the next poll.
    // Recoveries back to normal aren't worth a badge.
    const alertCount = unreadAlerts.filter(
        (a) => a.severity !== "normal" && !dismissed.has(a.id)
    ).length;

    const handleClose = () => {
        const ids = visible.map((a) => a.id);
        // Hide right away (also covers a failed request until the next reload)
        setDismissed((prev) => {
            const next = new Set(prev);
            ids.forEach((id) => next.add(id));
            return next;
        });
        // remember it on the backend, so a reload / another device doesn't re-show them
        Promise.allSettled(ids.map((id) => markAlertRead(id))).then((results) => {
            const failed = results.filter((r) => r.status === "rejected").length;
            if (failed) console.error(`Could not mark ${failed} alert(s) as read`);
        });
    };
    
    // Loading State
    if (loading) {
        return (
            <>
                <Navbar 
                    deviceName="Loading..." 
                    status="offline" 
                    activeTab={activeTab}
                    onTabChange={setActiveTab}
                    userName={user.name}
                    onLogout={onLogout}
                />
                {activeTab === "appearance" ? appearancePage : (
                <main className="dashboard">
                    {activeTab === "dashboard" ? (
                        // NEW: small glowing bar under the loading text
                        <div className="dashboard-loading">
                            <p>Loading dashboard data...</p>
                            <LoadingBar active={loading} />
                        </div>
                    ) : (
                        <Settings />
                    )}
                </main>
                )}
            </>
        );
    }
    // Error State
    if (error) {
        return (
            <>
                <Navbar 
                    deviceName="System Error" 
                    status="offline"
                    activeTab={activeTab}
                    onTabChange={setActiveTab}
                    userName={user.name}
                    onLogout={onLogout}
                />
                {activeTab === "appearance" ? appearancePage : (
                <main className="dashboard">
                    {activeTab === "dashboard" ? (
                        <p>Error: {error}</p>
                    ) : (
                        <Settings />
                    )}
                </main>
                )}
            </>
        );
    }
    // Main Render
    return (
        <>
            {/* Navbar - always visible. CHANGED: also holds the tabs (logo | tabs | account) */}
            <Navbar
                deviceName={device?.name || "Smart Hydroponic System"}
                status={device?.status || "offline"}
                lastUpdated={device?.lastUpdated}
                activeTab={activeTab}
                onTabChange={setActiveTab}
                userName={user.name}
                onLogout={onLogout}
            />
            {/*Page Content - conditionally rendered based on active tab*/}
            {activeTab === "dashboard" ? (
                <Dashboard
                    current={current}
                    thresholds={thresholds}
                    charts={charts}
                    profile={activeProfile}   
                    onManageProfiles={() => setActiveTab("settings")} 
                    alertCount={alertCount} 
                    onOpenAlerts={() => setAlertsOpen(true)}  
                    actuatorState={actuatorState}
                    actuatorError={actuatorError}
                    actuatorBusy={actuatorBusy}
                    onSetActuator={setActuatorOutput}
                    onSaveLightSchedule={updateLightSchedule}
                    onSetAutomatic={setAutomaticControl}
                />
            ) : activeTab === "appearance" ? (
                appearancePage
            ) : (
                <main className="dashboard">
                    <Settings />
                </main>
            )}
            {/* alert history panel (opened from the Dashboard's Alerts button) */}
            <AlertPanel
                open={alertsOpen}
                onClose={() => setAlertsOpen(false)}
                onChanged={() => setAlertsVersion((v) => v + 1)}   // refresh the badge after "Mark all as read"
            />

            {/*Alert Modal: use when threshold is on DANGER */}
            <AlertModal alerts={visible} onClose={handleClose} />
        </>
    );
}

export default App;