from typing import Literal

from boston311.api.fixtures import load_fixture_rows

Metric = Literal["request_count", "on_time_rate", "median_days_to_close"]
GroupBy = Literal["neighborhood", "request_type", "source", "month"]


def query_service_stats(
    metric: Metric,
    group_by: GroupBy,
    filters: dict[str, str | int] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Rows of {group_by: value, metric: value} from the service-stats table, sorted.

    filters keys: department, request_type, neighborhood, source, year.
    """
    # stub: BOS-2 replaces this body
    return load_fixture_rows("service_stats")[:limit]
