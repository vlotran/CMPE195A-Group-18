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

- Appearance settings: light/dark theme, °C/°F

- Mock sensor mode: the whole system runs on a laptop without hardware

- CI on every push (GitHub Actions): tests, lint and build on every push; every green commit on main is deployed to the Pi automatically, with a database backup and automatic rollback if the backend doesn't come back healthy

**Incomplete:**
- Password reset ("Forgot password?") is not implemented
...
## System Architecture
![ProtoypeDiagram](ProtoypeDiagram.png)
- **Sensors:** BME280 (temperature, humidity, pressure), BME680 (temperature, humidity, pressure, air quality), Atlas Scientific EZO-pH on I2C.
- **Data collector:** a background task in the backend reads every sensor, stores the reading, and evaluates it against every user's active profile. If a sensor's hardware is missing, that sensor falls back to mock data on its own.
- **API:** FastAPI. Sensor data is public; profiles and alerts need a login token (`Authorization: Bearer <token>`).
- **Database:** SQLite (`data/hydroponic.db`) with tables for readings, users, sessions, profiles and alerts. Older databases are upgraded automatically on startup.
- **Frontend:** React + Vite, reached through an ngrok tunnel to the Pi.
- **Open loop:** data flows one way, from sensors to the user. Nothing in the system controls pumps, lights or dosing.

## Prerequisites
- Python: Version 3.11+
- Node.js: 20.19+ or 22.12+
- Git: any

**Hardware (only for real sensors):** Raspberry Pi 5 with I2C enabled, BME280, BME680, Atlas Scientific EZO-pH (I2C mode). Without hardware, use mock mode.

**Accounts:** none needed to run locally. Public access to the Pi uses an ngrok account (held by the team).

## Installation
Numbered steps from a clean machine. Document environment variables without their values.

## Running the Prototype
The exact commands to start the system.

## Testing
How to run your tests, and what they cover.

## Demo
Your demo video link, plus screenshots or logs.

## Technical Stack
- **Languages:** Python, JavaScript (JSX), SQL
- **Frontend:** React 19, Vite 7, Tailwind CSS 4 + custom CSS, custom SVG charts
- **Backend:** FastAPI, Uvicorn, Pydantic v2, pydantic-settings, asyncio, Loguru
- **Database:** SQLite via aiosqlite
- **Auth:** scrypt password hashing and session tokens (Python standard library)
- **Hardware:** Raspberry Pi 5; BME280, BME680, Atlas Scientific EZO-pH
- **Hardware libraries:** Adafruit CircuitPython (BME280/BME680), smbus2 (EZO-pH)
- **Networking:** ngrok
- **Testing / CI:** pytest, ESLint, GitHub Actions

## What's Next
What you will finish before the Project Expo on December 11.