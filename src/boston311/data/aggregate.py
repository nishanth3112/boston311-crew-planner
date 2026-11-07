"""Cleaned requests -> the small files in data/processed/, and queries over them."""

from typing import Literal, get_args

import duckdb
import pandas as pd

from boston311.config import PROCESSED_DIR

Metric = Literal["request_count", "on_time_rate", "median_days_to_close"]
GroupBy = Literal["department", "neighborhood", "request_type", "source", "month"]

SERVICE_STATS = PROCESSED_DIR / "service_stats.parquet"
RESIDENT_SOURCES = {"Citizens Connect App", "Constituent Call", "Self Service"}
MIN_RESIDENT_REQUESTS = 30
FILTERS = {"department", "request_type", "neighborhood", "source", "year"}
METRIC_SQL = {
    "request_count": "COUNT(*)",
    # on_time is NULL for requests without a target date, so AVG leaves them out
    "on_time_rate": "ROUND(AVG(on_time::INT), 3)",
    "median_days_to_close": "ROUND(MEDIAN(close_days)::DOUBLE, 1)",  # stored as float32
}


def monthly_demand(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(["department", "month"]).size().rename("requests").reset_index()


def daily_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Requests per department per calendar day, with zero for days that had none."""
    date = df["open_dt"].dt.normalize().rename("date")
    counts = df.groupby(["department", date]).size()
    days = pd.date_range(date.min(), date.max(), name="date")
    full = pd.MultiIndex.from_product([sorted(df["department"].unique()), days])
    out = counts.reindex(full, fill_value=0).rename("requests").reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.rename(columns={"level_0": "department"})


def sla_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Share of each department's requests by target window in whole days (empty: no target)."""
    days = df["target_days"].round().astype("Int64").rename("target_days")
    out = df.groupby(["department", days], dropna=False).size().rename("requests").reset_index()
    out["share"] = (out["requests"] / out.groupby("department")["requests"].transform("sum")).round(
        5
    )
    return out


def service_stats(df: pd.DataFrame) -> pd.DataFrame:
    """One slim row per request, for exact counts, on-time rates and medians at query time."""
    on_time = (df["on_time"] == "ONTIME").astype("boolean")
    on_time[df["target_days"].isna()] = pd.NA
    return pd.DataFrame(
        {
            "year": df["month"].str[:4].astype("int16"),
            "month": df["month"],
            "department": df["department"],
            "request_type": df["request_type"],
            "neighborhood": df["neighborhood"],
            "source": df["source"],
            "on_time": on_time,
            "close_days": df["close_days"].astype("float32"),
        }
    )


def request_types(df: pd.DataFrame) -> pd.DataFrame:
    """One row per request type: its most common department and queue, count, median close.

    The median is what a resident can expect, so it uses resident sources only, unless the
    type has too few resident requests for that to be stable.
    """
    rows = []
    for request_type, group in df.groupby("request_type"):
        department = group["department"].mode().iloc[0]
        queue = group.loc[group["department"] == department, "queue"].mode().iloc[0]
        resident = group[group["source"].isin(RESIDENT_SOURCES)]
        basis = resident if len(resident) >= MIN_RESIDENT_REQUESTS else group
        rows.append(
            {
                "request_type": request_type,
                "department": department,
                "queue": queue,
                "requests": len(group),
                "median_days_to_close": round(basis["close_days"].median(), 1),
            }
        )
    return pd.DataFrame(rows).sort_values("requests", ascending=False)


def query_service_stats(
    metric: Metric,
    group_by: GroupBy,
    filters: dict[str, str | int] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Rows of {group_by: value, metric: value} from the service-stats table, sorted.

    filters keys: department, request_type, neighborhood, source, year.
    Months come back in calendar order, everything else largest first. Requests with no
    value for group_by (e.g. no neighborhood) are left out.
    """
    filters = filters or {}
    # metric, group_by and filter keys are pasted into the SQL, so only known names pass
    if metric not in METRIC_SQL:
        raise ValueError(f"unknown metric {metric!r}")
    if group_by not in get_args(GroupBy):
        raise ValueError(f"unknown group_by {group_by!r}")
    if unknown := set(filters) - FILTERS:
        raise ValueError(f"unknown filters {sorted(unknown)}")
    where = " AND ".join([f"{group_by} IS NOT NULL", *(f"{key} = ?" for key in filters)])
    order = "1" if group_by == "month" else "2 DESC NULLS LAST, 1"
    # a connection per call: duckdb's shared default connection is not thread-safe, and
    # the API runs requests on several threads
    with duckdb.connect() as con:
        rows = con.execute(
            f"""
            SELECT {group_by}, {METRIC_SQL[metric]} AS {metric}
            FROM read_parquet(?)
            WHERE {where}
            GROUP BY 1
            ORDER BY {order}
            LIMIT ?
            """,
            [str(SERVICE_STATS), *filters.values(), limit],
        ).fetchall()
    return [dict(zip((group_by, metric), row, strict=True)) for row in rows]
