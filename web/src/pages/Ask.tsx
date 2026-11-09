import { Link } from 'react-router'
import type { Schemas } from '@/api/client'
import { Conversation } from '@/components/Conversation'
import { ToolTrace } from '@/components/ToolTrace'
import { markUnverified } from '@/lib/unverified'

type AskResponse = Schemas['AskResponse']

// questions the tools answer directly, so every number in the answer can be verified
const SUGGESTIONS = [
  'How much does the base plan cost Transportation in 2025?',
  'In which months does Inspectional Services hire new crews?',
  'How does the 2025 Transportation forecast compare with 2024?',
  'What share of 2024 requests came in through the Citizens Connect app?',
]

function scenarioLink({ demand_multiplier, shock, on_time_target }: Schemas['SolveRequest']) {
  const params = new URLSearchParams({
    demand_multiplier: String(demand_multiplier),
    shock: String(shock),
    on_time_target: String(on_time_target),
  })
  return `/scenarios?${params}`
}

export default function Ask() {
  return (
    <>
      <h1>Ask</h1>
      <p className="mt-3 text-muted-foreground">Ask questions about the forecast, the crew plan and past service levels.</p>
      <Conversation<AskResponse>
        path="/api/ask"
        assistantText={(r) => r.answer}
        assistantLabel="Planning analyst"
        inputLabel="Your question"
        placeholder="Ask about crews, costs or on-time rates…"
        pendingText="Working on it…"
        submitLabel="Ask"
        renderEmpty={(send) => (
          <>
            <p>Try one of these, or write your own below.</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((q) => (
                <li key={q}>
                  <button
                    type="button"
                    onClick={() => send(q)}
                    className="rounded-md border bg-card px-3 py-2 text-left hover:bg-muted"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        renderResponse={(r) => (
          <>
            <p>
              {markUnverified(r.answer, r.unverified_numbers).map((s, i) =>
                s.unverified ? (
                  <mark
                    key={i}
                    className="bg-transparent text-inherit underline decoration-unverified decoration-3 underline-offset-4"
                  >
                    {s.text}
                    <span className="sr-only"> (not verified)</span>
                  </mark>
                ) : (
                  s.text
                ),
              )}
            </p>
            {r.unverified_numbers.length > 0 && (
              <p className="mt-2 text-sm text-muted-foreground">
                Underlined numbers didn’t come from any tool result: {r.unverified_numbers.join(', ')}.
              </p>
            )}
            {r.what_if && (
              <Link
                to={scenarioLink(r.what_if)}
                className="mt-4 inline-block rounded-md bg-primary px-4 py-2 font-display font-semibold text-primary-foreground hover:bg-primary/90"
              >
                Open in Scenarios
              </Link>
            )}
            <ToolTrace trace={r.trace} label="Used" />
          </>
        )}
      />
    </>
  )
}
