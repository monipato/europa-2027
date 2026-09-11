import type { Config } from '@netlify/functions'
import { ensureSchema, getOrCreateConversationBySession, getRecentMessages, insertInboundMessage, insertOutboundMessage } from './_lib/db'
import { buildSystemPrompt } from './_lib/tripContext'
import { generateReply } from './_lib/gemini'

// Backend for the in-app chat widget (`src/components/ChatWidget.tsx`) —
// the same Gemini-powered assistant + trip context the WhatsApp bot
// (twilio-whatsapp-webhook.mts) uses, just answering a plain JSON POST
// instead of a Twilio webhook. A Gemini flash-lite reply comfortably
// finishes inside Netlify's ~10s sync limit, so this stays a normal
// (non-background) function like the webhook.
export const config: Config = {
  path: '/api/chat',
  method: 'POST',
}

const FALLBACK_REPLY = 'Uy, tuve un problema respondiendo. ¿Puedes intentar de nuevo en un momento?'

export default async (req: Request) => {
  let body: { sessionId?: string; message?: string }
  try {
    body = await req.json()
  } catch {
    return jsonResponse({ error: 'invalid_json' }, 400)
  }

  const sessionId = body.sessionId?.trim()
  const message = body.message?.trim()
  if (!sessionId || !message) {
    return jsonResponse({ error: 'missing_fields' }, 400)
  }

  await ensureSchema()
  const conversation = await getOrCreateConversationBySession(sessionId)

  try {
    const history = await getRecentMessages(conversation.id, 20)
    await insertInboundMessage(conversation.id, crypto.randomUUID(), message)
    const systemPrompt = buildSystemPrompt()
    const reply = await generateReply(systemPrompt, history, message)
    await insertOutboundMessage(conversation.id, 'ai', reply)
    return jsonResponse({ reply })
  } catch (err) {
    console.error('chat: failed to generate reply', err)
    return jsonResponse({ reply: FALLBACK_REPLY })
  }
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
}
