import crypto from 'node:crypto'

const GRAPH_API_VERSION = 'v21.0'

/**
 * Timing-safe verification of Meta's X-Hub-Signature-256 header against the
 * raw (unparsed) request body — see spec step 4.2.
 */
export function verifyMetaSignature(rawBody: string, signatureHeader: string | null, appSecret: string): boolean {
  if (!signatureHeader) return false
  const expected = 'sha256=' + crypto.createHmac('sha256', appSecret).update(rawBody, 'utf8').digest('hex')
  const expectedBuf = Buffer.from(expected)
  const actualBuf = Buffer.from(signatureHeader)
  if (expectedBuf.length !== actualBuf.length) return false
  return crypto.timingSafeEqual(expectedBuf, actualBuf)
}

/**
 * Sends a text message via the Graph API. `to` is whatever came in as
 * `message.from` (a real phone number or a WhatsApp BSUID) — pass it back verbatim.
 */
export async function sendMetaWhatsAppMessage(to: string, body: string): Promise<void> {
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID
  const accessToken = process.env.WHATSAPP_ACCESS_TOKEN
  if (!phoneNumberId || !accessToken) {
    console.error('sendMetaWhatsAppMessage: missing WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN')
    return
  }

  const res = await fetch(`https://graph.facebook.com/${GRAPH_API_VERSION}/${phoneNumberId}/messages`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messaging_product: 'whatsapp',
      to,
      type: 'text',
      text: { body },
    }),
  })

  if (!res.ok) {
    const errorBody = await res.text()
    console.error(`sendMetaWhatsAppMessage: Graph API returned ${res.status}: ${errorBody}`)
  }
}
