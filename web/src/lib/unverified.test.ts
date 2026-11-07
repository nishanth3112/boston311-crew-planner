import { expect, test } from 'vitest'
import { markUnverified } from './unverified'

const marked = (text: string, numbers: string[]) =>
  markUnverified(text, numbers)
    .filter((s) => s.unverified)
    .map((s) => s.text)

test('marks a number with $ and commas', () => {
  expect(markUnverified('Total cost rises to $12,400,000.', ['$12,400,000'])).toEqual([
    { text: 'Total cost rises to ', unverified: false },
    { text: '$12,400,000', unverified: true },
    { text: '.', unverified: false },
  ])
})

test('marks every occurrence of the same number', () => {
  expect(marked('$12,400,000 now, $12,400,000 later', ['$12,400,000'])).toEqual([
    '$12,400,000',
    '$12,400,000',
  ])
})

test('does not mark a number inside a longer one', () => {
  expect(marked('Cost is $12,400,000 for 12,400 requests.', ['12,400'])).toEqual(['12,400'])
  expect(marked('Cost is $12,400,000 for 12,400 requests.', ['12,400', '$12,400,000'])).toEqual([
    '$12,400,000',
    '12,400',
  ])
})

test('leaves text alone when nothing is unverified', () => {
  expect(markUnverified('All good.', [])).toEqual([{ text: 'All good.', unverified: false }])
})
