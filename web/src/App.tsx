import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Outlet } from 'react-router'
import { getJson, type Schemas } from '@/api/client'
import { cn } from '@/lib/utils'

const pages = [
  { to: '/', label: 'Intake' },
  { to: '/plan', label: 'Crew plan' },
  { to: '/scenarios', label: 'Scenarios' },
  { to: '/ask', label: 'Ask' },
]

export default function App() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:bg-card focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl flex-col gap-x-10 px-4 pt-3 md:flex-row md:items-end md:px-6">
          <Link to="/" className="py-2 font-display text-lg font-bold md:pb-3">
            Boston 311 crew planner
          </Link>
          <nav aria-label="Main">
            <ul className="flex flex-wrap gap-x-6">
              {pages.map(({ to, label }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end
                    className={({ isActive }) =>
                      cn(
                        'inline-block whitespace-nowrap border-b-3 py-2 md:pb-3',
                        isActive
                          ? 'border-primary font-semibold text-foreground'
                          : 'border-transparent text-muted-foreground hover:text-foreground',
                      )
                    }
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 md:px-6">
        <Outlet />
      </main>
      <footer className="border-t">
        <div className="mx-auto max-w-6xl px-4 py-3 text-sm text-muted-foreground md:px-6">
          <HealthStatus />
        </div>
      </footer>
    </div>
  )
}

function HealthStatus() {
  const { data, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => getJson<Schemas['HealthResponse']>('/api/health'),
    retry: false,
  })
  // one live region that stays mounted, so screen readers announce each change
  return (
    <p role="status" className={cn(isError && 'text-destructive')}>
      {isError ? (
        <>
          Can’t reach the API. Start it with{' '}
          <code translate="no">uv run uvicorn boston311.api.main:app --reload</code>
        </>
      ) : data ? (
        <>
          <span aria-hidden="true" className="mr-2 inline-block size-2 rounded-full bg-foreground" />
          API {data.status}, model <span translate="no">{data.model}</span>
        </>
      ) : (
        'Checking API…'
      )}
    </p>
  )
}
