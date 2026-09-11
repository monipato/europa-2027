import type { Config } from '@netlify/functions'
import { ensureSchema, findConversationBySession, getRecentMessages } from './_lib/db'

// Backend for restoring the in-app chat widget's history on page load —
// reads what's already stored for this session (see chat.mts), never
// creates or deletes anything.
export const config: Config = {
  path: '/api/chat-history',
  method: 'GET',
}

export default async (req: Request) => {
  const sessionId = new URL(req.url).searchParams.get('sessionId')?.trim()
  if (!sessionId) {
    return new Response(JSON.stringify({ error: 'missing_session_id' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
  }

  await ensureSchema()
  const conversation = await findConversationBySession(sessionId)
  if (!conversation) {
    return new Response(JSON.stringify({ messages: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }

  const history = await getRecentMessages(conversation.id, 50)
  const messages = history.map((m) => ({ sender: m.sender === 'customer' ? 'user' : 'ai', body: m.body }))
  return new Response(JSON.stringify({ messages }), { status: 200, headers: { 'Content-Type': 'application/json' } })
}
