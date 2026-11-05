"""Write openapi.json at the repo root; the web app generates its TypeScript types from it."""

import json

from boston311.api.main import app
from boston311.config import ROOT

path = ROOT / "openapi.json"
path.write_text(json.dumps(app.openapi(), indent=2) + "\n")
print(f"wrote {path}")
