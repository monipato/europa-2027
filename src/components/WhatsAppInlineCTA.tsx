import { buildWhatsAppLink } from '../utils/whatsapp'
import { WhatsAppIcon } from './WhatsAppIcon'

/** Inline "ask about this" pill — same idea as `WhatsAppButton` but with a
 * label, meant to sit inside a specific piece of content (e.g. a day's
 * itinerary) rather than float globally. */
export function WhatsAppInlineCTA({ message, label }: { message: string; label: string }) {
  return (
    <a className="whatsapp-inline-cta" href={buildWhatsAppLink(message)} target="_blank" rel="noreferrer">
      <WhatsAppIcon size={18} />
      <span>{label}</span>
    </a>
  )
}
