"""Raw 311 CSV -> one row per request in the four departments."""

import html
from pathlib import Path

import duckdb
import pandas as pd

from boston311.config import DEPARTMENTS

SECONDS_PER_DAY = 86_400


def clean(path: Path) -> pd.DataFrame:
    """Requests of the four departments with parsed times (Boston local, as in the file).

    target_days is empty when the request has no sla_target_dt; close_days is empty while open.
    """
    df = duckdb.execute(
        f"""
        SELECT
            case_enquiry_id,
            open_dt::TIMESTAMP AS open_dt,
            sla_target_dt::TIMESTAMP AS sla_target_dt,
            closed_dt::TIMESTAMP AS closed_dt,
            strftime(open_dt::TIMESTAMP, '%Y-%m') AS month,
            on_time,
            case_status,
            case_title,
            type AS request_type,
            queue,
            department,
            neighborhood,
            source,
            date_diff('second', open_dt::TIMESTAMP, sla_target_dt::TIMESTAMP)
                / {SECONDS_PER_DAY} AS target_days,
            date_diff('second', open_dt::TIMESTAMP, closed_dt::TIMESTAMP)
                / {SECONDS_PER_DAY} AS close_days
        FROM read_csv(?, all_varchar = true)
        WHERE department IN (SELECT unnest(?))
        """,
        [str(path), list(DEPARTMENTS)],
    ).df()
    titles = df["case_title"].dropna().unique()
    df["case_title"] = df["case_title"].map({t: html.unescape(t) for t in titles})
    return df
