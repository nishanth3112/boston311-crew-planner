import type { components } from './schema'

export type Schemas = components['schemas']

/** A response with an error status, so the UI can say what went wrong. */
export class ApiError extends Error {
  status: number
  detail?: string
  constructor(path: string, status: number, detail?: unknown) {
    super(`${path} returned ${status}`)
    this.status = status
    if (typeof detail === 'string') this.detail = detail // 422s carry a list, not a message
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
  if (!res.ok) throw new ApiError(path, res.status, (await res.json().catch(() => null))?.detail)
  return res.json() as Promise<T>
}

/** What failed and what to do next, for an error from postJson or getJson. */
export function errorMessage(error: Error): string {
  // the API's own 503s say whether the AI service is busy or down; the proxy's 502-504 don't
  if (error instanceof ApiError && error.status === 503 && error.detail) return error.detail
  // fetch throws a TypeError when the server can't be reached; Vite's proxy answers 502-504
  if (!(error instanceof ApiError) || error.status >= 502) {
    return 'Couldn’t reach the planner service. Check that the API is running, then try again.'
  }
  if (error.status === 422) return 'That message couldn’t be sent. Try a shorter one.'
  return 'The assistant couldn’t answer just now. The AI service may be busy, so wait a minute and try again.'
}
