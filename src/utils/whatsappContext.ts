import type { Category, ViewMode } from '../types'
import type { GeneratedDay, GeneratedOption } from '../data/generated/itinerary.generated'

/**
 * Pre-fills the floating WhatsApp button's message with whatever the user is
 * actually looking at, so starting a chat doesn't mean re-explaining context
 * the app already has — see the AI assistant's system prompt
 * (`netlify/functions/_lib/tripContext.ts`), which can answer these directly.
 */
export function buildContextualMessage(params: {
  hasStartedPlanning: boolean
  option: GeneratedOption
  view: ViewMode
  selectedDay: GeneratedDay | null
  selectedCategory: Category | null
}): string {
  const { hasStartedPlanning, option, view, selectedDay, selectedCategory } = params

  if (!hasStartedPlanning) {
    return 'Hola! Estoy viendo las opciones del viaje a Europa 2027 y tengo una pregunta.'
  }
  if (view === 'day' && selectedDay) {
    return `Hola! Tengo una pregunta sobre el día ${selectedDay.dayKey} (${selectedDay.city}) de la opción "${option.name}".`
  }
  if (view === 'category' && selectedCategory) {
    return `Hola! Tengo una pregunta sobre los gastos de ${selectedCategory} en la opción "${option.name}".`
  }
  return `Hola! Tengo una pregunta sobre la opción "${option.name}".`
}
