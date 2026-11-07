import type { components } from './schema'

export type Schemas = components['schemas']

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${path} returned ${res.status}`)
  return res.json() as Promise<T>
}
