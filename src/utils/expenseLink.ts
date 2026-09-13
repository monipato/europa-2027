// A hotel/booking confirmation link (PDF) should download instead of opening
// in a browser tab, unlike a tour/flight-search link which should open the
// site in a new tab. Both link kinds share the same `link` field on an
// expense, so the anchor's behavior is chosen from the URL itself.
export function isDownloadableLink(link: string): boolean {
  return link.toLowerCase().endsWith('.pdf');
}

export function expenseLinkLabel(link: string): string {
  return isDownloadableLink(link) ? 'Descargar comprobante' : 'Ver tour o sitio web';
}
