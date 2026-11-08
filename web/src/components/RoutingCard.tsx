import type { Schemas } from '@/api/client'

type RoutedRequest = Schemas['RoutedRequest']

const DEPARTMENTS: Record<RoutedRequest['department'], string> = {
  PWDx: 'Public Works',
  BTDT: 'Transportation',
  PARK: 'Parks and Recreation',
  ISD: 'Inspectional Services',
}

function closeTime(days: number) {
  if (days < 1) return 'Under a day'
  const n = Math.round(days)
  return `About ${n} ${n === 1 ? 'day' : 'days'}`
}

export function RoutingCard({ request }: { request: RoutedRequest }) {
  return (
    <article className="rounded-md border bg-card p-4">
      <h2 className="text-lg">{request.request_type}</h2>
      <p className="mt-1">{request.details}</p>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt className="text-muted-foreground">Department</dt>
        <dd>{DEPARTMENTS[request.department]}</dd>
        <dt className="text-muted-foreground">Queue</dt>
        <dd translate="no" className="min-w-0 break-words">
          {request.queue}
        </dd>
        {request.location && (
          <>
            <dt className="text-muted-foreground">Location</dt>
            <dd className="min-w-0 break-words">{request.location}</dd>
          </>
        )}
        {request.typical_days_to_close != null && (
          <>
            <dt className="text-muted-foreground">Usually closed in</dt>
            <dd className="num">{closeTime(request.typical_days_to_close)}</dd>
          </>
        )}
      </dl>
    </article>
  )
}
