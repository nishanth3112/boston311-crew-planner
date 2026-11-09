# Staffing Boston's 311 city service teams: analysis report

IE 5374 hackathon. Nishanth Manoharan, Ramgopal Reddy Alumalla, Aryan Patil. Every number below comes from `notebooks/311_staffing_submission.ipynb`, which runs end to end on a clean kernel.

> **AI use: to be confirmed with the team.** The brief (section 7) asks us to explain how we used AI tools and to mark AI-generated sections. The wording will be agreed by Nishanth, Aryan and Ram before submission.

## Summary

For 2025 we recommend growing Public Works from 50 to 64 crews, Transportation from 18 to 27 and Inspectional Services from 16 to 22, and growing Parks from 10 to 11 crews plus up to 12 seasonal crews in summer. The plan costs **$15.91M** and closes **92.1%** of requests on time, against **$21.05M** and **25.5%** if January's crews are held all year. Every department reaches the 90% target. The plan's weak points are demand well above the forecast and a winter storm in Public Works, so it should be re-planned monthly rather than fixed for the year.

## 1. Data and forecast

- We used every 2023-2024 request in the four departments. The 2024 counts match the brief exactly: Public Works 157,610, Transportation 81,447, Parks 18,736, Inspectional Services 18,624.
- On-time rates leave out requests with no target date, which gives 2024 baselines of 87.3% (Public Works), 48.9% (Transportation), 93.0% (Parks) and 72.3% (Inspectional Services).
- **Forecast.** Each department uses the method with the lowest backtest error on July-December 2024: damped ETS for Public Works (3.8% MAPE), seasonal naive scaled by growth for Transportation (4.8%), and seasonal naive for Parks (17.4%) and Inspectional Services (11.9%). The 2025 totals are 157,828, 88,079, 18,736 and 18,624.
- **The forecast ran high.** Against January-September 2025, actual requests were 84%, 93%, 76% and 95% of the forecast. For Public Works and Parks the drop came with a change in how requests arrived: Public Works phone requests fell to 47% of 2024's level. The data alone doesn't say whether the work itself fell. Transportation's requests held steady; its gap comes from the forecast carrying 2024's growth of about 8% into 2025. The 80% interval is too narrow: it held only 1 of 9 months for Public Works.

## 2. The staffing plan

A small mixed-integer program per department picks crews, hires, releases and Parks seasonal crews at least cost. A day-by-day simulation of 2025 then scores the plan, and each month's capacity buffer is raised until the department is 90% on time.

| Department | January crews | December crews | Hires | Releases | Seasonal crew-months | On time | On time, held flat |
|---|---|---|---|---|---|---|---|
| Public Works | 50 | 64 | 16 | 2 | 0 | 91.5% | 27.1% |
| Transportation | 18 | 27 | 9 | 0 | 0 | 90.0% | 8.0% |
| Parks & Recreation | 10 | 11 | 1 | 0 | 39 | 99.6% | 63.4% |
| Inspectional Services | 16 | 22 | 9 | 3 | 0 | 97.8% | 66.1% |
| All | 94 | 124 | 35 | 5 | 39 | 92.1% | 25.5% |

Public Works peaks at 66 crews in August and Parks at 12 seasonal crews in June. The notebook's section 5.1 has the month-by-month table, with each hire and release.

## 3. Decisions and assumptions

1. **Workload is every request in the four departments**, including the 53% logged by city staff.
2. **On-time is a target, not a cost.** A crew costs $42.99 (Public Works), $29.10 (Transportation), $79.37 (Parks) and $138.89 (Inspectional Services) per request it can close. That is more than the $20 penalty for a late request in every department, so a plan that only minimized cost would let requests run late. Hiring becomes cheaper only once requests reach 30 days past their target ($120 in penalties), and for Inspectional Services not even then. So each department is held to 90% on time.
3. **Timing follows the brief:**
   - hires are paid in the month they're made and work from the next
   - releases work out their notice month and cost 25% of a year's pay
   - seasonal Parks crews work April to October at 1.3 times the cost
   - January crews are fixed at the brief's levels, and December's crews cover January's forecast
4. **The simulation, not the optimizer, reports cost and on-time.** Crews work weekdays, requests arrive daily and are handled in arrival order, and each day's requests are split across target windows by their 2024 shares.
5. **The AI picks only the request type;** department and queue come from a lookup table.

## 4. Cost and on-time impact

| | 2025 plan | January crews held flat |
|---|---|---|
| Crew cost | $15.51M | $11.92M |
| Overdue penalties | $0.40M | $9.13M |
| Total cost | $15.91M | $21.05M |
| On time | 92.1% | 25.5% |

