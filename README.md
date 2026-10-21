# Unit3_Summative_Assessment_Project

## Environmental Trends & Sensor Monitor

The Streamlit dashboard visualizes historical pollution and climate trends from
`global_climate_impact_1990_2025.csv`, supports uploaded sensor-reading CSVs,
and provides downloadable summaries for community and organizational review.
It does not connect to a live sensor feed.

### Run the dashboard

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### Sensor CSV format

Upload a CSV with a `timestamp` (or `datetime`) column and one or more pollutant
columns named `pm2_5`, `pm10`, `no2`, or `ozone`. A `site` column is optional.
Sensor data is used for in-session visualization; verify units and calibration
before interpreting readings. Short-interval sensor values must not be treated
as annual guideline compliance results.
