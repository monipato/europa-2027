import { MessageCircle } from 'lucide-react'
import { openChatWithMessage } from '../utils/chatBus'

/** Inline "ask about this" pill — opens the floating `ChatWidget` with
 * `message` pre-filled, instead of floating globally like the fab. */
export function ChatInlineCTA({ message, label }: { message: string; label: string }) {
  return (
    <button className="chat-inline-cta" onClick={() => openChatWithMessage(message)}>
      <MessageCircle size={18} />
      <span>{label}</span>
    </button>
  )
}
