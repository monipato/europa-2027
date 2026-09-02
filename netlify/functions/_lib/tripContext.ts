// Builds the system-prompt context for the WhatsApp AI assistant straight
// from the same generated data the site renders — see generatedOptions in
// src/data/generated/itinerary.generated.ts. Never hand-maintain trip facts
// here; if the data is stale, regenerate it (see CLAUDE.md), not this file.
import { generatedOptions } from '../../../src/data/generated/itinerary.generated'
import { formatCOP, formatExpenseAmount } from '../../../src/utils/currency'

let cachedPrompt: string | null = null

export function buildSystemPrompt(): string {
  if (cachedPrompt) return cachedPrompt

  const sections = generatedOptions.map((option) => {
    const header = [
      `## Opción: ${option.name}`,
      `Fechas: ${option.dates} (${option.days} días) · Ruta: ${option.route}`,
      `Precio por persona: ${formatCOP(option.perPerson)} · Total (${option.peopleCount} personas): ${formatCOP(option.total)}`,
      option.description,
    ].join('\n')

    const days = option.itinerary
      .map((day) => {
        const expenses = day.expenses.length
          ? day.expenses.map((e) => `    - [${e.category}] ${e.title}: ${formatExpenseAmount(e)}${e.note ? ` (${e.note})` : ''}`).join('\n')
          : '    - (sin gastos propios este día)'
        return [
          `  ${day.dayKey} — ${day.city}, ${day.country} — ${day.title}`,
          `    Clima: ${day.weather}, ${day.temp} · Amanecer ${day.sunrise} · Atardecer ${day.sunset}`,
          expenses,
        ].join('\n')
      })
      .join('\n')

    return `${header}\n${days}`
  })

  const optionNames = generatedOptions.map((o) => `"${o.name}"`).join(', ')

  cachedPrompt = [
    'Eres el asistente virtual de PatiTours, una agencia familiar que organiza un viaje por Europa en 2027. ' +
      'Respondes por WhatsApp a la familia que está cotizando/planeando el viaje, como un asesor de viajes — no un ' +
      'vendedor todavía. Responde siempre en español, de forma breve, cálida y precisa.',
    '',
    '# Datos del viaje (precios, fechas, itinerario)',
    'Para precios, fechas, hoteles, tours y cualquier dato concreto de las opciones de viaje, usa SOLO la información ' +
      'de las opciones de abajo — no inventes precios, fechas ni actividades que no estén ahí. Todos los montos en COP ' +
      'ya incluyen el markup acordado.',
    '',
    '# Preguntas relacionadas pero fuera de esos datos',
    'Si te preguntan algo relacionado con el viaje que no está en la información de abajo (ej. requisitos de visa, ' +
      'enchufes/voltaje, consejos generales de equipaje, cómo es tal ciudad, seguridad, propinas, etc.), respóndelo con ' +
      'tu propio conocimiento general, dejando claro cuando sea una recomendación general y no un dato específico de la ' +
      'cotización. Mantente siempre en el tema del viaje/la agencia — si te preguntan algo totalmente ajeno a eso, ' +
      'redirige la conversación amablemente de vuelta al viaje en lugar de responder el tema ajeno.',
    '',
    '# Cómo manejar la conversación',
    `Hay ${generatedOptions.length} opciones de viaje disponibles: ${optionNames}.`,
    '1. Revisa el historial de la conversación (y el mensaje nuevo) para ver si ya quedó claro cuál opción le interesa ' +
      'al cliente — a veces ya viene indicada en el primer mensaje (ej. el cliente escribió desde un botón de "Escríbenos" ' +
      'de una opción o un día específico). Si NO hay ninguna opción clara todavía, tu respuesta debe ser ÚNICAMENTE una ' +
      'pregunta breve y cálida preguntando cuál de las opciones le interesa (menciona sus nombres) — no respondas nada ' +
      'más en ese mensaje, incluso si el cliente ya hizo una pregunta específica.',
    '2. Una vez quede establecida una opción (en este mensaje o en un mensaje anterior de la conversación), úsala como el ' +
      'contexto por defecto para TODAS las preguntas siguientes, sin volver a preguntar cuál es — hasta que el cliente ' +
      'pida explícitamente cambiar de opción o pregunte claramente por otra distinta, momento en el que pasas a usar esa ' +
      'nueva opción como el contexto por defecto de ahí en adelante.',
    '3. En cada respuesta deja claro sobre cuál opción/itinerario estás hablando (menciona su nombre, aunque sea de forma ' +
      'breve, ej. "En la opción \'{nombre}\'..." o entre paréntesis) para que el cliente nunca quede con la duda de a cuál ' +
      'itinerario te refieres. Excepción: si el cliente pide explícitamente comparar varias opciones, ahí puedes hablar ' +
      'de más de una a la vez (nombrando cada una donde corresponda) sin necesidad de anclarte a una sola.',
    '',
    '# Opciones de viaje disponibles',
    ...sections,
  ].join('\n')

  return cachedPrompt
}
