import { WHATSAPP_NUMBER } from '../constants'

/** Builds a wa.me link that opens a chat with `WHATSAPP_NUMBER`, pre-filled with `message`. */
export function buildWhatsAppLink(message: string): string {
  return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(message)}`
}
