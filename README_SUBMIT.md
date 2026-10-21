# SMART HYDROPONIC GARDEN SYSTEM (the one we will submit)

## Team
- Hoa Tuong Minh Nguyen (GitHub: @MinhHoaNguyen)
- Vy Lo Phuong Tran (GitHub: @vlotran)
- Thai Nguyen (GitHub: @thaiHnguyen)

## Project Description
Small hydroponic growers have to check pH, temperature and humidity manually and problems often go unnoticed until plants are damaged. Our system uses a Raspberry Pi 5 with I2C sensors to read the garden data in real time, stores the readings, and shows them on a web dashboard that helps each user monitor their plant conditions. It is an **open-loop** system: senses, stores, displays and alerts, then user can takes action.

## Prototype Scope
**Works end to end now:**
- Sensors -> Raspberry Pi -> FastAPI -> SQLite -> React dashboard, refreshing every 5 seconds

- Five metrics: temperature, humidity, pH, air pressure, air quality score, each with a card and a 24-hour chart

- User accounts: create account, sign in with 6-hour session, log out

- Per-user threshold profiles: every account starts with 10 example profiles (Lettuce, Tomato, Basil) and can add, edit, delete and activate its own

- Per-user alerts: each reading is checked against each user's active profile; Warning/Danger states on the cards and a popup for Danger

- Appearance settings: light/dark theme, °C/°F

- Mock sensor mode: the whole system runs on a laptop without hardware

- CI on every push (GitHub Actions): backend tests, frontend lint and build

**Incomplete:**
- Password reset ("Forgot password?") is not implemented
...
## System Architecture
... insert diagram

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