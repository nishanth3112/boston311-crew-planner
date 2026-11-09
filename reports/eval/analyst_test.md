Analyst eval on `data/processed/analyst_test_set.csv`, model `openai/gpt-oss-120b`

| questions | errors | right tools | right arguments | numbers verified | tool calls / q | max tool calls | LLM calls / q | uncached tokens / q |
|---|---|---|---|---|---|---|---|---|
| 15 | 0 | 14/15 | 25/28 | 53/56 | 1.1 | 2 | 2.1 | 2541.5 |

Per question

| id | tools | right tools | arguments | unverified | error |
|---|---|---|---|---|---|
| A01 | run_what_if | False | 1/3 | $9.08 M |  |
| A02 | get_plan | True | 2/2 |  |  |
| A03 | get_plan | True | 2/2 |  |  |
| A04 | query_service_stats, query_service_stats | True | 3/4 |  |  |
| A05 | get_forecast | True | 1/1 |  |  |
| A06 | get_plan | True | 1/1 |  |  |
| A07 | run_what_if | True | 1/1 |  |  |
| A08 | query_service_stats | True | 3/3 |  |  |
| A09 | query_service_stats | True | 2/2 |  |  |
| A10 | run_what_if | True | 1/1 |  |  |
| A11 | get_forecast | True | 1/1 |  |  |
| A12 | get_plan | True | 1/1 |  |  |
| A13 | get_forecast | True | 1/1 |  |  |
| A14 | query_service_stats | True | 3/3 | 4.7% |  |
| A15 | get_plan | True | 2/2 | 95 % |  |

Answers, to check against the expected facts

**A01** expected: Transportation 19 hires (all January), releases 3 in February and 2 in March, peak 37 crews, 89.8% on time (below 90%), $3.77M vs $2.86M base (+$0.91M)

> With a 20 % demand increase, the Transportation (BTDT) department would see its on‑time performance dip slightly to **89.8 %** (down 0.25 percentage points from the base plan) and its annual cost rise by **$9.08 M** to **$3.77 M** total (the plan’s “cost” total for BTDT). These figures come from the what‑if run with a demand multiplier of 1.2 for BTDT.

**A02** expected: 66 crews in August (after 10 hires in July)

> Public Works has 66 crews in August 2025 in the base plan (see the “crews” list for August in the base‑plan output).

**A03** expected: seasonal crews April 2, May 6, June 12, July 10, August 7, September 2; 39 seasonal crew-months

> Parks hires its seasonal crews during the spring and summer months: 2 crews in April, 6 in May, 12 in June, 10 in July, 7 in August and 2 in September, for a total of 39 seasonal‑crew‑months (from the base 2025 plan).

**A04** expected: 2024 medians: Chestnut Hill 2.9 days, Jamaica Plain 2.6, Back Bay / Beacon Hill / Brighton 1.9

> The neighborhoods with the longest median time to close pothole repairs in 2024 are Chestnut Hill (2.9 days) and Jamaica Plain (2.6 days), according to the 2024 311 service‑stats query for “Request for Pothole Repair.”

**A05** expected: 1,796 requests in July 2025 (80% interval 1,464 to 2,128)

> The July 2025 forecast for Inspectional Services is 1,796 requests (from the get_forecast output for ISD).

**A06** expected: base $15.91M at 92.1% on time vs hold-flat $21.05M at 25.5%; saves about $5.14M

> The base 2025 plan costs about $15.91 million, while the “hold‑flat” scenario that keeps January crews unchanged would cost roughly $21.05 million, giving a saving of about $5.14 million by using the base plan (all figures from the base‑scenario plan).

**A07** expected: yes: 91.4% on time overall, every department at 90% or more (Public Works 90.0%); $17.88M, about $1.97M more than base; Public Works hires 39 in January, peaks at 89 crews in February

