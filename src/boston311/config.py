"""Constants from the hackathon brief, plus data paths."""

from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
CACHE_DIR = DATA_DIR / "cache"
PROCESSED_DIR = DATA_DIR / "processed"

DEFAULT_LLM_MODEL = "openai/gpt-oss-20b"

DEPARTMENTS = {
    "PWDx": {
        "name": "Public Works",
        "requests_2024": 157_610,
        "on_time_2024": 0.90,
        "requests_per_crew_day": 12,
        "annual_cost": 130_000,
        "jan_crews": 50,
    },
    "BTDT": {
        "name": "Transportation",
        "requests_2024": 81_447,
        "on_time_2024": 0.50,
        "requests_per_crew_day": 15,
        "annual_cost": 110_000,
        "jan_crews": 18,
    },
    "PARK": {
        "name": "Parks & Recreation",
        "requests_2024": 18_736,
        "on_time_2024": 0.93,
        "requests_per_crew_day": 6,
        "annual_cost": 120_000,
        "jan_crews": 10,
    },
    "ISD": {
        "name": "Inspectional Services",
        "requests_2024": 18_624,
        "on_time_2024": 0.72,
        "requests_per_crew_day": 4,
        "annual_cost": 140_000,
        "jan_crews": 16,
    },
}

WORK_DAYS_PER_MONTH = 21
HIRE_LEAD_MONTHS = 1  # hired in t (paid, training), works from t+1
RELEASE_NOTICE_MONTHS = 1  # notice in t, works t, gone from t+1, fee charged in t
RELEASE_FEE_SHARE = 0.25  # of annual cost
SEASONAL_DEPT = "PARK"
SEASONAL_MONTHS = range(4, 11)  # April to October
SEASONAL_COST_MULTIPLIER = 1.3
OVERDUE_PENALTY = 20
LATE_30_DAYS_PENALTY = 100  # extra, if still open 30 days past target


def monthly_capacity(code: str, crews: float) -> float:
    return crews * DEPARTMENTS[code]["requests_per_crew_day"] * WORK_DAYS_PER_MONTH


def monthly_crew_cost(code: str) -> float:
    return DEPARTMENTS[code]["annual_cost"] / 12
