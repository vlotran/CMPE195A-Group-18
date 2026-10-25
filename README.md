# SMART HYDROPONIC GARDEN SYSTEM (the one we will submit)

## Team
- Hoa Tuong Minh Nguyen (GitHub: @MinhHoaNguyen)
- Vy Lo Phuong Tran (GitHub: @vlotran)
- Thai Nguyen (GitHub: @thaiHnguyen)

## Project Description
Small hydroponic growers have to check pH, temperature and humidity by hand, and problems often go unnoticed until plants are damaged. Our system uses a Raspberry Pi 5 with live camera and I2C sensors to read the garden data every 30 seconds, stores the readings, and shows them on a browser dashboard. It is an open-loop system: it senses, stores, displays and alerts so that the user can decide what to do. 

## Prototype Scope
**Works end to end now:**
- Sensors -> Raspberry Pi -> FastAPI -> SQLite -> React dashboard

- Four metrics on the dashboard air temperature, air humidity, air quality score and water pH (each with a sensor data widget and a 24-hour chart)

- Live camera view of the plants on the dashboard (Arducam V3 camera)

- User accounts: create account, sign in with 6-hour session, log out

- Per-user threshold profiles: every account starts with 10 example profiles (Lettuce, Tomato, Basil) and user can add, edit, delete and activate them on their own

- Alerts: each reading is checked against each user's active profile; Warning/Danger states on the cards, a popup for Danger, and an alert history panel with an unread badge and "Mark all as read"

- Appearance settings: light/dark theme, °C to °F convertion

- Mock sensor mode: the whole system runs on a laptop without hardware

- CI on every push (GitHub Actions): tests, lint and build on every push; every green commit on main is deployed to the Pi automatically, with a database backup and automatic rollback if the backend doesn't come back healthy

**Incomplete:**
- Password reset ("Forgot password?") is not implemented
- The frontend runs locally and reaches the Pi through ngrok; it is not hosted at a public URL yet.
- The pH sensor still runs on simulated data on the Pi; BME280 and BME680 readings are live (remove if it is integrated before submititng)
- Password reset ("Forgot password?") is not implemented
...

## System Architecture
![ProtoypeDiagram](docs/system-architecture/ProtoypeDiagram.png)
- **Sensors:** 
    + BME280: Air temperature (C), air humidity (%)
    + BME680: Air temperature (C), air humidity (%), air quality
    + Atlas Scientific EZO-pH: Water pH (0–14)
- **Live Camera:** Arducam V3 using Picamera2 to stream MJPEG to the dashboard. The browser gets a short-lived stream token, so the login token never appears in a URL. Without a camera, the widget shows "unavailable" and everything else keeps working.
- **Data collector:** a background task in the backend reads every sensor, stores the reading, and evaluates it against every user's active profile. If a sensor's hardware is missing, that sensor falls back to mock data on its own..
- **API:** FastAPI. Sensor data is public; profiles and alerts need a login token (`Authorization: Bearer <token>`).
- **Networking**: the ngrok agent runs on the Pi and opens an outbound tunnel to ngrok, which gives the backend a public HTTPS URL and forwards each request to localhost:8000. The Pi needs no port forwarding or public IP, so it works behind the school or home network.
- **Deployment:** a self-hosted GitHub runner on the Pi pulls each green commit on `main`, backs up the database, restarts the `hydroponic` systemd service and rolls back if the health check fails ([docs/CI_CD.md](docs/CI_CD.md)).
- **Database:** SQLite (`data/hydroponic.db`) with tables for readings, users, sessions, profiles and alerts. Older databases are upgraded automatically on startup.
- **Frontend:** React + Vite. It calls the backend through `VITE_API_BASE_URL: localhost:8000` during development, or the Pi's ngrok URL.
- **Outlets (planned, dashed in the diagram):** a 4-channel relay board on the Pi's GPIO switches four outlets: light, humidifier, exhaust fan and water pump. The user will turn each one on or off with a dashboard button; the request goes through the same login-protected API.
- **Open loop:** the system senses, stores, displays and alerts, but never acts by itself. Readings never trigger an outlet automatically: user reads the dashboard and decides whether to switch something.
- **Deployment Pipeline**:
![DeploymentPipeline](docs/system-architecture/DeploymentPipeline.png)

## Prerequisites
- Python: Version 3.11+
- Node.js: 20.19+ or 22.12+
- Git: any

**Hardware (only for working sensors and camera):** 
    + Raspberry Pi 5 with I2C enabled, BME280, BME680, Atlas Scientific EZO-pH (I2C mode), Raspberry Pi camera module. 
    + Outputs: a 4-channel relay board on GPIO with four outlets (light, humidifier, exhaust fan, water pump)
    + The software to switch them is planned. Without hardware, use mock mode.

