import twilio from 'twilio'

/**
 * Validates Twilio's X-Twilio-Signature header against the exact webhook URL
 * and the parsed form params — see https://www.twilio.com/docs/usage/webhooks/webhooks-security.
 * This only computes a local HMAC (via TWILIO_AUTH_TOKEN); it never calls
 * Twilio's REST API, so it isn't gated by the account's compliance/KYC status
 * the way sending a message via the Messages REST resource is.
 */
export function verifyTwilioSignature(url: string, params: Record<string, unknown>, signatureHeader: string | undefined): boolean {
  const authToken = process.env.TWILIO_AUTH_TOKEN
  if (!authToken || !signatureHeader) return false
  return twilio.validateRequest(authToken, signatureHeader, url, params as Record<string, string>)
}
