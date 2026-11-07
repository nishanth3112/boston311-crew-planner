import type { Schemas } from '@/api/client'
import { Conversation } from '@/components/Conversation'
import { RoutingCard } from '@/components/RoutingCard'
import { ToolTrace } from '@/components/ToolTrace'

type IntakeResponse = Schemas['IntakeResponse']

export default function Intake() {
  return (
    <>
      <h1>Intake</h1>
      <p className="mt-3 text-muted-foreground">Describe a problem in your own words and get the matching 311 request type, department and queue.</p>
      <Conversation<IntakeResponse>
        path="/api/intake"
        assistantText={(r) => [r.reply, r.follow_up_question].filter(Boolean).join(' ')}
        assistantLabel="311 assistant"
        inputLabel="Your message"
        placeholder="What’s wrong, and where is it?"
        pendingText="Routing your message…"
        renderEmpty={() => (
          <p>Write it the way you’d tell a 311 operator. If there’s more than one problem, put them all in one message.</p>
        )}
        renderResponse={(r) => (
          <>
            <p>{r.reply}</p>
            {r.requests.length > 0 && (
              <ul className="mt-4 space-y-3">
                {r.requests.map((request, i) => (
                  <li key={i}>
                    <RoutingCard request={request} />
                  </li>
                ))}
              </ul>
            )}
            {r.follow_up_question && <p className="mt-4 font-semibold">{r.follow_up_question}</p>}
            {r.fallback_used && (
              <p className="mt-4 text-sm text-muted-foreground">Routed by the simpler backup matcher because the assistant didn’t answer.</p>
            )}
            <ToolTrace trace={r.trace} />
          </>
        )}
      />
    </>
  )
}
