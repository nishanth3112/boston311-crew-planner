# Boston 311 Crew Planner

A month-by-month 2025 staffing plan for four City of Boston departments, built from real 311 service request data, plus a GenAI intake assistant that routes a resident's plain-language report to the right request type and department queue.

IE 5374 Hackathon · Northeastern University · Team of 3

> **Status:** in progress. Setup instructions, results and the architecture diagram will be added here as each piece is merged.

## The problem

Boston 311 received 306,756 service requests in 2024. Demand is seasonal (Public Works peaks in August and September; Parks more than triples between January and June), and on-time performance varies widely by department. We decide how many field crews each of four departments should have in each month of 2025, trading crew cost against on-time service under the hiring, release and seasonal-crew rules below.

## Departments in scope

| Department | Code | 2024 requests | On time, 2024 | Crew capacity (requests/day) | Annual cost per crew | Crews, Jan 2025 |
|---|---|---|---|---|---|---|
| Public Works | PWDx | 157,610 | 90% | 12 | $130,000 | 50 |
| Transportation (parking & traffic) | BTDT | 81,447 | 50% | 15 | $110,000 | 18 |
| Parks & Recreation | PARK | 18,736 | 93% | 6 | $120,000 | 10 |
| Inspectional Services | ISD | 18,624 | 72% | 4 | $140,000 | 16 |

Request counts and on-time rates come from the real data. Crew capacities, costs and starting crew levels are planning assumptions set by the hackathon brief.

### Planning rules (from the brief)

- A crew works 21 days a month and closes up to its daily capacity each day.
- New crews need one month of hiring and training before they start.
- Releasing a crew needs one month's notice and costs 25% of its annual cost.
- Parks may add seasonal crews from April to October at 1.3× the monthly cost, with no training delay and no release cost.
- Each overdue request costs $20, and a request still open 30 days after its target date costs an extra $100.

## What we're building

1. **Demand forecast:** monthly 2025 requests per department from 2023–2024 data, backtested and checked against January–September 2025 actuals.
2. **Staffing optimizer:** a mixed-integer model that sets crews, hires, releases and Parks seasonal crews for each month.
3. **Queue simulator:** replays a year of requests day by day to measure the on-time rate and overdue cost of any plan.
4. **Sensitivity analysis:** demand 20% above and below forecast, a snowstorm and a heat wave, each tested with a re-optimized plan and with the base plan held fixed.
5. **311 intake assistant:** retrieves the closest real request types for a resident's message and returns type, department and queue as structured output, asking a follow-up question when the message is unclear. Accuracy is measured on a hand-written test set.
6. **Web app:** a React + Vite + TypeScript app with four screens (intake, crew plan, scenarios and "ask the plan"), served by a FastAPI backend.

## Data

Public 311 service requests from [Analyze Boston](https://data.boston.gov/dataset/311-service-requests): the 2023 and 2024 files for modeling and the 2025 file for validation. The raw CSVs are too large for GitHub and are **not committed**; a download script will fetch them into `data/raw/`.

## Tech stack (planned)

Backend: Python 3.12, uv, FastAPI, DuckDB, PuLP (CBC), statsmodels, LangChain, Pydantic, pytest, ruff. Frontend: React + Vite + TypeScript. CI: GitHub Actions.

## Getting started

Full instructions are coming. Dependencies are managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Copy `.env.example` to `.env` and add your own free `GROQ_API_KEY` from console.groq.com/keys. The intake endpoint (`/api/intake`) needs it, and returns an error without a key or when Groq's free-tier rate limit is reached.

## How we work

- `main` is protected: every change goes through a pull request, gets one approving review from a teammate, and is squash-merged.
- Branch names are short and plain, one per ticket, such as `backend-setup` or `intake-agent`.
- Raw data, `.env` files and API keys are never committed.

## Team

| Member | GitHub | Focus |
|---|---|---|
| Nishanth Manoharan | [@nishanth3112](https://github.com/nishanth3112) | to be assigned |
| Ramgopal Reddy Alumalla | [@ramg-0903](https://github.com/ramg-0903) | to be assigned |
| Aryan Patil | [@Aryan16d](https://github.com/Aryan16d) | to be assigned |

Each member's contributions will be listed here before submission.
