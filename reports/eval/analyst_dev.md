Analyst eval on `data/processed/analyst_dev_set.csv`, model `openai/gpt-oss-20b`

| questions | errors | right tools | right arguments | numbers verified | tool calls / q | max tool calls | LLM calls / q | uncached tokens / q |
|---|---|---|---|---|---|---|---|---|
| 10 | 0 | 10/10 | 20/20 | 56/57 | 1.1 | 2 | 2.1 | 2541.0 |

Per question

| id | tools | right tools | arguments | unverified | error |
|---|---|---|---|---|---|
| D01 | get_plan | True | 2/2 |  |  |
| D02 | get_plan | True | 2/2 |  |  |
| D03 | query_service_stats, query_service_stats | True | 3/3 |  |  |
| D04 | get_forecast | True | 1/1 |  |  |
| D05 | run_what_if | True | 1/1 |  |  |
| D06 | get_plan | True | 1/1 |  |  |
| D07 | get_plan | True | 2/2 | 29 |  |
| D08 | query_service_stats | True | 3/3 |  |  |
| D09 | run_what_if | True | 2/2 |  |  |
| D10 | query_service_stats | True | 3/3 |  |  |

Answers, to check against the expected facts

**D01** expected: 9 hires in total, in January, February and August; 18 crews in January, 27 in December

> Transportation hires 9 crews in the base plan, with hires occurring in January (3 crews), February (5 crews), and August (1 crew). These hires are spread across the months listed in the plan: January, February, and August. The monthly crew counts for Transportation are 18 in January, 21 in February, and 26 from March through July, rising to 27 from September through December. All figures come from the base scenario of the 2025 plan.

**D02** expected: demand_plus_20 plan: Public Works 38 hires, 12 releases, peak 83 crews, $10.4M crew cost; whole plan $20.52M

> If demand rises 20 % above forecast, the Public Works plan would increase its peak working crews to 83 in February and add 33 hires in January, with a total of 38 hires and 12 releases over the year. The on‑time rate would climb to 90.6 % (up from 10.4 % in the baseline) and the total cost would be $20.52 M (versus $34.22 M in the baseline). These figures come from the “demand_plus_20” scenario in the get_plan tool.

**D03** expected: 2024 medians: Chestnut Hill 2.9 days, Jamaica Plain 2.6, Allston / Brighton 1.9

> The longest median wait for pothole repairs in 2024 was in Chestnut Hill, with 2.9 days, followed by Jamaica Plain at 2.6 days. Back Bay, Beacon Hill, and Brighton each had a median of 1.9 days, while Allston/Brighton and West Roxbury were at 1.8 days. These figures come from the 2024 PWDx service‑stats query for pothole requests.

**D04** expected: 18,736 forecast for 2025, same as 2024 (seasonal naive); backtest error 17.4%

> The Parks & Recreation forecast for 2025 is 18,736 requests, the same as the 2024 total, with a 0‑percent change versus last year (get_forecast). The forecast method is seasonal naive and the back‑test mean absolute percentage error is 17.4 % (get_forecast). This indicates a moderate level of reliability, with an 80 % prediction interval ranging from 670 to 1,186 requests in January and 603 to 1,069 in December.

**D05** expected: target not met: best is 94.5% on time at $20.9M, about $5.0M more than the base plan

> No, the 2025 plan cannot hit a 98 % on‑time target. Even with the most aggressive staffing scenario the on‑time rate tops out at 94.5 % (see the run_what_if result). The cost for that scenario would be about $20.9 million (total_cost from the run_what_if output).

**D06** expected: base $15.91M at 92.1% on time against $21.05M at 25.5%; saves about $5.14M

> The base plan costs $15.91 M, which is $5.14 M cheaper than keeping January crews flat all year (baseline cost $21.05 M). This savings comes from the “saving_vs_hold_flat” figure in the base plan KPIs.

**D07** expected: April 2, May 6, June 12, July 10, August 7, September 2; 39 seasonal crew-months

> Parks & Recreation deploys 12 seasonal crews in June, 10 in July and 7 in August, for a total of 29 seasonal crews over the summer (2025‑base plan).

**D08** expected: Employee Generated 61.3% (49,948); City Worker App 0.3% (234)

> About 61.3 % of Transportation (BTDT) requests in 2024 were logged by city employees, according to the 2024 311 service stats.

**D09** expected: yes: 90.4% on time at $20.89M, about $4.99M more than the base plan

> The custom scenario with a 10 % demand increase and a snowstorm still meets the 90 % on‑time target (target_met = true). The overall on‑time rate is 90.44 % (from the run_what_if result). The plan’s total cost rises to $20.9 M, a $4.99 M increase over the base plan, and overdue cost climbs to $540,988. The change from the base plan shows a 1.62 % drop in on‑time performance relative to the base, but it remains above the 90 % threshold.

**D10** expected: Carbon Monoxide 522.9 days, Sign Repair 409.3, Rental Unit Delivery Conditions 372.0

> The Inspectional Services department’s longest‑to‑close request types in 2024 were Carbon Monoxide (522.9 days), Sign Repair (409.3 days), Rental Unit Delivery Conditions (372.0 days), Plumbing (291.0 days), BWSC General Request (252.5 days), Mechanical (250.9 days), Empty Litter Basket (242.0 days), Poor Ventilation (228.3 days), Public Works General Request (194.0 days), and Roadway Repair (186.8 days). These figures come from the 2024 median days to close data returned by the query_service_stats tool.

