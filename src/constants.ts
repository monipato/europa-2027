/** Currency symbol shown next to an expense's original (non-COP) amount. */
export const CURRENCY_SYMBOLS: Record<string, string> = { EUR: '€', CHF: 'CHF', CZK: 'Kč', USD: 'US$', COP: '$' }

/** PatiTours' WhatsApp Business number (the one wired to the Twilio webhook
 * + AI assistant — see `netlify/functions/twilio-whatsapp-webhook.mts`).
 * Digits only, country code first, no "+" or spaces — this is the format
 * `wa.me` links expect. Public by design, not a secret. */
export const WHATSAPP_NUMBER = '573042519907'
