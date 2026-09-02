import type { Config } from '@netlify/functions'
import { ensureSchema, getOrCreateConversation, getRecentMessages, insertInboundMessage, insertOutboundMessage } from './_lib/db'
import { verifyMetaSignature, sendMetaWhatsAppMessage } from './_lib/meta'
import { buildSystemPrompt } from './_lib/tripContext'
import { generateReply } from './_lib/gemini'

// Not a background function: Meta's one-time webhook verification (GET) needs
// a real synchronous response echoing back hub.challenge, which a background
// function (always 202, return value discarded) can't provide. So POST also
// runs synchronously — fine in practice, since a Gemini flash reply + one
// Graph API call comfortably finish inside Netlify's ~10s sync limit.
export const config: Config = {
  path: '/api/whatsapp-webhook',
  method: ['GET', 'POST'],
}

export default async (req: Request) => {
  if (req.method === 'GET') return handleVerification(req)
  return handleIncoming(req)
}

function handleVerification(req: Request): Response {
  const url = new URL(req.url)
  const mode = url.searchParams.get('hub.mode')
  const token = url.searchParams.get('hub.verify_token')
  const challenge = url.searchParams.get('hub.challenge')

  if (mode === 'subscribe' && token === process.env.WHATSAPP_VERIFY_TOKEN) {
    return new Response(challenge ?? '', { status: 200 })
  }
  return new Response(null, { status: 403 })
}

async function handleIncoming(req: Request): Promise<Response> {
  const rawBody = await req.text()

  const appSecret = process.env.WHATSAPP_APP_SECRET
  if (appSecret) {
    const signature = req.headers.get('x-hub-signature-256')
    if (!verifyMetaSignature(rawBody, signature, appSecret)) {
      return new Response(null, { status: 401 })
    }
  }

  let payload: unknown
  try {
    payload = JSON.parse(rawBody)
  } catch {
    return Response.json({ ok: true })
  }

  const message = extractMessage(payload)
  if (!message || message.type !== 'text' || !message.text?.body) {
    // Delivery/read receipts, non-text messages, etc. — nothing to do.
    return Response.json({ ok: true })
  }

  const from = message.from
  const text = message.text.body
  const waMessageId = message.id

  await ensureSchema()
  const conversation = await getOrCreateConversation(from)
  const isNew = await insertInboundMessage(conversation.id, waMessageId, text)

  if (isNew && !conversation.aiPaused) {
    try {
      const history = await getRecentMessages(conversation.id, 20)
      const systemPrompt = buildSystemPrompt()
      const reply = await generateReply(systemPrompt, history, text)

      await sendMetaWhatsAppMessage(from, reply)
      await insertOutboundMessage(conversation.id, 'ai', reply)
    } catch (err) {
      console.error('whatsapp-webhook: failed to generate/send reply', err)
    }
  }

  return Response.json({ ok: true })
}

type WhatsAppMessage = { from: string; id: string; type: string; text?: { body: string } }

function extractMessage(payload: unknown): WhatsAppMessage | null {
  const value = (payload as any)?.entry?.[0]?.changes?.[0]?.value
  return value?.messages?.[0] ?? null
}
