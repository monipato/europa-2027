import type { StoredMessage } from './db'

const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash'
const FALLBACK_REPLY = 'Uy, tuve un problema respondiendo. ¿Puedes intentar de nuevo en un momento?'

/**
 * Generates the assistant's reply for one WhatsApp turn. `history` is the
 * conversation so far (oldest first, excluding the new message), `systemPrompt`
 * is the trip catalog/context + conversation rules from tripContext.ts.
 */
export async function generateReply(systemPrompt: string, history: StoredMessage[], userMessage: string): Promise<string> {
  const apiKey = process.env.GEMINI_API_KEY
  if (!apiKey) {
    console.error('generateReply: missing GEMINI_API_KEY')
    return FALLBACK_REPLY
  }

  const contents = [
    ...history.map((m) => ({
      role: m.sender === 'customer' ? 'user' : 'model',
      parts: [{ text: m.body }],
    })),
    { role: 'user', parts: [{ text: userMessage }] },
  ]

  const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: systemPrompt }] },
      contents,
    }),
  })

  if (!res.ok) {
    const errorBody = await res.text()
    console.error(`generateReply: Gemini API returned ${res.status}: ${errorBody}`)
    return FALLBACK_REPLY
  }

  const data = (await res.json()) as {
    candidates?: { content?: { parts?: { text?: string }[] } }[]
  }
  const text = data.candidates?.[0]?.content?.parts?.map((p) => p.text ?? '').join('').trim()
  return text || FALLBACK_REPLY
}
