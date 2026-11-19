/**
 * AccountDeletedDialog Component (NEW)
 *
 * Popup shown after the account was deleted. Fades in and slides up as the
 * "Are you sure?" popup finishes fading out. OK leads to the landing page.
 * Rendered by App (not the Account page) so it stays put while the dashboard
 * behind it re-renders; its backdrop also blocks clicks on that dashboard.
 *
 * Props:
 *  - onOk()
 */
import React from "react";
import "../styles/confirmDialog.css";
import "../styles/settings.css";              // .btn-create for the OK button
import "../styles/deleteAccountDialog.css";

function AccountDeletedDialog({ onOk }) {
    return (
        // no-fade: the backdrop takes over from the previous popup's backdrop
        <div className="confirm-overlay no-fade">
            <div
                className="confirm-box account-deleted-box"
                role="alertdialog"
                aria-labelledby="account-deleted-title"
            >
                <h3 id="account-deleted-title" className="confirm-title account-deleted-title">
                    Your Account Has Been Deleted Successfully
                </h3>
                <div className="confirm-actions delete-account-actions">
                    <button type="button" className="btn-create" onClick={onOk} autoFocus>
                        OK
                    </button>
                </div>
            </div>
        </div>
    );
}

export default AccountDeletedDialog;