> The snow‑storm scenario still meets the 90 % on‑time target – `target_met` is true and no department falls below the target. Across all four departments the plan costs $17.88 M, achieves an overall on‑time rate of 91.4 % and saves $7.04 M versus the “hold‑flat” baseline (all figures from the snowstorm scenario returned by **run_what_if**).

**A08** expected: Transportation 48.9%; then Inspectional Services 72.3%, Public Works 87.3%, Parks 93.0%

> BTDT Transportation had the lowest on‑time rate in 2024, at 48.9% (from the 2024 311 service‑stats query).

**A09** expected: employee sources are Employee Generated and City Worker App; medians Employee Generated 0.5 days, City Worker App 0.1 vs Constituent Call 1.9, Self Service 0.7, Citizens Connect App 0.5 (employee sources faster or equal in every comparison)

> In 2024 the median time to close a request that came from a city employee (the “Employee Generated” source) was 0.5 days, and the median for the “City Worker App” (also employee‑driven) was just 0.1 days. By contrast, the fastest resident‑originated channel, “Constituent Call,” took 1.9 days on average. These figures come from the 2024 311 service‑stats query showing median days to close by source.

**A10** expected: 95% not reached: Transportation 93.4% at $4.02M vs $2.86M base (+$1.16M); Public Works also short at 93.7%; whole plan $17.55M, about $1.64M more than base

> The custom run‑what‑if shows that even with the 95 % on‑time target, Transportation (BTDT) would still fall short, ending at an on‑time rate of 93.4 % and costing $4.02 M for the year (both figures come from the “custom” plan output). Because the target isn’t met, the overall plan also fails to hit 95 % on‑time, with BTDT and PWDx listed as departments below target.

**A11** expected: seasonal naive, backtest error (MAPE) 17.4%

> The back‑test for the Parks forecast had a mean‑absolute‑percentage‑error of 0.1737, which is 17.4 % (from the get_forecast output for Parks).

**A12** expected: Public Works releases 5 in January and 2 in August; Parks 1 in January and 1 in September; Inspectional Services 2 in August; Transportation none; $13.05M, $2.86M less than base

> With a 20 % demand drop the plan shows releases in four departments:

* **Public Works (PWDx)** releases 5 crews in January and 2 crews in August.  
* **Parks & Recreation (PARK)** releases 1 crew in January and 1 crew in September.  
* **Inspectional Services (ISD)** releases 2 crews in August.  
* **Transportation (BTDT)** does not release any crews.  

These release numbers and months come directly from the “releases” series in the demand‑minus‑20 scenario of the 2025 crew plan.

**A13** expected: August, 16,425 requests (then September 15,940)

> The forecast shows the highest Public Works request volume in August 2025, with a projected 16,425 requests (from the get_forecast output).

**A14** expected: Rodent Activity 4,673 (25.1%), Unsatisfactory Living Conditions 2,368 (12.7%), Pest Infestation - Residential 1,824 (9.8%)

> The top request types for Inspectional Services in 2024 are Rodent Activity (4,673 requests, 25.1% share), Unsatisfactory Living Conditions (2,368 requests, 12.7% share), Pest Infestation – Residential (1,824 requests, 9.8% share), Work without Permit (893 requests, 4.8% share) and Contractors Complaint (866 requests, 4.7% share), all from the 2024 service‑stats query.

**A15** expected: Parks July seasonal crews 15 vs 10 in base, 44 seasonal crew-months vs 39; on time 98.5% vs 99.6% (95.9% in July and August); $1.88M vs $1.82M

> In the heat‑wave scenario, Parks & Recreation keeps a steady core crew of 10‑11 workers each month and adds a total of 44 seasonal crew‑months (peaking at 15 in July), compared with the baseline “hold‑flat” plan that has no seasonal crews.  The simulated on‑time performance rises to an overall 98.5 % on‑time rate (the monthly rates stay above 95 % and are 99.7 % in most months), up from the baseline on‑time rate of 25.3 % (the “hold‑flat” figure shown in the plan).  All these figures come from the heat‑wave scenario of the 2025 Parks plan.

