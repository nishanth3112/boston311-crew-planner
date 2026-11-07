"""Fetch the yearly 311 CSVs from Analyze Boston (CKAN) into data/raw/."""

import json
import shutil
import urllib.request
from pathlib import Path

from boston311.config import RAW_DIR

RESOURCE_SHOW = "https://data.boston.gov/api/3/action/resource_show?id="

# Old-system yearly files. 2025 covers January to September: the city moved to a new
# system with different columns in October 2025, and that file is not used.
RESOURCES = {
    2023: "e6013a93-1321-4f2a-bf91-8d8a02f1e62f",
    2024: "dff4d804-5031-443a-8409-8344efd0e5c8",
    2025: "9d7c2214-4709-478a-a2e8-fb2020a5bb94",
}


class _SignedUrlRedirect(urllib.request.HTTPRedirectHandler):
    # CKAN redirects to a signed S3 URL with an explicit ":443"; urllib then sends
    # "Host: s3.amazonaws.com:443", which no longer matches the signature (403)
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        newurl = newurl.replace(":443/", "/", 1)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_open = urllib.request.build_opener(_SignedUrlRedirect).open


def raw_path(year: int) -> Path:
    return RAW_DIR / f"311_{year}.csv"


def download(year: int) -> Path:
    """Download one year's CSV unless it is already there; returns its path."""
    path = raw_path(year)
    if path.exists():
        return path
    with urllib.request.urlopen(RESOURCE_SHOW + RESOURCES[year]) as response:
        resource = json.load(response)["result"]
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with _open(resource["url"]) as response, part.open("wb") as f:
        shutil.copyfileobj(response, f, 1 << 20)
    if resource.get("size") and part.stat().st_size != resource["size"]:
        raise RuntimeError(
            f"{year}: got {part.stat().st_size} bytes, CKAN lists {resource['size']}"
        )
    part.rename(path)
    return path
