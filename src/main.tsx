import { StrictMode, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { excelQuoteLines } from './generatedQuoteData'
import { ArrowRight, CalendarDays, ChevronDown, ChevronLeft, ExternalLink, Heart, Hotel, Luggage, MapPin, Menu, Plane, Utensils, Wallet, X } from 'lucide-react'
import './styles.css'

type Category = 'Transporte' | 'Alojamiento' | 'Comida' | 'Tours' | 'Entradas' | 'Crucero' | 'Seguro'
type Expense = { category: Category; title: string; amount: number; note: string; link?: string; originalAmount?: number; currency?: 'COP' | 'EUR' | 'CHF' | 'CZK' | 'USD' }
type Day = { date: string; city: string; country: string; title: string; emoji: string; image: string; expenses: Expense[] }
type TripOption = { name: string; dates: string; route: string; days: number; total: number; perPerson: number; color: string; description: string }

const options: TripOption[] = [
  { name: 'Completo', dates: '30 abr – 29 may 2027', route: 'Zúrich · París · Barcelona · Roma · Praga · Berlín · Múnich', days: 30, total: 20521419, perPerson: 20521419, color: '#e9a34c', description: 'El recorrido más completo por Europa' },
  { name: 'Solo crucero', dates: '5 – 16 may 2027', route: 'Barcelona · Crucero Mediterráneo · Venecia', days: 11, total: 8941207, perPerson: 8941207, color: '#7f9fc4', description: 'Una escapada mediterránea' },
  { name: 'Zúrich y Crucero', dates: '1 – 16 may 2027', route: 'Zúrich · Barcelona · Crucero · Venecia', days: 16, total: 15004194, perPerson: 15004194, color: '#91b9a2', description: 'Ciudad y mar en un solo viaje' },
  { name: 'Múnich y Crucero', dates: '1 – 16 may 2027', route: 'Múnich · Barcelona · Crucero · Venecia', days: 16, total: 12438249, perPerson: 12438249, color: '#bf8e9a', description: 'Alemania, España y Mediterráneo' },
]

const img = (id: string) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=900&q=80`
const allItineraryDays: Day[] = [
  { date: '30 ABR', city: 'Zúrich', country: 'Suiza', title: 'Llegada a Zúrich', emoji: '🇨🇭', image: img('photo-1527668752968-14dc70a27c95'), expenses: [{ category: 'Transporte', title: 'Vuelo de llegada', amount: 1820000, note: 'Bogotá → Zúrich' }, { category: 'Alojamiento', title: 'Hotel en Zúrich', amount: 1215900, originalAmount: 300, currency: 'CHF', note: '5 noches · habitación triple' }, { category: 'Comida', title: 'Cena de bienvenida', amount: 180000, note: 'Restaurante local' }] },
  { date: '01 MAY', city: 'Zúrich', country: 'Suiza', title: 'Recorrido por la ciudad', emoji: '🇨🇭', image: img('photo-1515488764276-beab7607c1e6'), expenses: [{ category: 'Tours', title: 'Tour guiado por Zúrich', amount: 210000, note: 'Punto de encuentro: estación central', link: 'https://www.getyourguide.com/zurich-l55/' }, { category: 'Comida', title: 'Almuerzo y cena', amount: 250000, note: 'Estimado del día' }] },
  { date: '02 MAY', city: 'Jungfrau', country: 'Suiza', title: 'Excursión de día completo', emoji: '🇨🇭', image: img('photo-1531366936337-7c912a4589a7'), expenses: [{ category: 'Tours', title: 'Excursión Jungfraujoch', amount: 690000, note: 'Tren panorámico y guía', link: 'https://www.getyourguide.com/jungfraujoch-l793/' }, { category: 'Comida', title: 'Almuerzo en la montaña', amount: 160000, note: 'Estimado del día' }] },
  { date: '03 MAY', city: 'París', country: 'Francia', title: 'La ciudad de la luz', emoji: '🇫🇷', image: img('photo-1502602898657-3e91760cbb34'), expenses: [{ category: 'Transporte', title: 'Tren Zúrich → París', amount: 640000, note: 'Traslado a la ciudad' }, { category: 'Tours', title: 'Tour Torre Eiffel', amount: 280000, note: 'Entrada con acceso prioritario', link: 'https://www.toureiffel.paris/es' }, { category: 'Comida', title: 'Comidas del día', amount: 220000, note: 'Estimado del día' }] },
  { date: '04 MAY', city: 'París', country: 'Francia', title: 'Disneyland París', emoji: '🇫🇷', image: img('photo-1503917988258-f87a78e3c995'), expenses: [{ category: 'Entradas', title: 'Disneyland París', amount: 410000, note: 'Entrada 1 parque', link: 'https://www.disneylandparis.com/es-es/' }, { category: 'Transporte', title: 'Traslado ida y vuelta', amount: 95000, note: 'RER / transporte local' }] },
  { date: '05 MAY', city: 'París', country: 'Francia', title: 'Jardines y Montmartre', emoji: '🇫🇷', image: img('photo-1502602898657-3e91760cbb34'), expenses: [{ category: 'Tours', title: 'Tour Montmartre', amount: 180000, note: 'Caminata guiada', link: 'https://www.getyourguide.com/montmartre-l2606/' }, { category: 'Comida', title: 'Comidas del día', amount: 220000, note: 'Estimado del día' }] },
  { date: '06 MAY', city: 'Barcelona', country: 'España', title: 'Llegada a Barcelona', emoji: '🇪🇸', image: img('photo-1539037116277-4db20889f2d4'), expenses: [{ category: 'Transporte', title: 'Vuelo a Barcelona', amount: 530000, note: 'París → Barcelona' }, { category: 'Alojamiento', title: 'Hotel en Barcelona', amount: 390000, note: '2 noches' }, { category: 'Tours', title: 'Sagrada Familia', amount: 230000, note: 'Entrada guiada', link: 'https://sagradafamilia.org/es/' }] },
  { date: '07 MAY', city: 'Barcelona', country: 'España', title: 'Gaudí y el centro', emoji: '🇪🇸', image: img('photo-1583422409516-2895a77efded'), expenses: [{ category: 'Tours', title: 'Parque Güell y Gaudí', amount: 260000, note: 'Visita guiada', link: 'https://www.getyourguide.com/barcelona-l45/' }, { category: 'Comida', title: 'Comidas del día', amount: 210000, note: 'Estimado del día' }] },
  { date: '08 MAY', city: 'Mediterráneo', country: 'En el mar', title: 'Embarque en el crucero', emoji: '🛳️', image: img('photo-1544551763-46a013bb70d5'), expenses: [{ category: 'Crucero', title: 'Crucero Mediterráneo', amount: 2150000, note: 'Barcelona → Venecia · pensión completa' }] },
  { date: '09 MAY', city: 'Mediterráneo', country: 'En el mar', title: 'Día completo en el mar', emoji: '🛳️', image: img('photo-1544550285-f813152fb2fd'), expenses: [{ category: 'Crucero', title: 'Servicios a bordo', amount: 0, note: 'Incluido en la tarifa' }] },
  { date: '10 MAY', city: 'La Spezia', country: 'Italia', title: 'Cinque Terre', emoji: '🇮🇹', image: img('photo-1533104816931-20fa691ff6ca'), expenses: [{ category: 'Tours', title: 'Excursión Cinque Terre', amount: 360000, note: 'Guía y transporte', link: 'https://www.getyourguide.com/cinque-terre-l272/' }, { category: 'Comida', title: 'Almuerzo en tierra', amount: 150000, note: 'Estimado' }] },
  { date: '11 MAY', city: 'Civitavecchia', country: 'Italia', title: 'Roma · primera visita', emoji: '🇮🇹', image: img('photo-1552832230-c0197dd311b5'), expenses: [{ category: 'Tours', title: 'Tour Coliseo y Foro Romano', amount: 340000, note: 'Entrada y guía', link: 'https://www.getyourguide.com/rome-l33/' }, { category: 'Comida', title: 'Comidas del día', amount: 210000, note: 'Estimado' }] },
  { date: '12 MAY', city: 'Salerno', country: 'Italia', title: 'Costa Amalfitana', emoji: '🇮🇹', image: img('photo-1530789253388-582c481c54b0'), expenses: [{ category: 'Tours', title: 'Excursión Costa Amalfitana', amount: 390000, note: 'Positano y Amalfi', link: 'https://www.getyourguide.com/amalfi-coast-l325/' }] },
  { date: '13 MAY', city: 'Mediterráneo', country: 'En el mar', title: 'Navegación', emoji: '🛳️', image: img('photo-1544551763-46a013bb70d5'), expenses: [{ category: 'Crucero', title: 'Día de navegación', amount: 0, note: 'Incluido en la tarifa' }] },
  { date: '14 MAY', city: 'Zadar', country: 'Croacia', title: 'Paseo por el casco antiguo', emoji: '🇭🇷', image: img('photo-1555990538-1e8f8e4c5c1f'), expenses: [{ category: 'Tours', title: 'Paseo guiado por Zadar', amount: 190000, note: 'Centro histórico', link: 'https://www.getyourguide.com/zadar-l1327/' }] },
  { date: '15 MAY', city: 'Venecia', country: 'Italia', title: 'Llegada a Venecia', emoji: '🇮🇹', image: img('photo-1520175480921-4edfa2983e0f'), expenses: [{ category: 'Transporte', title: 'Desembarque y traslado', amount: 180000, note: 'Puerto → hotel' }, { category: 'Alojamiento', title: 'Hotel en Venecia', amount: 480000, note: '2 noches' }] },
  { date: '16 MAY', city: 'Venecia', country: 'Italia', title: 'La ciudad de los canales', emoji: '🇮🇹', image: img('photo-1523906834658-6e24ef2386f9'), expenses: [{ category: 'Tours', title: 'Paseo en góndola', amount: 250000, note: 'Paseo compartido', link: 'https://www.getyourguide.com/venice-l35/' }, { category: 'Comida', title: 'Comidas del día', amount: 240000, note: 'Estimado' }] },
  { date: '17 MAY', city: 'Roma', country: 'Italia', title: 'Roma eterna', emoji: '🇮🇹', image: img('photo-1529260830199-42c24126f198'), expenses: [{ category: 'Transporte', title: 'Tren Venecia → Roma', amount: 360000, note: 'Alta velocidad' }, { category: 'Tours', title: 'Roma clásica', amount: 250000, note: 'Fontana di Trevi y Panteón', link: 'https://www.getyourguide.com/rome-l33/' }] },
  { date: '18 MAY', city: 'Roma', country: 'Italia', title: 'Coliseo y Foro Romano', emoji: '🇮🇹', image: img('photo-1552832230-c0197dd311b5'), expenses: [{ category: 'Tours', title: 'Coliseo y Foro Romano', amount: 330000, note: 'Entrada con guía', link: 'https://www.getyourguide.com/rome-l33/' }, { category: 'Comida', title: 'Comidas del día', amount: 220000, note: 'Estimado' }] },
  { date: '19 MAY', city: 'Praga', country: 'República Checa', title: 'Llegada a Praga', emoji: '🇨🇿', image: img('photo-1541849546-216549ae216d'), expenses: [{ category: 'Transporte', title: 'Vuelo Roma → Praga', amount: 520000, note: 'Traslado de ciudad' }, { category: 'Alojamiento', title: 'Hotel en Praga', amount: 330000, note: '2 noches' }] },
  { date: '20 MAY', city: 'Praga', country: 'República Checa', title: 'Castillo de Praga', emoji: '🇨🇿', image: img('photo-1541849546-216549ae216d'), expenses: [{ category: 'Tours', title: 'Castillo y Puente de Carlos', amount: 240000, note: 'Visita guiada', link: 'https://www.getyourguide.com/prague-l10/' }, { category: 'Comida', title: 'Comidas del día', amount: 180000, note: 'Estimado' }] },
  { date: '21 MAY', city: 'Praga', country: 'República Checa', title: 'Barrio Judío', emoji: '🇨🇿', image: img('photo-1519671282429-b44660ead0a7'), expenses: [{ category: 'Tours', title: 'Barrio Judío y Torre', amount: 190000, note: 'Entrada y guía', link: 'https://www.getyourguide.com/prague-l10/' }] },
  { date: '22 MAY', city: 'Berlín', country: 'Alemania', title: 'Tren a Berlín', emoji: '🇩🇪', image: img('photo-1560969184-10fe8719e047'), expenses: [{ category: 'Transporte', title: 'Tren Praga → Berlín', amount: 420000, note: 'Traslado de ciudad' }, { category: 'Alojamiento', title: 'Hotel en Berlín', amount: 350000, note: '2 noches' }] },
  { date: '23 MAY', city: 'Berlín', country: 'Alemania', title: 'Puerta de Brandeburgo', emoji: '🇩🇪', image: img('photo-1560969184-10fe8719e047'), expenses: [{ category: 'Tours', title: 'Muro y centro de Berlín', amount: 210000, note: 'Paseo guiado', link: 'https://www.getyourguide.com/berlin-l17/' }, { category: 'Comida', title: 'Comidas del día', amount: 190000, note: 'Estimado' }] },
  { date: '24 MAY', city: 'Berlín', country: 'Alemania', title: 'Reichstag y paseo', emoji: '🇩🇪', image: img('photo-1560969184-10fe8719e047'), expenses: [{ category: 'Entradas', title: 'Reichstag', amount: 0, note: 'Reserva gratuita' }, { category: 'Comida', title: 'Comidas del día', amount: 190000, note: 'Estimado' }] },
  { date: '25 MAY', city: 'Múnich', country: 'Alemania', title: 'Llegada a Múnich', emoji: '🇩🇪', image: img('photo-1595867818082-083862f3d630'), expenses: [{ category: 'Transporte', title: 'Tren Berlín → Múnich', amount: 480000, note: 'Alta velocidad' }, { category: 'Alojamiento', title: 'Hotel en Múnich', amount: 360000, note: '3 noches' }] },
  { date: '26 MAY', city: 'Múnich', country: 'Alemania', title: 'Centro histórico', emoji: '🇩🇪', image: img('photo-1595867818082-083862f3d630'), expenses: [{ category: 'Tours', title: 'Tour por Múnich', amount: 220000, note: 'Marienplatz y casco antiguo', link: 'https://www.getyourguide.com/munich-l26/' }, { category: 'Comida', title: 'Comidas del día', amount: 190000, note: 'Estimado' }] },
  { date: '27 MAY', city: 'Neuschwanstein', country: 'Alemania', title: 'Excursión al castillo', emoji: '🇩🇪', image: img('photo-1502784444187-359ac186c5bb'), expenses: [{ category: 'Tours', title: 'Castillo de Neuschwanstein', amount: 360000, note: 'Excursión de día completo', link: 'https://www.getyourguide.com/neuschwanstein-castle-l24/' }, { category: 'Comida', title: 'Almuerzo', amount: 130000, note: 'Estimado' }] },
  { date: '28 MAY', city: 'Múnich', country: 'Alemania', title: 'Compras y actividades finales', emoji: '🇩🇪', image: img('photo-1595867818082-083862f3d630'), expenses: [{ category: 'Comida', title: 'Comidas del día', amount: 200000, note: 'Estimado' }, { category: 'Entradas', title: 'Actividades finales', amount: 180000, note: 'Presupuesto flexible' }] },
  { date: '29 MAY', city: 'Regreso', country: 'Colombia', title: 'Vuelo de regreso', emoji: '🇨🇴', image: img('photo-1436491865332-7a61a109cc05'), expenses: [{ category: 'Transporte', title: 'Vuelo Múnich → Bogotá', amount: 2200000, note: 'Regreso a casa' }] },
]

const categoryMeta: Record<Category, { icon: string; color: string }> = { Transporte: { icon: '✈️', color: '#e7a663' }, Alojamiento: { icon: '🏨', color: '#889fc9' }, Comida: { icon: '🍴', color: '#e8bd6f' }, Tours: { icon: '🗺️', color: '#75a995' }, Entradas: { icon: '🎟️', color: '#b08cc2' }, Crucero: { icon: '🛳️', color: '#77a9c8' }, Seguro: { icon: '🛡️', color: '#96a7a2' } }
const originalCurrencyByPersonCop = new Map<number, string>()
excelQuoteLines.forEach(line => {
  if (line.perPersonCop && line.totalOriginal && line.quantity && line.currency !== 'COP') {
    const originalPerPerson = line.rateToCop ? line.perPersonCop / line.rateToCop : line.totalOriginal / line.quantity
    originalCurrencyByPersonCop.set(Math.round(line.perPersonCop), `${line.currency} ${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(originalPerPerson)}`)
  }
})
const formatCOP = (n: number) => {
  if (n === 0) return 'Incluido'
  const cop = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(n)
  const original = originalCurrencyByPersonCop.get(Math.round(n))
  return original ? `${original} · ${cop} COP` : cop
}
const formatOriginal = (expense: Expense) => {
  if (expense.originalAmount && expense.currency && expense.currency !== 'COP') {
    const symbols = { EUR: '€', CHF: 'CHF', CZK: 'Kč', USD: 'US$' }
    return `${symbols[expense.currency]} ${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(expense.originalAmount ?? 0)} · ${new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(expense.amount)} COP`
  }
  if (!expense.currency || expense.currency === 'COP') return formatCOP(expense.amount)
  const symbols = { EUR: '€', CHF: 'CHF', CZK: 'Kč', USD: 'US$' }
  return `${symbols[expense.currency]} ${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(expense.originalAmount ?? 0)} · ${formatCOP(expense.amount)} COP`
}
const rates = [{ code: 'EUR', value: '€ 1 = $3.750 COP' }, { code: 'CHF', value: 'CHF 1 = $4.053 COP' }, { code: 'CZK', value: 'Kč 1 = $156 COP' }, { code: 'USD', value: 'US$ 1 = $3.218 COP' }]

function App() {
  void excelQuoteLines
  const [option, setOption] = useState<number | null>(null)
  const [view, setView] = useState<'day' | 'category'>('day')
  const [selectedDay, setSelectedDay] = useState(0)
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [started, setStarted] = useState(false)
  useEffect(() => {
    const advance = (event: MouseEvent) => { if ((event.target as HTMLElement).closest('.start-button, .option-card')) setStarted(true) }
    document.addEventListener('click', advance)
    return () => document.removeEventListener('click', advance)
  }, [])
  const selected = options[option ?? 0]
  const itineraryDays = useMemo(() => option === 0 ? allItineraryDays : option === 1 ? allItineraryDays.filter(d => ['05 MAY','06 MAY','07 MAY','08 MAY','09 MAY','10 MAY','11 MAY','12 MAY','13 MAY','14 MAY','15 MAY','16 MAY'].includes(d.date)) : allItineraryDays.filter(d => ['30 ABR','01 MAY','02 MAY','03 MAY','04 MAY','05 MAY','06 MAY','07 MAY','08 MAY','09 MAY','10 MAY','11 MAY','12 MAY','13 MAY','14 MAY','15 MAY','16 MAY'].includes(d.date)), [option])
  const days = itineraryDays
  const activeDay = itineraryDays[selectedDay] ?? itineraryDays[0]
  const day = activeDay
  useEffect(() => {
    const flags: Record<string, string> = { Suiza: '🇨🇭', Francia: '🇫🇷', España: '🇪🇸', Italia: '🇮🇹', 'En el mar': '🛳️', Croacia: '🇭🇷', Alemania: '🇩🇪', 'República Checa': '🇨🇿', Colombia: '🇨🇴' }
    document.querySelectorAll('.day-nav').forEach(button => {
      const city = button.querySelector('strong')
      const country = button.querySelector('small')?.textContent?.trim() ?? ''
      if (city) city.textContent = `${flags[country] ?? '🌍'} ${city.textContent?.replace(/^\S+\s/, '') ?? ''}`
    })
  }, [itineraryDays])
  const totals = useMemo(() => itineraryDays.flatMap(d => d.expenses).reduce<Record<string, number>>((acc, expense) => { acc[expense.category] = (acc[expense.category] || 0) + expense.amount; return acc }, {}), [itineraryDays])
  const totalVisible = Object.values(totals).reduce((a, b) => a + b, 0)
  const excelCategoryNames: Record<Category, string> = { Transporte: 'Traslados', Alojamiento: 'Alojamiento', Comida: 'Comidas', Tours: 'Tours y Excursiones', Entradas: 'Entradas', Crucero: 'Crucero', Seguro: 'Seguro de Viaje' }
  const categoryDetails = selectedCategory ? excelQuoteLines.filter(line => line.option === selected.name && line.category === excelCategoryNames[selectedCategory]).map(line => ({ title: line.title, amount: line.perPersonCop ?? 0, note: line.note, category: selectedCategory, date: line.date, city: line.place, currency: line.currency, originalAmount: line.rateToCop && line.perPersonCop ? line.perPersonCop / line.rateToCop : undefined, link: undefined })) : []

  return <div className={`app-shell ${started ? 'planner-open' : 'selection-screen'}`}>
    <header className="topbar"><div className="brand"><span className="brand-mark">✈</span><div><strong>EUROPA <span>2027</span></strong><small>MI VIAJE · COTIZACIÓN</small></div></div><div className="header-actions"><button className="menu-button" aria-label="Abrir menú" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button></div><nav className={menuOpen ? 'open' : ''}><a href="#itinerario" onClick={() => setMenuOpen(false)}>Itinerario</a><a href="#resumen" onClick={() => setMenuOpen(false)}>Resumen de gastos</a></nav></header>
    <main onClick={(event) => { if ((event.target as HTMLElement).closest('.start-button')) setStarted(true) }}>
    {started && <div className="planner-heading"><button className="planner-back" onClick={() => { setStarted(false); setSelectedCategory(null) }}><ChevronLeft size={18} /> Cambiar viaje</button><p className="eyebrow">Tu itinerario seleccionado</p><div className="rates-card"><strong>Tasas estimadas · 24 ago 2026</strong><div>{rates.map(rate => <span key={rate.code}><b>{rate.code}</b> {rate.value}</span>)}</div><small>Referenciales; actualízalas antes de reservar.</small><p className="occupancy-note">👤 Todos los gastos detallados se muestran <b>por persona</b>, calculados con alojamiento en habitación triple (3 personas). En habitación doble, el precio por persona cambia.</p></div></div>}
    {!started && <>
      <section className="welcome"><div><p className="eyebrow">Tu viaje, más fácil de entender</p><h1>Elige tu forma de viajar por Europa</h1><p className="intro">Compara las opciones y revisa cada gasto con calma. Todo está organizado para que encuentres lo que necesitas.</p></div><div className="welcome-art">✈️<span>🌍</span></div></section>
      <section className="option-area"><div className="section-heading"><div><p className="eyebrow">Paso 1 de 2</p><h2>Selecciona una cotización</h2></div><span className="people-badge">👥 3 personas</span></div><div className="option-grid">{options.map((item, index) => <button className={`option-card ${option === index ? 'active' : ''}`} key={item.name} onClick={() => setOption(index)}><span className="option-accent" style={{ background: item.color }}></span><div className="option-top"><span className="radio">{option === index ? '✓' : ''}</span><span className="days">{item.days} días</span></div><h3>{item.name}</h3><p>{item.description}</p><strong>{formatCOP(item.total)}</strong><small>{item.dates}</small><div className="route">{item.route}</div></button>)}</div></section>
      <div className="rates-card rates-bottom"><strong>Tasas estimadas · 24 ago 2026</strong><div>{rates.map(rate => <span key={`first-${rate.code}`}><b>{rate.code}</b> {rate.value}</span>)}</div><small>Referenciales; actualízalas antes de reservar.</small><p className="occupancy-note">👤 Gastos por persona con alojamiento en habitación triple (3 personas). En habitación doble, el precio por persona cambia.</p></div>
    </>}
      <section className="trip-summary"><div className="summary-copy"><h2>{selected.name}</h2><span>{selected.route}</span></div><div className="summary-cost"><strong>{formatCOP(selected.perPerson)}</strong></div></section>
      <section id="itinerario" className="content-section"><div className="section-heading"><div><p className="eyebrow">Paso 2 de 2</p><h2>¿Cómo quieres verlo?</h2></div><span className="hint">Toca una tarjeta para ver el detalle</span></div><div className="view-toggle" role="tablist"><button className={view === 'day' ? 'selected' : ''} onClick={() => { setView('day'); setSelectedCategory(null) }}><CalendarDays /> Por día</button><button className={view === 'category' ? 'selected' : ''} onClick={() => setView('category')}><Wallet /> Por rubro</button></div>
        {view === 'day' ? <div className="day-layout"><aside className="day-list">{itineraryDays.map((item, index) => <button className={`day-nav ${selectedDay === index ? 'selected' : ''}`} key={item.date + item.city} onClick={() => setSelectedDay(index)}><span>{item.date}</span><div><strong>{item.city}</strong><small>{item.country}</small></div><ChevronDown /></button>)}</aside><article className="day-detail"><div className="day-hero"><img src={day.image} alt={`Paisaje de ${day.city}`} /><div className="day-hero-overlay"><span>{day.emoji} {day.country}</span><h2>{day.title}</h2><p><MapPin size={15} /> {day.city}</p></div></div><div className="expense-header"><div><p className="eyebrow">{day.date} · gastos del día</p><h3>¿En qué se va el dinero?</h3></div><strong>{formatCOP(day.expenses.reduce((a, e) => a + e.amount, 0))}</strong></div><div className="expense-list">{day.expenses.map((expense, i) => <div className="expense-row" key={expense.title}><span className="category-icon" style={{ background: categoryMeta[expense.category].color }}>{categoryMeta[expense.category].icon}</span><div className="expense-info"><strong>{expense.title}</strong><span>{expense.category} · {expense.note}</span>{expense.link && <a href={expense.link} target="_blank" rel="noreferrer">Ver tour o sitio web <ExternalLink size={14} /></a>}</div><b>{formatCOP(expense.amount)}</b></div>)}</div></article></div> : <div className="category-layout"><div className="category-grid">{Object.entries(totals).map(([category, amount]) => <button className={`category-card ${selectedCategory === category ? 'selected' : ''}`} key={category} onClick={() => setSelectedCategory(category as Category)}><span className="category-big-icon" style={{ background: categoryMeta[category as Category].color }}>{categoryMeta[category as Category].icon}</span><span className="category-name">{category}</span><strong>{formatCOP(amount)}</strong><small>{itineraryDays.flatMap(d => d.expenses).filter(e => e.category === category).length} movimientos <ArrowRight size={15} /></small></button>)}</div><div className="category-total"><div><span>Total de gastos detallados</span><strong>{formatCOP(totalVisible)}</strong></div><p>Los valores son estimados y pueden cambiar según la fecha de compra.</p></div>{selectedCategory && <div className="category-detail"><div className="detail-title"><div><p className="eyebrow">Detalle del rubro</p><h3>{categoryMeta[selectedCategory].icon} {selectedCategory}</h3></div><button onClick={() => setSelectedCategory(null)} aria-label="Cerrar detalle"><X /></button></div>{categoryDetails.map((item, i) => <div className="mini-row" key={item.title + i}><span>{item.date} · {item.city}</span><strong>{item.title}</strong><b>{formatCOP(item.amount)}</b>{item.link && <a href={item.link} target="_blank" rel="noreferrer">Abrir enlace <ExternalLink size={13} /></a>}</div>)}</div>}</div>}
      </section>
    </main><footer><span>Europa 2027 · Planifica con calma</span><span><Heart size={15} fill="currentColor" /> Hecho para viajar mejor</span></footer>
  </div>
}

export default App

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
