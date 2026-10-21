"""Streamlit dashboard for environmental trends and uploaded sensor data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


DATA_FILE = Path(__file__).resolve().with_name("global_climate_impact_1990_2025.csv")
PM25_GUIDELINE_UG_M3 = 5.0
PM10_GUIDELINE_UG_M3 = 15.0
POLLUTANT_COLUMNS = {
    "PM2.5": ("PM2_5_Annual_Mean_ug_m3", "µg/m³"),
    "PM10": ("PM10_Annual_Mean_ug_m3", "µg/m³"),
    "Nitrogen dioxide (NO₂)": ("NO2_Annual_Mean_ug_m3", "µg/m³"),
    "Ozone": ("Ozone_Annual_Mean_ug_m3", "µg/m³"),
    "Air quality index": ("Air_Quality_Index", "index"),
}
SENSOR_POLLUTANT_COLUMNS = {
    "pm2_5": ("PM2.5", PM25_GUIDELINE_UG_M3),
    "pm25": ("PM2.5", PM25_GUIDELINE_UG_M3),
    "pm2_5_ug_m3": ("PM2.5", PM25_GUIDELINE_UG_M3),
    "pm10": ("PM10", PM10_GUIDELINE_UG_M3),
    "pm10_ug_m3": ("PM10", PM10_GUIDELINE_UG_M3),
    "no2": ("NO₂", None),
    "no2_ug_m3": ("NO₂", None),
    "ozone": ("Ozone", None),
    "ozone_ug_m3": ("Ozone", None),
}


st.set_page_config(
    page_title="Environmental Trends & Sensor Monitor",
    page_icon="🌿",
    layout="wide",
)


@st.cache_data
def load_environmental_data(path: str) -> pd.DataFrame:
    """Load the supplied country-year dataset and validate dashboard columns."""
    data = pd.read_csv(path)
    required_columns = {
        "Country",
        "Continent",
        "Year",
        *[column for column, _ in POLLUTANT_COLUMNS.values()],
        "CO2_Emissions_Total_Mt",
        "Temperature_Anomaly_C",
        "Respiratory_Disease_Rate_Per100k",
    }
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        raise ValueError(
            f"Environmental dataset is missing required columns: {sorted(missing_columns)}"
        )
    data["Year"] = pd.to_numeric(data["Year"], errors="coerce")
    data = data.dropna(subset=["Year", "Country", "Continent"]).copy()
    data["Year"] = data["Year"].astype(int)
    return data


def display_sensor_monitor() -> None:
    """Render and validate user-uploaded sensor data; no live feed is implied."""
    st.subheader("Sensor and IoT data")
    st.info(
        "This project dataset contains annual country-level indicators, not live sensor "
        "telemetry. Upload an exported sensor CSV to explore readings here. "
        "No external sensor connection is configured."
    )
    upload = st.file_uploader(
        "Upload sensor readings (CSV)",
        type=["csv"],
        help=(
            "Include a timestamp column and one or more recognized pollutant columns, "
            "such as pm2_5, pm10, no2, or ozone."
        ),
        key="sensor_csv",
    )
    if upload is None:
        st.markdown(
            "**Expected format example**\n\n"
            "| timestamp | site | pm2_5 | pm10 |\n"
            "|---|---|---:|---:|\n"
            "| 2025-06-01 09:00:00 | School North | 8.2 | 14.5 |"
        )
        return

    try:
        sensor_data = pd.read_csv(upload)
    except pd.errors.ParserError as exc:
        st.error(f"Could not parse the uploaded sensor CSV: {exc}")
        return
    normalized = {str(column).strip().lower(): column for column in sensor_data.columns}
    timestamp_column = normalized.get("timestamp") or normalized.get("datetime")
    pollutant_columns = {
        normalized[key]: value
        for key, value in SENSOR_POLLUTANT_COLUMNS.items()
        if key in normalized
    }
    if timestamp_column is None:
        st.error("Sensor CSV must include a `timestamp` or `datetime` column.")
        return
    if not pollutant_columns:
        st.error(
            "No recognized pollutant columns found. Supported names include "
            "`pm2_5`, `pm10`, `no2`, and `ozone` (with optional units suffixes)."
        )
        return

    sensor_data[timestamp_column] = pd.to_datetime(
        sensor_data[timestamp_column], errors="coerce", utc=True
    )
    for column in pollutant_columns:
        sensor_data[column] = pd.to_numeric(sensor_data[column], errors="coerce")

    valid_timestamp = sensor_data[timestamp_column].notna()
    if not valid_timestamp.any():
        st.error("No valid timestamps were found in the uploaded sensor CSV.")
        return
    sensor_data = sensor_data.loc[valid_timestamp].sort_values(timestamp_column).copy()
    selected_sensor_label = st.selectbox(
        "Pollutant to visualize",
        options=list(pollutant_columns),
        format_func=lambda column: pollutant_columns[column][0],
    )
    label, guideline = pollutant_columns[selected_sensor_label]
    valid_values = sensor_data[selected_sensor_label].dropna()
    if valid_values.empty:
        st.warning(f"No numeric measurements are available for {label}.")
        return

    latest_value = sensor_data.dropna(subset=[selected_sensor_label]).iloc[-1]
    metric_columns = st.columns(3)
    unit = "index" if label == "Air quality index" else "µg/m³"
    metric_columns[0].metric(
        f"Latest {label}", f"{latest_value[selected_sensor_label]:.2f} {unit}"
    )
    metric_columns[1].metric("Readings", f"{len(valid_values):,}")
    metric_columns[2].metric(
        "Sites",
        str(sensor_data["site"].nunique())
        if "site" in sensor_data.columns
        else "Not provided",
    )

    plot_columns = st.columns(2)
    with plot_columns[0]:
        st.markdown(f"**{label} over time**")
        chart_data = sensor_data.set_index(timestamp_column)[[selected_sensor_label]]
        st.line_chart(chart_data, y=selected_sensor_label, width="stretch")
    with plot_columns[1]:
        if guideline is not None:
            exceedances = int(valid_values.gt(guideline).sum())
            st.markdown("**Comparison with WHO annual guideline reference**")
            st.metric(
                f"Readings above {guideline:g} µg/m³",
                f"{exceedances:,} ({valid_values.gt(guideline).mean() * 100:.1f}%)",
            )
            st.caption(
                "WHO's value is an annual mean guideline. Comparing short-interval "
                "sensor readings with it is only an exploratory flag, not a valid "
                "annual compliance assessment."
            )
        else:
            st.markdown("**Reading distribution**")
            st.dataframe(
                valid_values.describe().rename("measurement").to_frame().round(2),
                width="stretch",
            )

    st.dataframe(sensor_data, width="stretch", hide_index=True)
    st.download_button(
        "Download cleaned sensor readings",
        data=sensor_data.to_csv(index=False).encode("utf-8"),
        file_name="sensor_readings_cleaned.csv",
        mime="text/csv",
    )


def main() -> None:
    st.title("🌿 Environmental Trends & Sensor Monitor")
    st.caption(
        "Explore historical air-quality and climate indicators, or upload sensor "
        "measurements for a focused review."
    )

    if not DATA_FILE.is_file():
        st.error(f"Environmental dataset not found: {DATA_FILE}")
        st.stop()
    try:
        data = load_environmental_data(str(DATA_FILE))
    except (OSError, pd.errors.ParserError, ValueError) as exc:
        st.error(f"Could not load the environmental dataset: {exc}")
        st.stop()

    min_year, max_year = int(data["Year"].min()), int(data["Year"].max())
    with st.sidebar:
        st.header("Explore the historical data")
        year_range = st.slider(
            "Year range",
            min_value=min_year,
            max_value=max_year,
            value=(min_year, max_year),
        )
        continents = sorted(data["Continent"].dropna().unique().tolist())
        selected_continents = st.multiselect(
            "Continents",
            options=continents,
            default=continents,
        )

    filtered = data.loc[
        data["Year"].between(year_range[0], year_range[1])
        & data["Continent"].isin(selected_continents)
    ].copy()
    if filtered.empty:
        st.warning("No records match the selected filters.")
        st.stop()

    historical_tab, sensor_tab, action_tab = st.tabs(
        ["Historical trends", "Sensor data", "Public awareness & collaboration"]
    )

    with historical_tab:
        latest_year = int(filtered["Year"].max())
        latest = filtered.loc[filtered["Year"].eq(latest_year)]
        pm25 = latest["PM2_5_Annual_Mean_ug_m3"].dropna()
        avg_pm25 = pm25.mean() if not pm25.empty else float("nan")
        above_guideline = (
            int(pm25.gt(PM25_GUIDELINE_UG_M3).sum()) if not pm25.empty else 0
        )
        metric_columns = st.columns(4)
        metric_columns[0].metric("Countries in selection", f"{filtered['Country'].nunique():,}")
        metric_columns[1].metric("Latest year", str(latest_year))
        metric_columns[2].metric(
            "Mean PM2.5",
            f"{avg_pm25:.1f} µg/m³" if pd.notna(avg_pm25) else "No data",
            help="Equal-weighted mean across available country observations.",
        )
        metric_columns[3].metric(
            "Countries above PM2.5 guideline",
            f"{above_guideline}/{len(pm25)}" if len(pm25) else "No data",
            help="WHO 2021 annual guideline reference: 5 µg/m³. Not population weighted.",
        )

        annual = filtered.groupby("Year").agg(
            **{
                "PM2.5 (µg/m³)": ("PM2_5_Annual_Mean_ug_m3", "mean"),
                "PM10 (µg/m³)": ("PM10_Annual_Mean_ug_m3", "mean"),
                "PM2.5 country count": ("PM2_5_Annual_Mean_ug_m3", "count"),
                "PM10 country count": ("PM10_Annual_Mean_ug_m3", "count"),
            }
        )
        st.subheader("Particulate matter trends and measurement coverage")
        particulate_plot = annual[["PM2.5 (µg/m³)", "PM10 (µg/m³)"]].copy()
        particulate_plot["PM2.5 WHO annual guideline"] = PM25_GUIDELINE_UG_M3
        particulate_plot["PM10 WHO annual guideline"] = PM10_GUIDELINE_UG_M3
        st.line_chart(particulate_plot, width="stretch")
        st.caption(
            "WHO annual reference values: PM2.5 5 µg/m³; PM10 15 µg/m³. "
            "Country averages are not population-weighted."
        )
        st.line_chart(
            annual[["PM2.5 country count", "PM10 country count"]],
            width="stretch",
        )

        st.subheader(f"Latest available country comparisons ({latest_year})")
        continent_summary = latest.groupby("Continent").agg(
            PM2_5_mean=("PM2_5_Annual_Mean_ug_m3", "mean"),
            PM2_5_reporting_countries=("PM2_5_Annual_Mean_ug_m3", "count"),
            PM10_mean=("PM10_Annual_Mean_ug_m3", "mean"),
            PM10_reporting_countries=("PM10_Annual_Mean_ug_m3", "count"),
        ).sort_values("PM2_5_mean", ascending=False)
        st.bar_chart(continent_summary[["PM2_5_mean", "PM10_mean"]])
        st.dataframe(continent_summary.round(2), width="stretch")

        country_summary = latest[
            [
                "Country",
                "Continent",
                "PM2_5_Annual_Mean_ug_m3",
                "PM10_Annual_Mean_ug_m3",
                "Air_Quality_Index",
            ]
        ].sort_values("PM2_5_Annual_Mean_ug_m3", ascending=False)
        st.dataframe(country_summary.head(15).round(2), width="stretch", hide_index=True)
        st.download_button(
            "Download latest-year country summary",
            data=country_summary.to_csv(index=False).encode("utf-8"),
            file_name=f"environmental_summary_{latest_year}.csv",
            mime="text/csv",
        )

        st.subheader("Climate and emissions context")
        annual_context = filtered.groupby("Year").agg(
            **{
                "Temperature anomaly (°C)": ("Temperature_Anomaly_C", "mean"),
                "Reported CO₂ emissions (Mt)": ("CO2_Emissions_Total_Mt", "sum"),
            }
        )
        context_columns = st.columns(2)
        with context_columns[0]:
            st.markdown("**Mean temperature anomaly**")
            st.line_chart(annual_context[["Temperature anomaly (°C)"]])
        with context_columns[1]:
            st.markdown("**Sum of reported country CO₂ emissions**")
            st.line_chart(annual_context[["Reported CO₂ emissions (Mt)"]])

        st.subheader("Pollution and respiratory disease")
        association = filtered[
            ["PM2_5_Annual_Mean_ug_m3", "Respiratory_Disease_Rate_Per100k"]
        ].dropna()
        if len(association) >= 2:
            correlation = association.iloc[:, 0].corr(association.iloc[:, 1])
            st.scatter_chart(
                filtered,
                x="PM2_5_Annual_Mean_ug_m3",
                y="Respiratory_Disease_Rate_Per100k",
                color="Continent",
                width="stretch",
            )
            st.caption(
                f"Pearson correlation across {len(association):,} available country-year "
                f"pairs: {correlation:.2f}. This is descriptive and does not establish causation."
            )
        else:
            st.info("Not enough paired observations for the selected filters.")

    with sensor_tab:
        display_sensor_monitor()

    with action_tab:
        st.subheader("Turn information into community action")
        st.markdown(
            """
            **For public awareness**
            - Share the downloadable country summary with its year, units, and data-source caveats.
            - Explain that country-level averages can hide neighborhood-level exposure.
            - Use local validated air-quality alerts and health guidance for immediate decisions.

            **For environmental organizations and technical partners**
            - Review indicator definitions, sensor calibration, siting, and data completeness together.
            - Compare uploaded readings with quality-assured monitoring stations before drawing conclusions.
            - Agree on a response owner and review date for any flagged trend.

            **This app does not currently connect to an organization, provide medical advice, or consume a live sensor feed.**
            """
        )
        st.link_button(
            "WHO Air Quality Guidelines",
            "https://www.who.int/publications/i/item/9789240034228",
        )
        st.caption(
            "Guideline exceedances are screening information, not a regulatory finding. "
            "For urgent exposure or health decisions, consult local environmental and public-health authorities."
        )

    st.divider()
    st.caption(
        "Source: supplied global_climate_impact_1990_2025.csv. "
        "Observations are country-year summaries; missing values are excluded per metric."
    )


if __name__ == "__main__":
    main()
