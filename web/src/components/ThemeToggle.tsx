import { useState } from 'react'

/** Switches between the light theme (default) and the dark one built from the same tokens. */
export function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))

  function toggle() {
    const next = !dark
    document.documentElement.classList.toggle('dark', next)
    try {
      localStorage.setItem('theme', next ? 'dark' : 'light')
    } catch {
      // storage can be blocked; the theme still applies for this visit
    }
    setDark(next)
  }

  return (
    <button
      type="button"
      aria-pressed={dark}
      onClick={toggle}
      className="rounded-md border px-3 py-1 text-sm text-muted-foreground hover:text-foreground"
    >
      Dark theme
    </button>
  )
}