Spending $3.59M more on crews cuts overdue penalties by $8.73M. Holding January's crews fails because three departments start the year below demand: with no hiring, the backlog grows all year. Real departments would absorb some of this with overtime, which the model leaves out.

## 5. Sensitivity

Each scenario is simulated twice: with the base plan's crews held fixed, and re-planned for that demand.

| Scenario | Held fixed: total cost | Held fixed: on time | Re-planned: total cost | Re-planned: on time |
|---|---|---|---|---|
| Demand +20% | $27.21M | 14.8% | $20.52M | 90.6% |
| Demand -20% | $15.64M | 96.7% | $13.05M | 96.5% |
| Snowstorm (Feb 3-9) | $17.69M | 57.5% | $17.88M | 91.4% |
| Heat wave (Jul 14-20) | $15.96M | 91.0% | $16.13M | 91.9% |
| 2025 as it happened | $15.66M | 96.6% | $13.98M | 96.1% |

- **Demand 20% above forecast breaks a fixed plan.** With the base crews, $11.70M goes to overdue penalties. Re-planning restores 90.6%, with Public Works (89.6%) and Transportation (89.8%) just short of 90%.
- **A one-week snowstorm is the biggest risk from a short event.** With the base crews, Public Works falls to 30.9% on time for the year, because it has almost no spare capacity and the February backlog never clears. Transportation drops to 80.8%. The re-planned response hires 39 Public Works crews in January and releases 33 after February.
- **Lower demand is safe;** re-planning for it just saves money ($2.59M at 20% below forecast).
- **Higher targets buy little.** Targets from 80% to 88% give the same $15.90M plan at 91.9%. Above 92%, Public Works and Transportation can't reach the target: 98% costs $20.90M for 94.5%.

## 6. Equity and request sources

- **Transportation has the widest neighborhood gap:** 35% of West Roxbury requests closed on time in 2024, against 62% in South Boston. Inspectional Services ranges from 62% to 78%, Public Works from 77% to 91%, and Parks from 89% to 98%.
- **Close times vary most in Parks:** a median of 12.4 days in Hyde Park, against 1.0 day in its fastest neighborhood.
- **Staff-logged requests are on time more often than residents' in every department,** and they make up half the workload. In Parks, resident demand is more seasonal (4.7 times its low month, against 3.3 for staff), but staff log more requests overall, so both groups drive the summer peak.

We recommend tracking on-time rates by neighborhood alongside the plan, starting with Transportation.

## 7. The AI assistants

**Intake assistant** (45 held-out messages, `gpt-oss-120b`):

| | Single-call pipeline | Agent |
|---|---|---|
| Request type correct | 31/41 | 33/41 |
| Department correct | 34/41 | 37/41 |
| Multi-problem messages split | 4/6 | 6/6 |
| Out of scope caught | 2/3 | 3/3 |
| Follow-up asked when needed | 2/8 | 0/8 |
| Uncached tokens per message | 614.3 | 1303.9 |

The agent routes and splits better, but it never asks a follow-up question, and it fell back to the pipeline on 12 of 45 messages.

**Planning analyst** (10 development questions, `gpt-oss-120b`):
- It used the right tools on 10/10 questions and the right arguments on 19/19.
- 36 of 40 numbers in its answers were verified against tool results. The server flags the rest, and the app underlines them.

**Planning analyst** (15 held-out questions, `gpt-oss-120b`): right tools on 14/15 questions and right arguments on 25/28. 53 of 56 numbers were verified, with 0 errors. That is close to the development results, so the agent wasn't tuned to its own questions.

## 8. Limitations

- The simulation has no randomness: one outcome per plan, not a range.
- The planner is a heuristic, not an exact optimum. For example, a 92% target came out slightly cheaper than 90%.
- Crews are the only lever: no overtime, contractors or priority rules.
- The forecast ran high in 2025, and its interval is too narrow.
- The intake agent doesn't ask follow-up questions.
- District-routed request types show a single district queue.

## 9. Recommendations

1. Adopt the plan, but **re-plan monthly** as demand comes in. Re-planning for 2025's actual demand, if it had been known from January, would have saved up to $1.68M.
2. **Give Public Works winter slack or a storm-response plan,** since a short storm hits it hardest.
3. **Set neighborhood on-time goals,** starting with Transportation.
4. **Use the intake agent for multi-problem messages,** and add a clarifying-question step before relying on it for ambiguous ones.
