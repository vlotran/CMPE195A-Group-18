/**
 * DeleteAccountDialog Component (NEW)
 *
 * "Are you sure?" popup for the Account page. Asks for the account password,
 * then calls DELETE /api/auth/me.
 *  - No / click outside: closes it (not while the delete is running)
 *  - Yes: deletes. A wrong password shows "Incorrect password" in the popup
 *    and the account stays.
 *  - On success the box fades out, THEN onDeleted() runs, so App can fade the
 *    "deleted" popup in right after (see AccountDeletedDialog).
 *
 * Props:
 *  - onCancel()
 *  - onDeleted(): called once the fade-out has finished
 */
import React, { useState } from "react";
import { deleteAccount } from "../services/api.js";
import "../styles/confirmDialog.css";       
import "../styles/profileModal.css";
import "../styles/deleteAccountDialog.css";

function DeleteAccountDialog({ onCancel, onDeleted }) {
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [closing, setClosing] = useState(false);  

    const handleSubmit = async (e) => {
        e.preventDefault();             // a form, so Enter in the box also submits
        if (busy || !password) return;
        setBusy(true);
        setError("");
        try {
            await deleteAccount(password);
            setClosing(true);           // onAnimationEnd below continues from here
        } catch (err) {
            setError(err.message);    
            setBusy(false);
        }
    };

    // Ignore clicks outside while deleting or fading out
    const handleCancel = () => {
        if (!busy) onCancel();
    };

    return (
        <div className="confirm-overlay" onClick={handleCancel}>
            <form
                className={`confirm-box delete-account-box ${closing ? "is-closing" : ""}`}
                onClick={(e) => e.stopPropagation()}
                onSubmit={handleSubmit}
                onAnimationEnd={(e) => {
                    // only the fade-out, not animations of elements inside
                    if (closing && e.target === e.currentTarget) onDeleted();
                }}
            >
                <h3 className="confirm-title">Are you sure?</h3>
                <p className="confirm-message">
                    This will delete all of the account information, including email
                    and profile settings.
                </p>

                <label htmlFor="delete-password" className="delete-account-label">
                    Enter your password to confirm
                </label>
                <div className="delete-account-password">
                    <input
                        id="delete-password"
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => {
                            setPassword(e.target.value);
                            setError("");        // clear the error once they retype
                        }}
                        placeholder="Password"
                        autoComplete="current-password"
                        disabled={busy}
                        aria-invalid={Boolean(error)}
                        aria-describedby={error ? "delete-password-error" : undefined}
                        autoFocus
                    />
                    <button
                        type="button"
                        className="delete-account-toggle"
                        onClick={() => setShowPassword((s) => !s)}
                    >
                        {showPassword ? "Hide password" : "Show password"}
                    </button>
                </div>
                {error && (
                    <p id="delete-password-error" className="delete-account-error" role="alert">
                        {error}
                    </p>
                )}

                <div className="confirm-actions delete-account-actions">
                    <button type="button" className="btn-cancel" onClick={handleCancel} disabled={busy}>
                        No
                    </button>
                    <button type="submit" className="btn-confirm-delete" disabled={busy || !password}>
                        {busy ? "Deleting..." : "Yes"}
                    </button>
                </div>
            </form>
        </div>
    );
}

export default DeleteAccountDialog;
