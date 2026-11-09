import { expect, test } from 'vitest'
import { ApiError, errorMessage } from './client'

test("a 503 from the API shows the server's message", () => {
  expect(errorMessage(new ApiError('/api/ask', 503, 'The assistant is busy right now.'))).toBe(
    'The assistant is busy right now.',
  )
})

test('a 503 without a message, like a proxy error, still says the service is unreachable', () => {
  expect(errorMessage(new ApiError('/api/ask', 503))).toMatch(/Couldn’t reach the planner service/)
  expect(errorMessage(new ApiError('/api/ask', 422, [{ msg: 'too long' }]))).toMatch(/shorter/)
})
