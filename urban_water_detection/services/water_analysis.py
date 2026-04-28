from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd

LOSS_REQUIRED_COLUMNS = {
    "zone": ["zone", "zone name", "zone_name", "area", "district"],
    "water_supplied": ["water supplied", "water_supplied", "supplied", "supply"],
    "water_billed": ["water billed", "water_billed", "billed", "billing"],
}

LOSS_OPTIONAL_COLUMNS = {
    "pressure": ["pressure"],
    "flow_rate": ["flow rate", "flow_rate", "flow"],
    "date": ["date", "timestamp", "day"],
}

LEAK_REQUIRED_COLUMNS = {
    "zone": ["zone", "zone name", "zone_name", "area", "district"],
    "leakage_flag": ["leakage flag", "leakage_flag", "leak flag", "leak_flag", "target", "label"],
}

LEAK_OPTIONAL_COLUMNS = {
    "date": ["date", "timestamp", "day"],
}


def normalize_column_name(name: str) -> str:
    return " ".join(name.strip().lower().replace("_", " ").split())


def _find_source_column(normalized_to_raw: dict[str, str], aliases: list[str]) -> str | None:
    return next((normalized_to_raw.get(alias) for alias in aliases if alias in normalized_to_raw), None)


def _build_rename_map(
    normalized_to_raw: dict[str, str],
    required_columns: dict[str, list[str]],
    optional_columns: dict[str, list[str]],
) -> dict[str, str]:
    rename_map: dict[str, str] = {}

    for canonical, aliases in required_columns.items():
        source = _find_source_column(normalized_to_raw, aliases)
        if source is None:
            alias_text = ", ".join(aliases)
            raise ValueError(f"Missing required column for '{canonical}'. Accepted names: {alias_text}")
        rename_map[source] = canonical

    for canonical, aliases in optional_columns.items():
        source = _find_source_column(normalized_to_raw, aliases)
        if source is not None:
            rename_map[source] = canonical

    return rename_map


def standardize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    raw_to_normalized = {col: normalize_column_name(col) for col in df.columns}
    normalized_to_raw = {v: k for k, v in raw_to_normalized.items()}

    has_loss_columns = all(_find_source_column(normalized_to_raw, aliases) for aliases in LOSS_REQUIRED_COLUMNS.values())
    has_leak_columns = all(_find_source_column(normalized_to_raw, aliases) for aliases in LEAK_REQUIRED_COLUMNS.values())

    if has_loss_columns:
        rename_map = _build_rename_map(normalized_to_raw, LOSS_REQUIRED_COLUMNS, LOSS_OPTIONAL_COLUMNS)
        return df.rename(columns=rename_map), "water_loss"

    if has_leak_columns:
        rename_map = _build_rename_map(normalized_to_raw, LEAK_REQUIRED_COLUMNS, LEAK_OPTIONAL_COLUMNS)
        return df.rename(columns=rename_map), "leakage_detection"

    raise ValueError(
        "Unsupported dataset schema. Use either: "
        "(zone, water_supplied, water_billed) or (zone, leakage_flag)."
    )


def prepare_dataframe_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    text = file_bytes.decode("utf-8", errors="replace")
    return prepare_dataframe_from_text(text)


def prepare_dataframe_from_text(text: str) -> pd.DataFrame:
    df = pd.read_csv(StringIO(text))
    return _clean_dataframe(df)


def prepare_dataframe_from_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    return _clean_dataframe(df)


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df, mode = standardize_columns(df)

    df["zone"] = df["zone"].astype(str).str.strip()

    if mode == "water_loss":
        for col in ["water_supplied", "water_billed"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["zone", "water_supplied", "water_billed"])
        if df.empty:
            raise ValueError("No valid records found after cleaning input data.")

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        df["water_loss"] = df["water_supplied"] - df["water_billed"]
        df.attrs["analysis_mode"] = "water_loss"
        return df

    df["leakage_flag"] = df["leakage_flag"].apply(_normalize_binary_flag)
    df = df.dropna(subset=["zone", "leakage_flag"])
    if df.empty:
        raise ValueError("No valid records found after cleaning input data.")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df["leakage_flag"] = df["leakage_flag"].astype(int)
    df.attrs["analysis_mode"] = "leakage_detection"
    return df


