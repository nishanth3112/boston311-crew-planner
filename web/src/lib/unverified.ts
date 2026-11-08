export type Segment = { text: string; unverified: boolean }

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Split text so each listed number stands alone, e.g. to mark "$12,400,000" in an answer. */
export function markUnverified(text: string, numbers: string[]): Segment[] {
  const alternatives = numbers
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map(escape)
  if (alternatives.length === 0) return [{ text, unverified: false }]
  // the lookarounds stop a match inside a longer number, e.g. 12,400 inside 12,400,000
  const pattern = new RegExp(`(?<!\\d[.,]?)(${alternatives.join('|')})(?![.,]?\\d)`)
  return text
    .split(pattern)
    .map((part, i) => ({ text: part, unverified: i % 2 === 1 }))
    .filter((s) => s.text)
}
