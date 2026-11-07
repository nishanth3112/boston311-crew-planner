import pytest

from boston311.config import DEPARTMENTS, monthly_capacity


@pytest.mark.parametrize(
    ("code", "expected"),
    [("PWDx", 12_600), ("BTDT", 5_670), ("PARK", 1_260), ("ISD", 1_344)],
)
def test_january_monthly_capacity(code, expected):
    assert monthly_capacity(code, DEPARTMENTS[code]["jan_crews"]) == expected
