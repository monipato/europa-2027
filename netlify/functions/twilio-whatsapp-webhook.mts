import type { Config } from '@netlify/functions'
import { ensureSchema, getOrCreateConversation, getRecentMessages, hasReachedDailyMessageCap, insertInboundMessage, insertOutboundMessage } from './_lib/db'
import { verifyTwilioSignature } from './_lib/twilio'
import { buildSystemPrompt } from './_lib/tripContext'
import { generateReply } from './_lib/gemini'

// The reply goes back as TwiML in the webhook response itself — Twilio then
// delivers it — instead of a separate call to the Messages REST resource.
// That REST call is what requires the account's compliance/KYC (Trust Hub)
// approval to send WhatsApp messages; replying via TwiML doesn't. Because the
// response body IS the reply, this can't be a background function (whose
// return value gets discarded) — it runs synchronously, which is fine since
// a Gemini flash-lite reply comfortably finishes inside Twilio's ~15s webhook
// timeout and Netlify's ~10s sync limit.
export const config: Config = {
  path: '/api/twilio-whatsapp-webhook',
  method: 'POST',
}

const FALLBACK_REPLY = '¡Hola! Recibimos tu mensaje, en un momento seguimos. 😊'
const DAILY_CAP_REPLY = 'Hemos hablado bastante hoy 😊 Para no perder detalle, sigamos la conversación en unas horas o mañana. ¡Gracias por tu paciencia!'

export default async (req: Request) => {
  const formData = await req.formData()
  const params: Record<string, string> = {}
  for (const [key, value] of formData.entries()) params[key] = String(value)

  const signature = req.headers.get('x-twilio-signature') ?? undefined
  if (!verifyTwilioSignature(req.url, params, signature)) {
    return new Response(null, { status: 401 })
  }

  const from = params.From // e.g. "whatsapp:+573001234567"
  const text = params.Body
  const messageSid = params.MessageSid
  const hasMedia = params.NumMedia && params.NumMedia !== '0'

  if (!from || !messageSid || !text || hasMedia) {
    // No usable text message (e.g. only media, or a malformed payload) — ack, no reply.
    return twimlReply('')
  }

  await ensureSchema()
  const conversation = await getOrCreateConversation(from)
  const isNew = await insertInboundMessage(conversation.id, messageSid, text)
  // Not new (Twilio retried this webhook) or the AI is paused for this
  // conversation (a human is handling it elsewhere) — ack without replying.
  if (!isNew || conversation.aiPaused) return twimlReply('')

  try {
    // Cost/abuse backstop — anyone can message the WhatsApp number with no
    // login, so this caps it per conversation instead of calling Gemini forever.
    if (await hasReachedDailyMessageCap(conversation.id)) {
      await insertOutboundMessage(conversation.id, 'ai', DAILY_CAP_REPLY)
      return twimlReply(DAILY_CAP_REPLY)
    }

    const history = await getRecentMessages(conversation.id, 20)
    const systemPrompt = buildSystemPrompt([...history.map((m) => m.body), text])
    const reply = await generateReply(systemPrompt, history, text)
    await insertOutboundMessage(conversation.id, 'ai', reply)
    return twimlReply(reply)
  } catch (err) {
    console.error('twilio-whatsapp-webhook: failed to generate reply', err)
    return twimlReply(FALLBACK_REPLY)
  }
}

function twimlReply(message: string): Response {
  const escaped = message
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
  const body = message ? `<Message>${escaped}</Message>` : ''
  return new Response(`<?xml version="1.0" encoding="UTF-8"?><Response>${body}</Response>`, {
    status: 200,
    headers: { 'Content-Type': 'text/xml' },
  })
}
