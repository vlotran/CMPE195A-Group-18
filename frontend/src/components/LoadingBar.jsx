import "../styles/loadingBar.css";

// Small indeterminate glowing bar.
// No state or effect needed: the parent (loading screen in App.jsx) is removed
// when loading finishes, which removes the bar with it.
export default function LoadingBar({ active = true }) {
    if (!active) return null;

    return (
        <div
        className="loading-bar"
        role="progressbar"
        aria-busy="true"
        aria-label="Loading dashboard"
        >
        <div className="loading-bar__fill" />
        </div>
    );
}