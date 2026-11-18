# Email Alerts and Sign-up Email Check — Setup for Pi Owner

## What changed
- **DANGER alerts are emailed.** When a reading reaches DANGER on a user's active profile, that user gets an email. WARNING and back-to-normal alerts stay in the dashboard only.
- **Sign-up checks the email domain.** Domains that can't receive mail, such as `example.com` or `gmail.con`, are rejected. Existing accounts can still log in

Email stays off until `SMTP_USERNAME` is set in `.env`

## What to do on the Pi
Run these from the repo root. `venv/bin/python` is the backend's virtualenv; use `.venv/bin/python` if that's what the Pi has.

### 1. Deploy the code first
Merge to `main` and let the deploy finish. It installs `email-validator` because `requirements.txt` changed. If you deploy by hand:
```bash
git pull
venv/bin/python -m pip install -r requirements.txt
```

> **Do this before editing `.env`.** Older code rejects keys it doesn't know, so the backend won't start and logs `Extra inputs are not permitted`.

### 2. Create the sender account
1. Create a Gmail account just for this project. Don't use a personal account.
2. Turn on 2-Step Verification.
3. Create an App Password in the Google account settings and copy it without spaces.

### 3. Add the settings
Add to `.env` in the **repo root**:
```
SMTP_USERNAME=yourproject@gmail.com
SMTP_PASSWORD=yourapppasswordnospaces
```
Then lock the file. Run this as the user that runs the backend:
```bash
chmod 600 .env
```

Never commit `.env` or paste the password into chat, code or screenshots.

### 4. Remove fake accounts
Alerts sent to accounts like `@example.com` bounce back to the project Gmail. **This permanently deletes those users and their profiles and alerts**, so back up first and check the list.
```bash
sudo systemctl stop hydroponic
cp data/hydroponic.db data/hydroponic-before-email.db

venv/bin/python - <<'PY'
import sqlite3
db = sqlite3.connect("data/hydroponic.db")
db.execute("PRAGMA foreign_keys=ON")  # also removes their profiles and alerts
print(db.execute("SELECT id, email FROM users").fetchall())
print("deleted:", db.execute("DELETE FROM users WHERE email LIKE '%@example.com'").rowcount)
db.commit()
PY
```
If `DATABASE_PATH` in `.env` is different, use that path instead.

### 5. Restart the backend
```bash
sudo systemctl restart hydroponic
```

## How to verify
1. **Send a test email.** Replace the address with your own:
   ```bash
   venv/bin/python -c "import asyncio; from backend.src.services.email_service import send_email; print(asyncio.run(send_email('you@sjsu.edu', 'Hydroponic test', 'Email works.')))"
   ```
   `True` means the mail server accepted it. Check that it arrives, including in spam.
2. **Check sign-up.** `test@example.com` and `test@gmail.con` should show "This email domain can't receive mail." A real address should work.
3. **Trigger a real alert.** Set your active profile's temperature range far from the current reading. An email should arrive after about two readings (`SENSOR_READ_INTERVAL` is 30 seconds by default). Put the range back afterwards.

## Troubleshooting
Watch the log with `sudo journalctl -u hydroponic -f`.

| What you see | Likely cause | Fix |
|---|---|---|
| Backend won't start, `Extra inputs are not permitted` | New `.env` keys with old code | Deploy the code, or remove the keys |
| `Username and Password not accepted` | Wrong password, or the normal Gmail password was used | Create a new App Password and restart |
| Test prints `False` with no error | `SMTP_USERNAME` isn't set, or `.env` isn't in the repo root | Check `.env` |
| Timeout or connection error | The network may block port 587 | Try another network, such as a phone hotspot |
| `Alert email sent` in the log, but nothing arrives | Spam filter | Check spam, especially on school accounts |

## Turning it off
Remove `SMTP_USERNAME` from `.env` and restart. Alerts still appear in the dashboard.

Before rolling back to code older than this feature, also remove `SMTP_USERNAME` and `SMTP_PASSWORD`, or the old code won't start.

If the password may have leaked, delete it in the Google account's App Passwords page, create a new one and restart.

## Known limits
- The check confirms the domain receives mail, not that the mailbox exists or belongs to the person signing up.
- Sign-up has no email confirmation or rate limit, so don't treat this as ready for public use.
- One incident can send two emails, because the BME280 and BME680 both report temperature and humidity.
