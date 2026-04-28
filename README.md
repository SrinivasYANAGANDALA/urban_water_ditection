# Urban Water Loss Detection System

This is a complete, structured Flask project for urban water loss detection using CSV data.
It detects leaks and abnormal consumption, identifies high-loss zones, and displays all required dashboards.

## Problem Statement

Urban water systems lose significant resources due to leaks and inefficiencies.
This project provides a data-driven system to:

- Analyze water usage and flow data
- Detect leakage and abnormal consumption
- Identify high-loss zones
- Support targeted maintenance actions
- Improve long-term water reliability

## Tech Stack

- Python
- Flask
- Pandas
- HTML/CSS/JavaScript
- Chart.js

## Core Logic

- Water Loss = Water Supplied - Water Billed
- If zone loss exceeds threshold, zone is flagged for leakage
- If billed is greater than supplied, anomaly alert is created

The system now supports two analysis modes automatically:

- Water Loss mode: uses zone + water supplied + water billed
- Leakage Flag mode: uses zone + leakage_flag (Kaggle-style datasets)

## Required Dashboards Included

- Water Supplied vs Water Billed (bar chart)
- Water Loss per Zone (bar chart)
- Leakage Detection Alerts (alert panel)
- Water Distribution (pie chart)
- Time-Based Trends (line chart)
- Zone Loss Summary (tabular dashboard)

## Input Data Format

Required columns (aliases supported):

- zone
- water supplied
- water billed

Alternative supported schema (Kaggle-style):

- zone
- leakage_flag

Optional columns:

- pressure
- flow rate
- date

Example row:

```csv
Zone1,1000,950
```

Sample file: sample_data/water_data.csv

## API Endpoints

- POST /api/analyze
  - form-data: file (csv), threshold (number)
- GET /api/analyze-sample?threshold=50
  - analyzes bundled sample CSV

## Workflow

1. User uploads CSV or clicks Run Sample Dataset.
2. Backend cleans data and computes water loss metrics.
3. Leakage and anomaly alerts are generated.
4. Dashboard updates all visual components.

## Run Instructions

1. Create and activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run server

```bash
python app.py
```

4. Open browser

http://127.0.0.1:5000

## Tests

Run unit tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Single Server Deployment (Production)

This app can run on a single server with Gunicorn and optionally Nginx.

### Option A: Gunicorn only (simple)

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start Gunicorn:

```bash
gunicorn -c deploy/gunicorn.conf.py wsgi:app
```

3. Open:

http://127.0.0.1:8000

### Option B: Gunicorn + Nginx + systemd (recommended)

Files provided:

- deploy/systemd/urban-water.service
- deploy/nginx/urban-water.conf
- deploy/.env.example
- deploy/setup_single_server.sh

One-command setup on Ubuntu server:

```bash
sudo bash deploy/setup_single_server.sh --domain your-domain.com --app-dir /opt/urban_water_ditection --app-user www-data
```

This script installs system packages, creates/updates venv, installs Python dependencies, writes systemd and Nginx configs, and starts both services.

High-level setup on Ubuntu:

1. Copy project to /opt/urban_water_ditection
2. Create virtual environment and install dependencies
3. Copy deploy/.env.example to deploy/.env and adjust values
4. Copy deploy/systemd/urban-water.service to /etc/systemd/system/
5. Reload and start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable urban-water
sudo systemctl start urban-water
sudo systemctl status urban-water
```

6. Copy deploy/nginx/urban-water.conf to /etc/nginx/sites-available/
7. Enable site and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/urban-water.conf /etc/nginx/sites-enabled/urban-water.conf
sudo nginx -t
sudo systemctl restart nginx
```

### Quick production start script

```bash
bash deploy/run_prod.sh
```

## Project Structure

```text
urban_water_ditection/
├── app.py
├── requirements.txt
├── wsgi.py
├── deploy/
│   ├── .env.example
│   ├── gunicorn.conf.py
│   ├── run_prod.sh
│   ├── nginx/
│   │   └── urban-water.conf
│   └── systemd/
│       └── urban-water.service
├── urban_water_detection/
│   ├── __init__.py
│   ├── config.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── api.py
│   └── services/
│       ├── __init__.py
│       └── water_analysis.py
├── templates/
│   └── index.html
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       └── app.js
├── sample_data/
│   └── water_data.csv
└── tests/
    └── test_water_analysis.py
```