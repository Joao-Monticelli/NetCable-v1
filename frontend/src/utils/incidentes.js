// Incident states and impacts, shared by the editor (IncidentesModal) and the public status page.
// Texts are translation keys (t()). Colors come from the status palette of the status page.
export const ESTADOS_INCIDENTE = {
  investigando: 'Investigando',
  identificado: 'Causa identificada',
  monitorando: 'Monitorando',
  resolvido: 'Resolvido',
}
export const IMPACTOS = {
  menor: { texto: 'Impacto pequeno', cor: '#fab219' },
  parcial: { texto: 'Parte dos serviços afetada', cor: '#ec835a' },
  grave: { texto: 'Fora do ar', cor: '#d03b3b' },
}
