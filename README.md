# Dashboard

A simple Python Flask dashboard with weather, time, bus departures, and website uptime monitoring.

## Features

- **Weather Widget**: Displays current weather (hardcoded)
- **Time Widget**: Shows current London time
- **Bus Departures**: Shows next bus departures from 4 stops with vehicle information
- **Uptime Monitor**: Monitors eeveeit.uk with status changes and sound alerts
- **Dark Mode**: Automatically switches to dark mode between sunset and sunrise
- **Simplified Night Mode**: Shows only time, weather, buses, and uptime at night

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running

Start the Flask server:
```bash
python app.py
```

The dashboard will be available at http://127.0.0.1:5000

## API Endpoints

- `GET /` - Dashboard HTML page
- `GET /api/weather` - Weather data
- `GET /api/time` - Current London time
- `GET /api/buses` - Bus departure data
- `GET /api/uptime` - Website uptime status

## Bus Data Sources

The dashboard fetches bus data from:
- https://bustimes.org/stops/1900HA040094/times.json
- https://bustimes.org/stops/1900HA040095/times.json
- https://bustimes.org/stops/1900HA040115/times.json
- https://bustimes.org/stops/1900HA040114/times.json

Vehicle information is fetched from bustimes.org/vehicles.json based on the operator ID from the bus data.

## Uptime Monitoring

The uptime monitor checks eeveeit.uk every 30 seconds and plays a ding sound when the status changes. Status colors:
- Green: UP
- Red: DOWN (404, 502)
- Yellow: ERROR (other errors or connection issues)
