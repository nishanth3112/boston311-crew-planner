Analyst eval on `data/processed/analyst_dev_set.csv`, model `openai/gpt-oss-20b`

| questions | errors | right tools | right arguments | numbers verified | tool calls / q | max tool calls | LLM calls / q | uncached tokens / q |
|---|---|---|---|---|---|---|---|---|
| 10 | 0 | 10/10 | 20/20 | 51/54 | 1.1 | 2 | 2.1 | 2432.8 |

Per question

| id | tools | right tools | arguments | unverified | error |
|---|---|---|---|---|---|
| D01 | get_plan | True | 2/2 |  |  |
| D02 | get_plan | True | 2/2 |  |  |
| D03 | query_service_stats, query_service_stats | True | 3/3 |  |  |
| D04 | get_forecast | True | 1/1 | 1,548 |  |
| D05 | run_what_if | True | 1/1 |  |  |
| D06 | get_plan | True | 1/1 |  |  |
| D07 | get_plan | True | 2/2 | 29 |  |
| D08 | query_service_stats | True | 3/3 |  |  |
| D09 | run_what_if | True | 2/2 | 90.6 % |  |
| D10 | query_service_stats | True | 3/3 |  |  |

Answers, to check against the expected facts

**D01** expected: 9 hires in total, in January, February and August; 18 crews in January, 27 in December

> Transportation hires 9 crews in the base plan, with hires in January (3), February (5), and August (1). These numbers come from the BTDT department data in the base plan.

**D02** expected: demand_plus_20 plan: Public Works 38 hires, 12 releases, peak 83 crews, $10.4M crew cost; whole plan $20.52M

> If demand rises 20 % above forecast, the Public Works plan would add 38 hires and 12 releases, raising the yearly cost to $20.52 M (from $34.22 M in the baseline) and improving the on‑time rate to 90.6 % (up from 10.4 % in the baseline). The plan would still meet the 90 % on‑time target, with peak crews of 83 and a January crew count of 50. These figures come from the “demand_plus_20” scenario in the get_plan tool.

**D03** expected: 2024 medians: Chestnut Hill 2.9 days, Jamaica Plain 2.6, Allston / Brighton 1.9

> The longest median wait for pothole repairs in 2024 was in Chestnut Hill, with 2.9 days, followed by Jamaica Plain at 2.6 days. Back Bay, Beacon Hill, and Brighton each had a median of 1.9 days, while Allston/Brighton and West Roxbury were at 1.8 days. These figures come from the 2024 311 service stats for the PWDx department.

**D04** expected: 18,736 forecast for 2025, same as 2024 (seasonal naive); backtest error 17.4%

> The Parks & Recreation forecast for 2025 is 18,736 requests, the same as the 2024 total, so the change is 0.0 % (from the forecast data). The model used is seasonal‑naive with an 80 % prediction interval of 670–1,186 in January and 1,548–2,740 in August, and a back‑test MAPE of 17.4 % (from the forecast result). This indicates a moderate level of reliability, with the forecast’s error rate around 17 %.

**D05** expected: target not met (Public Works and Transportation fall short): 94.5% on time overall at $20.9M, about $4.99M more than the base plan

> The 98 % on‑time target cannot be met; the plan falls short for PWDx and BTDT. Re‑solving the plan for a 98 % target adds about $4.99 M in total cost (from the base plan) and improves the overall on‑time rate by 2.44 % (the change_from_base). This cost figure comes from the run_what_if result.

**D06** expected: base $15.91M at 92.1% on time against $21.05M at 25.5%; saves about $5.14M

> The base plan saves $5.14 M compared to keeping January crews flat all year, as shown by the total_cost of $15.91 M versus the baseline_total_cost of $21.05 M in the base scenario.

**D07** expected: April 2, May 6, June 12, July 10, August 7, September 2; 39 seasonal crew-months

> Parks & Recreation deploys 12 seasonal crews in June, 10 in July, and 7 in August, for a total of 29 seasonal crews over the summer (2025‑base plan).

**D08** expected: Employee Generated 61.3% (49,948); City Worker App 0.3% (234)

> About 61.3 % of Transportation (BTDT) requests in 2024 were logged by city employees, according to the 2024 311 service‑stats data.

**D09** expected: no: 90.4% overall, but Public Works is at 88.9%, below 90%; $20.89M, about $4.99M more than the base plan

> The 2025 plan with a 10 % demand increase and a snowstorm does **not** meet the 90 % on‑time target; the overall on‑time rate falls to 88.9 % (from 90.6 % in the base plan) and Public Works is the only department below target. The plan still saves about $11.4 M versus holding January crews flat, but the cost rises by $4.99 M. These figures come from the run_what_if tool.

**D10** expected: Carbon Monoxide 522.9 days, Sign Repair 409.3, Rental Unit Delivery Conditions 372.0

> The Inspectional Services department’s longest‑to‑close request types in 2024 were Carbon Monoxide (522.9 days), Sign Repair (409.3 days), Rental Unit Delivery Conditions (372.0 days), Plumbing (291.0 days), BWSC General Request (252.5 days), Mechanical (250.9 days), Empty Litter Basket (242.0 days), Poor Ventilation (228.3 days), Public Works General Request (194.0 days), and Roadway Repair (186.8 days). These figures come from the 2024 median days to close data returned by the query_service_stats tool.

