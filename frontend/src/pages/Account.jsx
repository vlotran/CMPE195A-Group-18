/**
 * Account Page 
 *
 * Shows who is signed in and the account actions:
 *  - Name
 *  - Email + "Change Email" button       (not working yet, implemented later)
 *  - "Reset Password" button              (not working yet, implemented later)
 *  - "Delete Account" button -> DeleteAccountDialog (asks for the password)
 *
 * After a successful delete, App shows AccountDeletedDialog with an OK button
 * that leads to the landing page (see onAccountDeleted in App.jsx).
 *
 * Button styles are reused on purpose:
 *  - Change Email / Reset Password = Settings' "New Profile" (.btn-create)
 *  - Delete Account                = Navbar's "Log out" (.nav-logout)
 *
 * Props:
 *  - user: { name, email }
 *  - onAccountDeleted(): called after the account was deleted
 */
import React, { useState } from "react";
import DeleteAccountDialog from "../components/DeleteAccountDialog.jsx";
import "../styles/settings.css";   // .btn-create
import "../styles/navbar.css";     // .nav-logout
import "../styles/account.css";

function Account({ user, onAccountDeleted }) {
    const [confirmOpen, setConfirmOpen] = useState(false);

    // Placeholders: these buttons do nothing until the features are built
    const handleChangeEmail = () => {};    // TODO: change email
    const handleResetPassword = () => {};  // TODO: reset password

    return (
        <div className="account-page">
            <h2 className="account-title">Account</h2>

            {/* Row 1: Name */}
            <div className="account-row">
                <span className="account-label">Name</span>
                <span className="account-value">{user.name}</span>
            </div>

            {/* Row 2: Email + Change Email */}
            <div className="account-row">
                <span className="account-label">Email</span>
                <div className="account-value-group">
                    <span className="account-value">{user.email}</span>
                    <button type="button" className="btn-create" onClick={handleChangeEmail}>
                        Change Email
                    </button>
                </div>
            </div>

            {/* Row 3: Reset Password next to Delete Account, on the right */}
            <div className="account-actions">
                <button type="button" className="btn-create" onClick={handleResetPassword}>
                    Reset Password
                </button>
                <button type="button" className="nav-logout" onClick={() => setConfirmOpen(true)}>
                    Delete Account
                </button>
            </div>

            {confirmOpen && (
                <DeleteAccountDialog
                    onCancel={() => setConfirmOpen(false)}
                    onDeleted={() => {
                        // Same event, so React swaps the two popups in one step
                        setConfirmOpen(false);
                        onAccountDeleted();
                    }}
                />
            )}
        </div>
    );
}

export default Account;
