import type { components } from './schema'

export type Schemas = components['schemas']

/** A response with an error status, so the UI can say what went wrong. */
export class ApiError extends Error {
  status: number
  constructor(path: string, status: number) {
    super(`${path} returned ${status}`)
    this.status = status
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new ApiError(path, res.status)
  return res.json() as Promise<T>
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(path, res.status)
  return res.json() as Promise<T>
}

/** What failed and what to do next, for an error from postJson or getJson. */
export function errorMessage(error: Error): string {
  // fetch throws a TypeError when the server can't be reached; Vite's proxy answers 502-504
  if (!(error instanceof ApiError) || error.status >= 502) {
    return 'Couldn’t reach the planner service. Check that the API is running, then try again.'
  }
  if (error.status === 422) return 'That message couldn’t be sent. Try a shorter one.'
  return 'The assistant couldn’t answer just now. The AI service may be busy, so wait a minute and try again.'
}
