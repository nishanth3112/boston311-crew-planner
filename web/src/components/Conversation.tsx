import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { errorMessage, postJson, type Schemas } from '@/api/client'

type ChatMessage = Schemas['ChatMessage']

// the API accepts at most 20 messages: after 9 turns (18 messages) a 10th question still
// fits (19), and after 10 the next one (21) wouldn't
const MAX_TURNS = 10

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
  /** The send button, named for what it does ("Send report", "Ask"). */
  submitLabel: string
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
  const input = useRef<HTMLTextAreaElement>(null)
  const mutation = useMutation({
    mutationFn: (messages: ChatMessage[]) => postJson<R>(props.path, { messages }),
    // set here, not in mutate(), so an answer that lands after the page is left is still kept
    onSuccess: (response, messages) =>
      queryClient.setQueryData<Turn<R>[]>(threadKey, (t = []) => [
        ...t,
        { question: messages[messages.length - 1].content, response },
      ]),
    // put the question back in the box, so it can be shortened or sent again
    onError: (_error, messages) => setDraft((d) => d || messages[messages.length - 1].content),
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
    if (!question || mutation.isPending) return // keep the draft while an answer is pending
    send(question)
    setDraft('')
  }

  function retry(question: string) {
    send(question)
    setDraft('')
    input.current?.focus() // the Try again button goes away
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
    // the New conversation button goes away; wait for the box to render (it may have been
    // replaced by the "conversation is full" note)
    setTimeout(() => input.current?.focus())
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

      {/* one live region that stays mounted: it says when an answer is on its way and when it
          arrives (the arrival only for screen readers) */}
      <p role="status" className={mutation.isPending ? 'mt-4 text-muted-foreground' : 'sr-only'}>
        {mutation.isPending ? props.pendingText : mutation.isSuccess ? 'Answer received.' : ''}
      </p>
      {mutation.isError && (
        <div role="alert" className="mt-4">
          <p className="text-destructive">{errorMessage(mutation.error)}</p>
          <button
            type="button"
            onClick={() => waitingQuestion && retry(waitingQuestion)}
            className={`${buttonBase} mt-2 border hover:bg-muted`}
          >
            Try again
          </button>
        </div>
      )}

      {turns.length >= MAX_TURNS ? (
        <p className="mt-8">This conversation is full. Start a new one to keep going.</p>
      ) : (
        <form onSubmit={onSubmit} className="mt-8">
          <label htmlFor="message" className="block text-sm text-muted-foreground">
            {props.inputLabel}
          </label>
          <textarea
            ref={input}
            id="message"
            name="message"
            aria-describedby="message-hint"
            autoComplete="off"
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
              {props.submitLabel}
            </button>
            <span id="message-hint" className="text-sm text-muted-foreground">
              Enter sends, Shift+Enter adds a new line
            </span>
          </div>
        </form>
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
