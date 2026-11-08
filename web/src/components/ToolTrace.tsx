import type { Schemas } from '@/api/client'

/** The agent's steps in plain words, e.g. "How this was routed: searched request types for 2
 * problems; looked up 2 request types", expanding to each step's tool and arguments. */
export function ToolTrace({ trace, label }: { trace: Schemas['ToolTraceStep'][]; label: string }) {
  if (trace.length === 0) return null
  const steps = trace.map((step, i) => (i === 0 ? step.summary : lowerFirst(step.summary)))
  return (
    <details className="mt-4 text-sm">
      <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
        {label}: {steps.join('; ')}
      </summary>
      <ol className="mt-2 space-y-2 border-l pl-4">
        {trace.map((step, i) => (
          <li key={i}>
            <code translate="no" className="font-semibold">
              {step.tool}
            </code>
            <p translate="no" className="break-words text-muted-foreground">
              {Object.entries(step.args)
                .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
                .join(', ') || 'no arguments'}
            </p>
          </li>
        ))}
      </ol>
    </details>
  )
}

function lowerFirst(text: string) {
  return text.charAt(0).toLowerCase() + text.slice(1)
}
