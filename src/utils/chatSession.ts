const STORAGE_KEY = 'patitours-chat-session-id'

/** Stable per-browser id so the AI chat backend can keep conversation
 * history across messages (and page reloads) without any login — generated
 * once and cached in localStorage. */
export function getChatSessionId(): string {
  try {
    const existing = localStorage.getItem(STORAGE_KEY)
    if (existing) return existing
    const id = crypto.randomUUID()
    localStorage.setItem(STORAGE_KEY, id)
    return id
  } catch {
    // localStorage unavailable (private mode, etc.) — fall back to a
    // session-only id so chat still works, just without cross-reload memory.
    return crypto.randomUUID()
  }
}

/** "Reiniciar conversación" — starts a brand-new session id so the widget
 * begins a fresh conversation. The old conversation is never deleted from
 * the database, just abandoned; its history stays there under its old
 * session id if it's ever needed again. */
export function resetChatSessionId(): string {
  const id = crypto.randomUUID()
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch {
    // Nothing to persist — the fallback id above still lets chat continue.
  }
  return id
}
