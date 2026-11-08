export type Segment = { text: string; unverified: boolean }

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Split text so each listed number stands alone, e.g. to mark "$12,400,000" in an answer. */
export function markUnverified(text: string, numbers: string[]): Segment[] {
  const alternatives = numbers
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map(escape)
  if (alternatives.length === 0) return [{ text, unverified: false }]
  // the lookarounds stop a match inside a longer number (12,400 inside 12,400,000) or a
  // different quantity: a flagged 9 is not the 9 in $9, 9% or 9M
  const pattern = new RegExp(
    `(?<![\\d$][.,]?)(${alternatives.join('|')})(?![.,]?\\d|\\s?(?:%|[MKmk]\\b|million|thousand|billion))`,
  )
  return text
    .split(pattern)
    .map((part, i) => ({ text: part, unverified: i % 2 === 1 }))
    .filter((s) => s.text)
}
