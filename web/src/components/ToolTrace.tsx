import type { Schemas } from '@/api/client'

export function ToolTrace({ trace }: { trace: Schemas['ToolTraceStep'][] }) {
  if (trace.length === 0) return null
  return (
    <details className="mt-4 text-sm">
      <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
        {trace.length} tool {trace.length === 1 ? 'call' : 'calls'}
      </summary>
      <ol className="mt-2 space-y-2 border-l pl-4">
        {trace.map((step, i) => (
          <li key={i}>
            <p>
              <code translate="no" className="font-semibold">
                {step.tool}
              </code>{' '}
              {step.summary}
            </p>
            <p translate="no" className="break-words text-muted-foreground">
              {Object.entries(step.args)
                .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
                .join(', ')}
            </p>
          </li>
        ))}
      </ol>
    </details>
  )
}
