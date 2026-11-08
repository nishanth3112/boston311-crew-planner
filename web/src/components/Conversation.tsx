import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { postJson, type Schemas } from '@/api/client'

type ChatMessage = Schemas['ChatMessage']

// the API accepts at most 20 messages; a new question adds one more
const MAX_TURNS = 9

type Props<R> = {
  path: string
  /** What the assistant said, sent back as history on the next turn. */
  assistantText: (response: R) => string
  renderResponse: (response: R) => ReactNode
  renderEmpty: (send: (question: string) => void) => ReactNode
  assistantLabel: string
  inputLabel: string
  placeholder: string
  pendingText: string
}

const buttonBase = 'rounded-md px-4 py-2 font-display font-semibold'

type Turn<R> = { question: string; response: R }

export function Conversation<R>(props: Props<R>) {
  const queryClient = useQueryClient()
  const threadKey = ['conversation', props.path]
  // the thread lives in the query cache (memory only) so it survives leaving the page
  const { data: turns } = useQuery({
    queryKey: threadKey,
    queryFn: () => [] as Turn<R>[],
    initialData: [] as Turn<R>[],
    staleTime: Infinity,
    gcTime: Infinity,
  })
  const [draft, setDraft] = useState('')
  const mutation = useMutation({
    mutationFn: (messages: ChatMessage[]) => postJson<R>(props.path, { messages }),
    // set here, not in mutate(), so an answer that lands after the page is left is still kept
    onSuccess: (response, messages) =>
      queryClient.setQueryData<Turn<R>[]>(threadKey, (t = []) => [
        ...t,
        { question: messages[messages.length - 1].content, response },
      ]),
  })

  function send(question: string) {
    if (mutation.isPending) return
    const history = turns.flatMap(({ question, response }): ChatMessage[] => [
      { role: 'user', content: question },
      { role: 'assistant', content: props.assistantText(response).slice(0, 4000) || '(no reply)' },
    ])
    mutation.mutate([...history, { role: 'user', content: question }])
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const question = draft.trim()
    if (!question) return
    send(question)
    setDraft('')
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      e.currentTarget.form?.requestSubmit()
    }
  }

  function startOver() {
    queryClient.setQueryData<Turn<R>[]>(threadKey, [])
    mutation.reset()
  }

  const waiting = mutation.isPending || mutation.isError
  const waitingQuestion = waiting ? mutation.variables?.at(-1)?.content : undefined

  return (
    <div className="mt-6 max-w-2xl">
      {turns.length === 0 && !waiting && props.renderEmpty(send)}

      <ol className="space-y-8 break-words">
        {turns.map(({ question, response }, i) => (
          <li key={i}>
            <Said by="You">{question}</Said>
            <div className="mt-4">
              <p className="text-sm text-muted-foreground">{props.assistantLabel}</p>
              {props.renderResponse(response)}
            </div>
          </li>
        ))}
        {waitingQuestion && (
          <li>
            <Said by="You">{waitingQuestion}</Said>
          </li>
        )}
      </ol>

      <p role="status" className="mt-4 text-muted-foreground empty:mt-0">
        {mutation.isPending ? props.pendingText : ''}
      </p>
      {mutation.isError && (
        <div role="alert" className="mt-4">
          <p className="text-destructive">Couldn’t get an answer: {mutation.error.message}.</p>
          <button
            type="button"
            onClick={() => waitingQuestion && send(waitingQuestion)}
            className={`${buttonBase} mt-2 border hover:bg-muted`}
          >
            Try again
          </button>
        </div>
      )}

      {turns.length >= MAX_TURNS ? (
        <p className="mt-8">This conversation is full. Start a new one to keep going.</p>
      ) : (
        !mutation.isError && (
          <form onSubmit={onSubmit} className="mt-8">
            <label htmlFor="message" className="block text-sm text-muted-foreground">
              {props.inputLabel}
            </label>
            <textarea
              id="message"
              name="message"
              rows={3}
              maxLength={4000}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={props.placeholder}
              className="mt-1 block w-full rounded-md border border-input bg-card px-3 py-2"
            />
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <button type="submit" className={`${buttonBase} bg-primary text-primary-foreground hover:bg-primary/90`}>
                Send
              </button>
              <span className="text-sm text-muted-foreground">Enter to send, Shift+Enter for a new line</span>
            </div>
          </form>
        )
      )}
      {(turns.length > 0 || waiting) && (
        <button type="button" onClick={startOver} className={`${buttonBase} mt-4 border hover:bg-muted`}>
          New conversation
        </button>
      )}
    </div>
  )
}

function Said({ by, children }: { by: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-sm text-muted-foreground">{by}</p>
      <p className="whitespace-pre-wrap">{children}</p>
    </div>
  )
}
