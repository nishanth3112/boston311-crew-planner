"""Solve every named scenario and write data/processed/plans.json, which /api/plan serves."""

import json

from boston311.planning.scenarios import PLANS_PATH, build_plans

plans = build_plans()
PLANS_PATH.write_text(json.dumps({k: p.model_dump() for k, p in plans.items()}, indent=2) + "\n")
for name, plan in plans.items():
    k = plan.kpis
    print(
        f"{name:16} total ${k.total_cost:>13,.0f}  on time {k.on_time_pct:.1%}  "
        f"(hold flat ${k.baseline_total_cost:>13,.0f}, {k.baseline_on_time_pct:.1%})"
    )
print(f"wrote {PLANS_PATH}")
