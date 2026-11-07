"""Clean the raw 311 files and write the small files in data/processed/."""

import pandas as pd

from boston311.config import DEPARTMENTS, INTERIM_DIR, PROCESSED_DIR
from boston311.data import aggregate
from boston311.data.clean import clean
from boston311.data.download import raw_path

years = {year: clean(raw_path(year)) for year in (2023, 2024, 2025)}
# the old system's 2025 file runs on to December, but from October most requests went to
# the new system, so its October-December counts are partial
years[2025] = years[2025][years[2025]["month"] <= "2025-09"]
INTERIM_DIR.mkdir(parents=True, exist_ok=True)
for year, df in years.items():
    df.to_parquet(INTERIM_DIR / f"clean_{year}.parquet")

model = pd.concat([years[2023], years[2024]], ignore_index=True)
latest = years[2024]

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
# 2025 (January to September) is only for checking the forecast, so it only enters monthly demand
aggregate.monthly_demand(pd.concat(years.values())).to_csv(
    PROCESSED_DIR / "monthly_demand.csv", index=False
)
aggregate.daily_profile(model).to_csv(PROCESSED_DIR / "daily_profile.csv", index=False)
aggregate.sla_profile(latest).to_csv(PROCESSED_DIR / "sla_profile.csv", index=False)
aggregate.request_types(latest).to_csv(PROCESSED_DIR / "request_types.csv", index=False)
aggregate.service_stats(model).to_parquet(aggregate.SERVICE_STATS, index=False, compression="zstd")

counts = latest["department"].value_counts()
for code, dept in DEPARTMENTS.items():
    print(f"{code}: {counts[code]:,} requests in 2024 (brief: {dept['requests_2024']:,})")
for year, df in years.items():
    print(f"{year}: {df['case_enquiry_id'].duplicated().sum()} duplicate case ids")
for path in sorted(PROCESSED_DIR.iterdir()):
    print(f"{path.name}: {path.stat().st_size / 1e6:.2f} MB")
