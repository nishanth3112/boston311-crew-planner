Analyst eval on `data/processed/analyst_dev_set.csv`, model `openai/gpt-oss-120b`

| questions | errors | right tools | right arguments | numbers verified | tool calls / q | max tool calls | LLM calls / q | uncached tokens / q |
|---|---|---|---|---|---|---|---|---|
| 10 | 0 | 10/10 | 19/19 | 36/40 | 1.1 | 2 | 2.1 | 3263.6 |

Per question

| id | tools | right tools | arguments | unverified | error |
|---|---|---|---|---|---|
| D01 | get_plan | True | 2/2 | 12 |  |
| D02 | run_what_if | True | 1/1 | 1.9 |  |
| D03 | query_service_stats, query_service_stats | True | 3/3 |  |  |
| D04 | get_forecast | True | 1/1 | $18.736 M |  |
| D05 | run_what_if | True | 1/1 |  |  |
| D06 | get_plan | True | 1/1 |  |  |
| D07 | get_plan | True | 2/2 | 29 |  |
| D08 | query_service_stats | True | 3/3 |  |  |
| D09 | run_what_if | True | 2/2 |  |  |
| D10 | query_service_stats | True | 3/3 |  |  |

Answers, to check against the expected facts

**D01** expected: 9 hires in total, in January, February and August; 18 crews in January, 27 in December

> Transportation hires 9 crews in the base plan — 3 in January, 5 in February and 1 in August (the hires array shows [3, 5, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0] for the 12 months). This comes from the base scenario get_plan output for BTDT.

**D02** expected: demand_plus_20 plan: Public Works 38 hires, 12 releases, peak 83 crews, $10.4M crew cost; whole plan $20.52M

> With a 20 % demand increase, Public Works would finish about **89.6 % of requests on time** (the “on_time_pct” in the totals), **spend roughly $10.4 M** and would need **38 hires and 12 releases** over the year, with a peak of **83 working crews** in February. Compared with the base plan, its on‑time rate falls by **1.9 percentage points**, cost rises by **$2.59 M**, hires increase by **22**, and releases go up by **10** (all figures from the what‑if run). Because the on‑time target of 90 % is not reached, the plan would be flagged as not meeting the target for Public Works (and also BTDT).

**D03** expected: 2024 medians: Chestnut Hill 2.9 days, Jamaica Plain 2.6, Allston / Brighton 1.9

> The neighborhoods with the longest median time to close pothole repairs in 2024 are Chestnut Hill (2.9 days) and Jamaica Plain (2.6 days), according to the 2024 311 service‑stats query for “Request for Pothole Repair.”

**D04** expected: 18,736 forecast for 2025, same as 2024 (seasonal naive); backtest error 17.4%

> The Parks & Recreation forecast for 2025 totals $18.736 M, exactly the same as the 2024 total (both $18.736 M), according to the forecast data. Its reliability is measured by a back‑test mean absolute percentage error of 0.1737, i.e., about 17.4 % error (the “seasonal_naive” method).

**D05** expected: target not met (Public Works and Transportation fall short): 94.5% on time overall at $20.9M, about $4.99M more than the base plan

> The custom run‑what‑if shows the plan cannot meet a 98 % on‑time target – the target is missed by the Public Works (PWDx) and Transportation (BTDT) departments. The whole‑plan cost for this scenario is $20.90 M (total_cost = 20899801) as returned by the run_what_if tool.

**D06** expected: base $15.91M at 92.1% on time against $21.05M at 25.5%; saves about $5.14M

> The base 2025 plan saves **$5.14 M** compared with the “hold‑flat” scenario that keeps the January crew levels for the whole year (saving_vs_hold_flat = 5,138,307 from the base plan).

**D07** expected: April 2, May 6, June 12, July 10, August 7, September 2; 39 seasonal crew-months

> Parks uses 12 seasonal crews in June, 10 in July and 7 in August, for a total of 29 seasonal crews over the summer months (from the base 2025 plan).

**D08** expected: Employee Generated 61.3% (49,948); City Worker App 0.3% (234)

> 61.3% of Transportation (BTDT) requests in 2024 were logged by city employees, according to the 2024 service‑stats query.

**D09** expected: no: 90.4% overall, but Public Works is at 88.9%, below 90%; $20.89M, about $4.99M more than the base plan

> The custom what‑if run (10 % higher demand with a snowstorm) shows an overall on‑time rate of 90.44 % (all_departments on_time_pct = 0.9044) but the Public Works (PWDx) department falls to 88.88 % on‑time, so the plan does **not** meet the 90 % target overall (target_met = false, departments_below_target = [“PWDx”])【run_what_if†result】.

**D10** expected: Carbon Monoxide 522.9 days, Sign Repair 409.3, Rental Unit Delivery Conditions 372.0

> The Inspectional Services request types with the longest median time to close in 2024 were Carbon Monoxide (523 days), Sign Repair (409 days), and Rental Unit Delivery Conditions (372 days), according to the 2024 service‑stats query.