def _normalize_binary_flag(value) -> int | None:
    if pd.isna(value):
        return None

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "leak", "leakage"}:
        return 1
    if normalized in {"0", "false", "no", "n", "normal", "ok"}:
        return 0

    try:
        numeric = int(float(normalized))
        return 1 if numeric > 0 else 0
    except ValueError:
        return None


def analyze_water_loss(df: pd.DataFrame, threshold: float) -> dict:
    zone_grouped = (
        df.groupby("zone", as_index=False)[["water_supplied", "water_billed", "water_loss"]].sum()
        .sort_values("water_loss", ascending=False)
        .reset_index(drop=True)
    )

    zone_grouped["leak_flag"] = zone_grouped["water_loss"] > threshold

    alerts = []
    for _, row in zone_grouped[zone_grouped["leak_flag"]].iterrows():
        alerts.append(
            {
                "zone": row["zone"],
                "water_loss": round(float(row["water_loss"]), 2),
                "message": f"Leak suspected in {row['zone']} (loss={row['water_loss']:.2f}).",
            }
        )

    anomalies = zone_grouped[zone_grouped["water_loss"] < 0]
    for _, row in anomalies.iterrows():
        alerts.append(
            {
                "zone": row["zone"],
                "water_loss": round(float(row["water_loss"]), 2),
                "message": f"Anomaly in {row['zone']}: billed water exceeds supplied water.",
            }
        )

    trend_payload = {"labels": [], "supplied": [], "billed": [], "loss": []}
    if "date" in df.columns:
        dated_df = df.dropna(subset=["date"]).copy()
        if not dated_df.empty:
            dated_df["date_only"] = dated_df["date"].dt.date
            trend_df = (
                dated_df.groupby("date_only", as_index=False)[["water_supplied", "water_billed", "water_loss"]]
                .sum()
                .sort_values("date_only")
            )
            trend_payload = {
                "labels": [str(d) for d in trend_df["date_only"].tolist()],
                "supplied": [round(float(v), 2) for v in trend_df["water_supplied"].tolist()],
                "billed": [round(float(v), 2) for v in trend_df["water_billed"].tolist()],
                "loss": [round(float(v), 2) for v in trend_df["water_loss"].tolist()],
            }

    total_supplied = round(float(zone_grouped["water_supplied"].sum()), 2)
    total_billed = round(float(zone_grouped["water_billed"].sum()), 2)
    total_loss = round(float(zone_grouped["water_loss"].sum()), 2)

    zone_records = []
    for _, row in zone_grouped.iterrows():
        zone_records.append(
            {
                "zone": row["zone"],
                "water_supplied": round(float(row["water_supplied"]), 2),
                "water_billed": round(float(row["water_billed"]), 2),
                "water_loss": round(float(row["water_loss"]), 2),
                "leak_flag": bool(row["leak_flag"]),
            }
        )

    return {
        "mode": "water_loss",
        "mode_label": "Water Loss Analysis",
        "metric_labels": {
            "total_supplied": "Total Supplied",
            "total_billed": "Total Billed",
            "total_loss": "Total Loss",
            "loss_percentage": "Loss %",
        },
        "metrics": {
            "zone_count": int(zone_grouped.shape[0]),
            "total_supplied": total_supplied,
            "total_billed": total_billed,
            "total_loss": total_loss,
            "loss_percentage": round((total_loss / total_supplied) * 100, 2) if total_supplied else 0,
            "threshold": threshold,
            "alerts_count": len(alerts),
        },
        "zones": {
            "labels": zone_grouped["zone"].tolist(),
            "supplied": [round(float(v), 2) for v in zone_grouped["water_supplied"].tolist()],
            "billed": [round(float(v), 2) for v in zone_grouped["water_billed"].tolist()],
            "loss": [round(float(v), 2) for v in zone_grouped["water_loss"].tolist()],
            "leak_flags": zone_grouped["leak_flag"].tolist(),
            "table": zone_records,
        },
        "distribution": {
            "labels": zone_grouped["zone"].tolist(),
            "supplied_share": [round(float(v), 2) for v in zone_grouped["water_supplied"].tolist()],
        },
        "trends": trend_payload,
        "alerts": alerts,
    }


