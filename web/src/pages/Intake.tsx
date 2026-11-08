import type { Schemas } from '@/api/client'
import { Conversation } from '@/components/Conversation'
import { RoutingCard } from '@/components/RoutingCard'
import { ToolTrace } from '@/components/ToolTrace'

type IntakeResponse = Schemas['IntakeResponse']

const COUNT = ['No', 'One', 'Two', 'Three', 'Four', 'Five']

export default function Intake() {
  return (
    <>
      <h1>Intake</h1>
      <p className="mt-3 text-muted-foreground">Describe a problem in your own words and get the matching 311 request type, department and queue.</p>
      <Conversation<IntakeResponse>
        path="/api/intake"
        assistantText={(r) => [r.reply, r.follow_up_question].filter(Boolean).join(' ')}
        assistantLabel="311 assistant"
        inputLabel="What’s the problem, and where is it?"
        placeholder="For example: there’s a deep pothole on Centre St near the T stop"
        pendingText="Routing your report…"
        submitLabel="Send report"
        renderEmpty={() => (
          <p>Write it the way you’d tell a 311 operator. If there’s more than one problem, put them all in one message.</p>
        )}
        renderResponse={(r) => (
          <>
            <p>{r.reply}</p>
            {r.requests.length > 0 && (
              <>
                <p className="mt-4 font-semibold">
                  {COUNT[r.requests.length] ?? r.requests.length} {r.requests.length === 1 ? 'request' : 'requests'} filed
                </p>
                <ol className="mt-2 space-y-3">
                  {r.requests.map((request, i) => (
                    <li key={i} className="flex gap-3">
                      <span aria-hidden="true" className="num pt-4 font-display text-lg font-bold">
                        {i + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <RoutingCard request={request} />
                      </div>
                    </li>
                  ))}
                </ol>
              </>
            )}
            {r.follow_up_question && <p className="mt-4 font-semibold">{r.follow_up_question}</p>}
            {r.out_of_scope && (
              <p className="mt-4 text-sm text-muted-foreground">
                Nothing was filed: this isn’t handled by Public Works, Transportation, Parks or Inspectional Services.
              </p>
            )}
            {r.fallback_used && (
              <p className="mt-4 text-sm text-muted-foreground">Routed by the simpler backup matcher because the assistant didn’t answer.</p>
            )}
            <ToolTrace trace={r.trace} label="How this was routed" />
          </>
        )}
      />
    </>
  )
}