**Accounts:** none needed to run locally. Public access to the Pi uses an ngrok account (held by the team).

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/vlotran/CMPE195A-Group-18.git
   cd CMPE195A-Group-18
   ```
2. Install backend dependencies (from the repo root):
   ```bash
   pip install -r requirements.txt
   ```
3. Create the backend config. On a machine without sensors, set `USE_MOCK_SENSORS=True` in it:
   ```bash
   cp .env.example .env
   ```
4. Install frontend dependencies and create its config:
   ```bash
   cd frontend
   npm install
   cp .env.example .env
   cd ..
   ```
5. **Raspberry Pi only:** install the hardware libraries into the same Python that runs the backend, and set `USE_MOCK_SENSORS=False` in `.env`:
   ```bash
   pip install adafruit-blinka adafruit-circuitpython-bme280 adafruit-circuitpython-bme680 smbus2
   sudo apt install -y python3-picamera2 

### Environment variables
`.env` files are gitignored. The `.env.example` files list every variable; no secrets are needed.

**Backend** (`.env` in the repo root):
-
- `APP_NAME`: API title
- `CONTROLLER_NAME`: Device name shown in the navbar (defaults to the hostname)
- `DEBUG`: Auto-reload and debug output
- `LOG_LEVEL`: Log detail (`INFO`, `DEBUG`, ...) 
- `API_HOST`, `API_PORT`: Address the API listens on
- `DATABASE_PATH`: SQLite file, relative to the repo root 
- `USE_MOCK_SENSORS`: `True` = simulated sensors, `False` = real I2C sensors 
- `SENSOR_READ_INTERVAL`: Seconds between sensor reads 
- `ALLOWED_ORIGINS`: Frontend URLs allowed to call the API (comma-separated, or `*`) 

**Frontend** (`frontend/.env`):
- `VITE_API_BASE_URL`: Backend URL: the local backend (for Mock sensor data) or the Pi's ngrok URL (for live sensor data)

## Running the Prototype
Start the backend **from the repo root** (the database path is relative to it):
```bash
python -m backend.src.main
```
In a second terminal, start the frontend:
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173`, click **Get Started -> Create account**, then sign in.

- **Without hardware:** `USE_MOCK_SENSORS=True` and `VITE_API_BASE_URL=http://localhost:8000`. The camera widget shows "unavailable".
- **With the Pi:** the backend runs on the Pi as the `hydroponic` systemd service (`sudo systemctl status hydroponic`). Point `VITE_API_BASE_URL` at the Pi's ngrok URL and create an account there (accounts are stored per database).
- **API docs:** `http://localhost:8000/docs`

After changing `frontend/.env`, restart `npm run dev`.

## Testing

```bash
python -m pytest tests -v                       # backend, from the repo root
cd frontend && npm run lint && npm run build    # frontend checks
```
49 backend tests, no hardware needed:

- `tests/test_alert_evaluator.py`:  24 tests - Normal / Warning / Danger bands for every metric, hysteresis, recovery 
- `tests/test_auth.py`: 15 tests -  Register, login, wrong password, logout, expired sessions; users can't see or change each other's profiles or alerts; per-user alerts 
- `tests/test_sensor_factory.py`: 7 tests - Real/mock selection per sensor data and fallback to mock when hardware is missing 
- `tests/test_camera_manager.py`: 3 tests - Stream output waits for a fresh frame; concurrent starts open the camera only once 

GitHub Actions runs all of these on every push and pull request (`.github/workflows/ci.yml`). 
A green run on `main` triggers the deploy to the Pi (`.github/workflows/deploy.yml`). Details: [docs/CI_CD.md](docs/CI_CD.md).

## Demo
Your demo video link, plus screenshots or logs.

## Technical Stack
- **Languages:** Python, JavaScript (JSX), SQL
- **Frontend:** React 19, Vite 7, Tailwind CSS 4 + custom CSS, custom SVG charts
- **Backend:** FastAPI, Uvicorn, Pydantic v2, pydantic-settings, asyncio, Loguru
- **Database:** SQLite via aiosqlite
- **Auth:** scrypt password hashing and session tokens (Python standard library)
- **Hardware:** Raspberry Pi 5; BME280, BME680, Atlas Scientific EZO-pH; Arducam V3 camera
- **Hardware libraries:** Adafruit CircuitPython (BME280/BME680), smbus2 (EZO-pH), Picamera2 (camera)
- **Networking:** ngrok
- **Testing / CI/CD:** pytest, ESLint, GitHub Actions, self-hosted runner + systemd on the Pi

## What's Next
- Delete/Clear Alerts features for the AlertPanels in DashBoard
- Deploy and Host the frontend at a public URL
- Outlet control: backend endpoints for the 4 relays and on/off buttons on the dashboard (light, humidifier, fan, water pump)
- Connect and calibrate the pH sensor so all four metrics are live? (remove if pH sensor is integrated before submitting this)
- Refine alert feature and push notifications when a reading reaches Warning or Danger
- Email service integration 
- Password Reset via email
- Wire the correct font to Frontend
