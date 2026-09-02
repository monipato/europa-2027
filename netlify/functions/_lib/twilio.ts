import twilio from 'twilio'

/**
 * Validates Twilio's X-Twilio-Signature header against the exact webhook URL
 * and the parsed form params — see https://www.twilio.com/docs/usage/webhooks/webhooks-security.
 */
export function verifyTwilioSignature(url: string, params: Record<string, unknown>, signatureHeader: string | undefined): boolean {
  const authToken = process.env.TWILIO_AUTH_TOKEN
  if (!authToken || !signatureHeader) return false
  return twilio.validateRequest(authToken, signatureHeader, url, params as Record<string, string>)
}

/** Sends a WhatsApp text message via the Twilio REST API. `to` must be a bare "whatsapp:+..." address. */
export async function sendTwilioWhatsAppMessage(to: string, body: string): Promise<void> {
  const accountSid = process.env.TWILIO_ACCOUNT_SID
  const authToken = process.env.TWILIO_AUTH_TOKEN
  const from = process.env.TWILIO_WHATSAPP_NUMBER
  if (!accountSid || !authToken || !from) {
    console.error('sendTwilioWhatsAppMessage: missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN or TWILIO_WHATSAPP_NUMBER')
    return
  }

  const client = twilio(accountSid, authToken)
  try {
    await client.messages.create({ from, to, body })
  } catch (err) {
    console.error('sendTwilioWhatsAppMessage: Twilio API call failed', err)
  }
}
