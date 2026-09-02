import type { Config } from '@netlify/functions'
import { ensureSchema, getOrCreateConversation, getRecentMessages, insertInboundMessage, insertOutboundMessage } from './_lib/db'
import { verifyTwilioSignature, sendTwilioWhatsAppMessage } from './_lib/twilio'
import { buildSystemPrompt } from './_lib/tripContext'
import { generateReply } from './_lib/gemini'

// A background function: Netlify replies 202 to Twilio immediately (so Twilio
// never times out and retries) and runs this handler afterwards; its return
// value is discarded, so we do all the work — signature check included —
// straight through instead of splitting a fast ack from a slow background part.
export const config: Config = {
  path: '/api/twilio-whatsapp-webhook',
  method: 'POST',
  background: true,
}

export default async (req: Request) => {
  const formData = await req.formData()
  const params: Record<string, string> = {}
  for (const [key, value] of formData.entries()) params[key] = String(value)

  const signature = req.headers.get('x-twilio-signature') ?? undefined
  if (!verifyTwilioSignature(req.url, params, signature)) {
    console.error('twilio-whatsapp-webhook: invalid X-Twilio-Signature, dropping request')
    return
  }

  const from = params.From // e.g. "whatsapp:+573001234567"
  const text = params.Body
  const messageSid = params.MessageSid
  const hasMedia = params.NumMedia && params.NumMedia !== '0'

  if (!from || !messageSid || !text || hasMedia) {
    // No usable text message (e.g. only media, or a malformed payload) — nothing to do.
    return
  }

  await ensureSchema()
  const conversation = await getOrCreateConversation(from)
  const isNew = await insertInboundMessage(conversation.id, messageSid, text)
  if (!isNew || conversation.aiPaused) return

  try {
    const history = await getRecentMessages(conversation.id, 20)
    const systemPrompt = buildSystemPrompt()
    const reply = await generateReply(systemPrompt, history, text)

    await sendTwilioWhatsAppMessage(from, reply)
    await insertOutboundMessage(conversation.id, 'ai', reply)
  } catch (err) {
    console.error('twilio-whatsapp-webhook: failed to generate/send reply', err)
  }
}
