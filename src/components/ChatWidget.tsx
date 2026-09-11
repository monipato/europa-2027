import { useEffect, useRef, useState } from 'react'
import { MessageCircle, RotateCcw, Send, X } from 'lucide-react'
import { getChatSessionId, resetChatSessionId } from '../utils/chatSession'
import { setChatOpenListener } from '../utils/chatBus'

type ChatMessage = { sender: 'user' | 'ai'; body: string }

const FALLBACK_REPLY = 'Uy, tuve un problema respondiendo. ¿Puedes intentar de nuevo en un momento?'

/**
 * Gemini replies use light markdown (**bold**, *italic*) that showed up as
 * literal asterisks in a plain-text bubble. Renders just those two safely as
 * React elements — never dangerouslySetInnerHTML, since this is model
 * output — instead of pulling in a full markdown parser for two tags.
 * Newlines stay as plain "\n" characters in the text nodes; `.chat-bubble`'s
 * `white-space:pre-wrap` renders those as line breaks regardless of which
 * element they end up inside.
 */
function renderChatText(text: string): React.ReactNode[] {
  // A markdown bullet ("* item") isn't paired italic — swap it for a plain
  // bullet character first so the italic regex below never has to guess.
  const withBullets = text.replace(/^\*\s+/gm, '• ')
  const parts = withBullets.split(/(\*\*[^*]+\*\*|\*[^\s*][^*]*\*)/g)
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={index}>{part.slice(1, -1)}</em>
    }
    return part
  })
}

/**
 * The floating in-app chat: a fab that opens a panel talking to the same
 * Gemini-powered assistant the WhatsApp bot used
 * (`netlify/functions/chat.mts` → `_lib/tripContext.ts` + `_lib/gemini.ts`),
 * just over a plain fetch instead of WhatsApp. `contextMessage` pre-fills the
 * input the first time the panel opens on an empty conversation — same idea
 * as the old wa.me pre-filled text, just typed into a box instead of sent
 * straight to WhatsApp.
 */
export function ChatWidget({ contextMessage }: { contextMessage: string }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // Restore this session's saved conversation (see netlify/functions/chat-
  // history.mts) once on mount, so a page reload doesn't wipe the visible
  // chat — the backend already kept every message for AI context, this just
  // brings it back into view too.
  useEffect(() => {
    let cancelled = false
    fetch(`/api/chat-history?sessionId=${encodeURIComponent(getChatSessionId())}`)
      .then((res) => res.json())
      .then((data: { messages?: ChatMessage[] }) => {
        if (!cancelled && Array.isArray(data.messages) && data.messages.length > 0) {
          setMessages(data.messages)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setHistoryLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Auto-grow the input with its content (up to the CSS max-height, which
  // takes over with a scrollbar) — a fixed 1-row box was clipping longer
  // pre-filled context messages instead of showing them in full.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [input])

  useEffect(() => {
    setChatOpenListener((message) => {
      setInput(message)
      setOpen(true)
    })
    return () => setChatOpenListener(null)
  }, [])

  // Only pre-fill from context once we know for sure there's no saved
  // history to restore instead (avoids a flash of the generic context
  // message right before real history loads in).
  useEffect(() => {
    if (open && historyLoaded && messages.length === 0 && input === '') {
      setInput(contextMessage)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, historyLoaded])

  function handleReset() {
    resetChatSessionId()
    setMessages([])
    setInput('')
    setHistoryLoaded(true)
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  async function handleSend() {
    const text = input.trim()
    if (!text || sending) return
    setMessages((prev) => [...prev, { sender: 'user', body: text }])
    setInput('')
    setSending(true)
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId: getChatSessionId(), message: text }),
      })
      const data = (await res.json()) as { reply?: string }
      setMessages((prev) => [...prev, { sender: 'ai', body: data.reply || FALLBACK_REPLY }])
    } catch {
      setMessages((prev) => [...prev, { sender: 'ai', body: FALLBACK_REPLY }])
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  return (
    <>
      {!open && (
        <button className="chat-fab" onClick={() => setOpen(true)} aria-label="Abrir chat con PatiTours">
          <MessageCircle size={26} />
        </button>
      )}

      {open && (
        <div className="chat-panel">
          <div className="chat-panel-header">
            <div>
              <strong>PatiTours</strong>
              <span>Asistente del viaje · IA</span>
            </div>
            <div className="chat-panel-header-actions">
              <button onClick={handleReset} aria-label="Reiniciar conversación" title="Reiniciar conversación">
                <RotateCcw size={18} />
              </button>
              <button onClick={() => setOpen(false)} aria-label="Cerrar chat">
                <X size={20} />
              </button>
            </div>
          </div>

          <div className="chat-messages">
            {messages.length === 0 && (
              <p className="chat-empty-hint">¡Hola! Pregúntame lo que quieras sobre el viaje: vuelos, hoteles, tours, precios o clima.</p>
            )}
            {messages.map((message, index) => (
              <div className={`chat-bubble ${message.sender}`} key={index}>
                {message.sender === 'ai' ? renderChatText(message.body) : message.body}
              </div>
            ))}
            {sending && <div className="chat-bubble ai chat-typing">Escribiendo…</div>}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-row">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Escribe tu pregunta…"
              rows={1}
            />
            <button onClick={handleSend} disabled={sending || !input.trim()} aria-label="Enviar mensaje">
              <Send size={18} />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
