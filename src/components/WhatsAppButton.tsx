import { buildWhatsAppLink } from '../utils/whatsapp'
import { WhatsAppIcon } from './WhatsAppIcon'

/** Floating "chat with us" button, always visible bottom-right. `message`
 * pre-fills the chat with whatever the user is currently looking at — see
 * `buildContextualMessage` in `utils/whatsappContext.ts`. */
export function WhatsAppButton({ message }: { message: string }) {
  return (
    <a className="whatsapp-fab" href={buildWhatsAppLink(message)} target="_blank" rel="noreferrer" aria-label="Escríbenos por WhatsApp">
      <WhatsAppIcon size={28} />
    </a>
  )
}
