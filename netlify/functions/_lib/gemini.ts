import type { StoredMessage } from './db'

// An alias, not a pinned snapshot — Google keeps it pointed at the current
// lightweight Flash model, so it doesn't 404 again the next time a specific
// snapshot (e.g. gemini-2.5-flash) gets retired.
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-flash-lite-latest'
const FALLBACK_REPLY = 'Uy, tuve un problema respondiendo. ¿Puedes intentar de nuevo en un momento?'

/** One attempt at calling Gemini — returns the reply text, or throws (a
 * network failure, a non-2xx response, or an empty reply) so the retry
 * wrapper below can decide whether to try again. */
async function callGemini(apiKey: string, systemPrompt: string, contents: { role: string; parts: { text: string }[] }[]): Promise<string> {
  const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: systemPrompt }] },
      contents,
      // Left at the API default (~1.0) this is tuned for creative writing,
      // not for reliably repeating a price or a total back verbatim — a
      // lower temperature trades away some of the personality in the reply
      // for fewer slips on the numbers, which matters more here. A generous
      // but finite output cap is just a cost/abuse backstop, not a real
      // constraint — a WhatsApp reply is never anywhere near this long.
      generationConfig: { temperature: 0.3, maxOutputTokens: 1024 },
    }),
  })

  if (!res.ok) {
    const errorBody = await res.text()
    throw new Error(`Gemini API returned ${res.status}: ${errorBody}`)
  }

  const data = (await res.json()) as {
    candidates?: { content?: { parts?: { text?: string }[] } }[]
  }
  const text = data.candidates?.[0]?.content?.parts?.map((p) => p.text ?? '').join('').trim()
  if (!text) throw new Error('Gemini API returned an empty reply')
  return text
}

/**
 * Generates the assistant's reply for one WhatsApp turn. `history` is the
 * conversation so far (oldest first, excluding the new message), `systemPrompt`
 * is the trip catalog/context + conversation rules from tripContext.ts.
 *
 * A transient failure (a dropped connection, a momentary 5xx) shouldn't cost
 * the customer a whole turn just to have to say "no me contestaste" and ask
 * again — retries once, with a short pause, before giving up to the generic
 * fallback reply.
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

  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      return await callGemini(apiKey, systemPrompt, contents)
    } catch (err) {
      console.error(`generateReply: attempt ${attempt} failed:`, err)
      if (attempt === 1) await new Promise((resolve) => setTimeout(resolve, 500))
    }
  }
  return FALLBACK_REPLY
}
