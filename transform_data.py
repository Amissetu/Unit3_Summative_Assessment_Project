"""Clean and transform the global climate impact country-year dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = Path(__file__).resolve().with_name(
    "global_climate_impact_1990_2025.csv"
)
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("transformed_data.csv")
REQUIRED_COLUMNS = {"Country", "Year"}
GEOGRAPHIC_CATEGORICAL_COLUMNS = ("Continent", "Region")
MONITORING_COLUMNS = (
    "PM2_5_Annual_Mean_ug_m3",
    "PM10_Annual_Mean_ug_m3",
    "Air_Quality_Index",
    "Ozone_Annual_Mean_ug_m3",
    "NO2_Annual_Mean_ug_m3",
    "CO2_Emissions_Total_Mt",
)


def load_data(input_path: Path) -> pd.DataFrame:
    """Read a CSV and check that it has the country-year keys."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Input CSV does not exist: {input_path}")

    data = pd.read_csv(input_path)
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        raise ValueError(
            f"Input CSV is missing required columns: {sorted(missing_columns)}"
        )
    return data


def clean_data(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize values, remove unusable keys, and impute numeric measurements."""
    cleaned = data.copy()

    # Normalize text fields and treat blank strings as missing values.
    text_columns = cleaned.select_dtypes(include=["object", "string", "category"]).columns
    for column in text_columns:
        values = cleaned[column].astype("string").str.strip()
        cleaned[column] = values.mask(values.eq(""))

    cleaned = cleaned.drop_duplicates().copy()
    cleaned["Year"] = pd.to_numeric(cleaned["Year"], errors="coerce")
    invalid_key_rows = cleaned["Country"].isna() | cleaned["Year"].isna()
    if invalid_key_rows.any():
        print(f"Dropping {int(invalid_key_rows.sum())} rows with missing country/year.")
        cleaned = cleaned.loc[~invalid_key_rows].copy()
    cleaned["Year"] = cleaned["Year"].astype("int64")

    duplicate_keys = cleaned.duplicated(["Country", "Year"], keep=False)
    if duplicate_keys.any():
        examples = cleaned.loc[duplicate_keys, ["Country", "Year"]].head(5)
        raise ValueError(
            "Conflicting duplicate country-year rows found after removing exact "
            f"duplicates. Example keys:\n{examples.to_string(index=False)}"
        )

    # CSV measurements should be numeric; unparseable values become missing.
    for column in cleaned.columns:
        if column not in {"Country", "ISO2", "ISO3", "Continent", "Region"}:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    cleaned = cleaned.replace([float("inf"), float("-inf")], pd.NA)

    # Keep missingness visible for the main monitoring measurements.
    for column in MONITORING_COLUMNS:
        if column in cleaned.columns:
            cleaned[f"{column}_was_missing"] = cleaned[column].isna().astype("int8")

    numeric_columns = cleaned.select_dtypes(include="number").columns
    numeric_columns = [column for column in numeric_columns if column != "Year"]
    country_groups = cleaned.groupby("Country", sort=False, dropna=False)
    for column in numeric_columns:
        country_medians = country_groups[column].transform("median")
        global_median = cleaned[column].median()
        cleaned[column] = cleaned[column].fillna(country_medians)
        if pd.notna(global_median):
            cleaned[column] = cleaned[column].fillna(global_median)

    # Missing categories are explicit rather than silently dropped by encoding.
    for column in text_columns:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].fillna("Unknown")

    return cleaned.sort_values(["Country", "Year"], kind="stable").reset_index(drop=True)


def create_features(data: pd.DataFrame) -> pd.DataFrame:
    """Add time, per-capita, and particulate monitoring features."""
    transformed = data.copy()
    transformed["Decade"] = (transformed["Year"] // 10) * 10

    if {
        "CO2_Emissions_Total_Mt",
        "Population_Year_Millions",
    }.issubset(transformed.columns):
        population = transformed["Population_Year_Millions"].replace(0, pd.NA)
        transformed["CO2_Emissions_Per_Capita_Tons"] = (
            transformed["CO2_Emissions_Total_Mt"] / population
        )

    if "PM2_5_Annual_Mean_ug_m3" in transformed.columns:
        transformed["PM2_5_Above_WHO_Guideline"] = (
            transformed["PM2_5_Annual_Mean_ug_m3"] > 5.0
        ).astype("int8")

    if "PM10_Annual_Mean_ug_m3" in transformed.columns:
        transformed["PM10_Above_WHO_Guideline"] = (
            transformed["PM10_Annual_Mean_ug_m3"] > 15.0
        ).astype("int8")

    particulate_columns = {
        "PM2_5_Annual_Mean_ug_m3",
        "PM10_Annual_Mean_ug_m3",
    }
    if particulate_columns.issubset(transformed.columns):
        pm10 = transformed["PM10_Annual_Mean_ug_m3"].replace(0, pd.NA)
        transformed["PM2_5_to_PM10_Ratio"] = (
            transformed["PM2_5_Annual_Mean_ug_m3"] / pm10
        )

    # Country and ISO codes remain identifiers; encode analytical geography.
    categorical_columns = [
        column
        for column in GEOGRAPHIC_CATEGORICAL_COLUMNS
        if column in transformed.columns
    ]
    if categorical_columns:
        transformed = pd.get_dummies(
            transformed,
            columns=categorical_columns,
            prefix=categorical_columns,
            dtype="int8",
        )

    return transformed


def transform_csv(input_path: Path, output_path: Path) -> pd.DataFrame:
    """Run the complete transformation and write the resulting CSV."""
    transformed = create_features(clean_data(load_data(input_path)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    transformed.to_csv(output_path, index=False)
    return transformed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean and transform the global climate impact CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Source CSV (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Transformed CSV (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    transformed = transform_csv(args.input, args.output)
    print(
        f"Saved {len(transformed):,} rows and {len(transformed.columns):,} columns "
        f"to {args.output.resolve()}"
    )
    remaining_missing = int(transformed.isna().sum().sum())
    if remaining_missing:
        print(
            f"Note: {remaining_missing:,} missing values remain; "
            "these are in columns with no usable numeric values or derived "
            "features that require unavailable/zero denominators."
        )


if __name__ == "__main__":
    main()