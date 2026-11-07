import pandas as pd
import pytest

from boston311.data import aggregate
from boston311.data.aggregate import query_service_stats, request_types, service_stats
from boston311.data.clean import clean

RAW = pd.DataFrame(
    {
        "case_enquiry_id": [1, 2, 3],
        "open_dt": ["2024-01-31 23:30:00", "2024-02-01 08:00:00", "2024-02-03 09:00:00"],
        "sla_target_dt": ["2024-02-02 23:30:00", None, None],
        "closed_dt": ["2024-02-01 11:30:00", None, None],
        "on_time": ["ONTIME"] * 3,
        "case_status": ["Closed", "Open", "Open"],
        "case_title": ["Pothole on A &amp; B St", "Needle Pickup", "Tree &lt;dead&gt;"],
        "type": ["Request for Pothole Repair", "Needle Pickup", "Tree Maintenance Requests"],
        "queue": ["PWDx_Pothole", "GEN_Needle_Pickup", "PARK_Forestry"],
        "department": ["PWDx", "GEN", "PARK"],
        "neighborhood": ["Dorchester", "Dorchester", "Roxbury"],
        "source": ["Citizens Connect App", "Constituent Call", "Constituent Call"],
    }
)


@pytest.fixture
def cleaned(tmp_path):
    path = tmp_path / "raw.csv"
    RAW.to_csv(path, index=False)
    return clean(path).set_index("case_enquiry_id")


def test_clean_keeps_only_the_four_departments(cleaned):
    assert list(cleaned.index) == ["1", "3"]


def test_clean_unescapes_titles(cleaned):
    assert cleaned.loc["1", "case_title"] == "Pothole on A & B St"
    assert cleaned.loc["3", "case_title"] == "Tree <dead>"


def test_clean_derives_days_and_month_from_open_dt(cleaned):
    assert cleaned.loc["1", "target_days"] == 2.0
    assert cleaned.loc["1", "close_days"] == 0.5
    assert cleaned.loc["1", "month"] == "2024-01"  # opened in January, closed in February
    assert pd.isna(cleaned.loc["3", "target_days"])  # no target: still a request
    assert pd.isna(cleaned.loc["3", "close_days"])  # still open


def test_on_time_rate_excludes_requests_without_a_target(tmp_path, monkeypatch):
    # PWDx in Dorchester: 4 requests, 3 with a target, 2 of those on time -> 2/3;
    # closed in 1.1, 2.3 and 4.0 days -> median 2.3 (not exact in float32).
    # Roxbury: on time but outside the PWDx filter. Last row: PWDx with no neighborhood.
    rows = pd.DataFrame(
        {
            "month": ["2024-01"] * 6,
            "department": ["PWDx"] * 4 + ["PARK", "PWDx"],
            "request_type": ["Pothole"] * 6,
            "neighborhood": ["Dorchester"] * 4 + ["Roxbury", None],
            "source": ["Constituent Call"] * 6,
            "on_time": ["ONTIME", "ONTIME", "OVERDUE", "ONTIME", "ONTIME", "OVERDUE"],
            "target_days": [2.0, 2.0, 2.0, None, 3.0, 2.0],
            "close_days": [1.1, 2.3, 4.0, None, 1.0, 9.0],
        }
    )
    path = tmp_path / "service_stats.parquet"
    service_stats(rows).to_parquet(path)
    monkeypatch.setattr(aggregate, "SERVICE_STATS", path)

    args = ("neighborhood", {"department": "PWDx", "year": 2024})
    assert query_service_stats("on_time_rate", *args) == [
        {"neighborhood": "Dorchester", "on_time_rate": 0.667}
    ]
    assert query_service_stats("request_count", *args) == [
        {"neighborhood": "Dorchester", "request_count": 4}
    ]
    assert query_service_stats("median_days_to_close", *args) == [
        {"neighborhood": "Dorchester", "median_days_to_close": 2.3}
    ]


def test_request_type_median_falls_back_to_all_sources():
    # Pothole: 30 resident requests closed in 1 day, 40 employee ones in 5 -> residents: 1.0.
    # Signs: 29 resident requests in 1 day, 40 employee ones in 5 -> too few, all sources: 5.0.
    def requests(request_type, source, n, close_days):
        return pd.DataFrame(
            {
                "request_type": [request_type] * n,
                "department": ["PWDx"] * n,
                "queue": ["PWDx_Queue"] * n,
                "source": [source] * n,
                "close_days": [close_days] * n,
            }
        )

    df = pd.concat(
        [
            requests("Pothole", "Constituent Call", 30, 1.0),
            requests("Pothole", "Employee Generated", 40, 5.0),
            requests("Signs", "Citizens Connect App", 29, 1.0),
            requests("Signs", "Employee Generated", 40, 5.0),
        ]
    )
    medians = request_types(df).set_index("request_type")["median_days_to_close"]
    assert medians.to_dict() == {"Pothole": 1.0, "Signs": 5.0}


def test_query_rejects_unknown_filters():
    with pytest.raises(ValueError, match="borough"):
        query_service_stats("request_count", "source", {"borough": "x"})