def analyze_leakage_flags(df: pd.DataFrame, threshold: float) -> dict:
    zone_grouped = (
        df.groupby("zone", as_index=False)["leakage_flag"]
        .agg(total_records="count", leak_events="sum")
        .sort_values("leak_events", ascending=False)
        .reset_index(drop=True)
    )
    zone_grouped["normal_events"] = zone_grouped["total_records"] - zone_grouped["leak_events"]
    zone_grouped["leak_rate"] = (zone_grouped["leak_events"] / zone_grouped["total_records"]) * 100
    zone_grouped["leak_flag"] = zone_grouped["leak_rate"] > threshold

    alerts = []
    for _, row in zone_grouped[zone_grouped["leak_flag"]].iterrows():
        alerts.append(
            {
                "zone": row["zone"],
                "water_loss": round(float(row["leak_events"]), 2),
                "message": (
                    f"Leak risk in {row['zone']} "
                    f"(leak-rate={row['leak_rate']:.2f}%, events={int(row['leak_events'])})."
                ),
            }
        )

    trend_payload = {"labels": [], "supplied": [], "billed": [], "loss": []}
    if "date" in df.columns:
        dated_df = df.dropna(subset=["date"]).copy()
        if not dated_df.empty:
            dated_df["date_only"] = dated_df["date"].dt.date
            trend_df = (
                dated_df.groupby("date_only", as_index=False)["leakage_flag"]
                .agg(total_records="count", leak_events="sum")
                .sort_values("date_only")
            )
            trend_df["normal_events"] = trend_df["total_records"] - trend_df["leak_events"]
            trend_payload = {
                "labels": [str(d) for d in trend_df["date_only"].tolist()],
                "supplied": [int(v) for v in trend_df["total_records"].tolist()],
                "billed": [int(v) for v in trend_df["normal_events"].tolist()],
                "loss": [int(v) for v in trend_df["leak_events"].tolist()],
            }

    total_records = int(zone_grouped["total_records"].sum())
    total_normal = int(zone_grouped["normal_events"].sum())
    total_leaks = int(zone_grouped["leak_events"].sum())

    zone_records = []
    for _, row in zone_grouped.iterrows():
        zone_records.append(
            {
                "zone": row["zone"],
                "water_supplied": int(row["total_records"]),
                "water_billed": int(row["normal_events"]),
                "water_loss": int(row["leak_events"]),
                "leak_flag": bool(row["leak_flag"]),
            }
        )

    return {
        "mode": "leakage_detection",
        "mode_label": "Leakage Flag Analysis",
        "metric_labels": {
            "total_supplied": "Total Records",
            "total_billed": "Normal Events",
            "total_loss": "Leak Events",
            "loss_percentage": "Leak Rate %",
        },
        "metrics": {
            "zone_count": int(zone_grouped.shape[0]),
            "total_supplied": total_records,
            "total_billed": total_normal,
            "total_loss": total_leaks,
            "loss_percentage": round((total_leaks / total_records) * 100, 2) if total_records else 0,
            "threshold": threshold,
            "alerts_count": len(alerts),
        },
        "zones": {
            "labels": zone_grouped["zone"].tolist(),
            "supplied": [int(v) for v in zone_grouped["total_records"].tolist()],
            "billed": [int(v) for v in zone_grouped["normal_events"].tolist()],
            "loss": [int(v) for v in zone_grouped["leak_events"].tolist()],
            "leak_flags": zone_grouped["leak_flag"].tolist(),
            "table": zone_records,
        },
        "distribution": {
            "labels": zone_grouped["zone"].tolist(),
            "supplied_share": [int(v) for v in zone_grouped["total_records"].tolist()],
        },
        "trends": trend_payload,
        "alerts": alerts,
    }


def analyze_dataset(df: pd.DataFrame, threshold: float) -> dict:
    mode = df.attrs.get("analysis_mode")
    if mode == "leakage_detection":
        return analyze_leakage_flags(df, threshold)
    return analyze_water_loss(df, threshold)
