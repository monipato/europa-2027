/**
 * Tiny pub/sub so `ChatInlineCTA` (deep inside e.g. `DayByDayView`) can open
 * the single `ChatWidget` mounted at the top of `App` with a prefilled
 * message, without threading chat-open state through every component in
 * between.
 */
type Listener = (message: string) => void

let listener: Listener | null = null

export function openChatWithMessage(message: string): void {
  listener?.(message)
}

export function setChatOpenListener(fn: Listener | null): void {
  listener = fn
}
