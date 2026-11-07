"""Download the 2023, 2024 and 2025 (January to September) 311 files into data/raw/."""

from boston311.data.download import RESOURCES, download

for year in RESOURCES:
    path = download(year)
    print(f"{year}: {path} ({path.stat().st_size / 1e6:.0f} MB)")
