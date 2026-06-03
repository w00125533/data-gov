import type { Layer } from '../../api/client'

export const layerPalette: Record<Layer, { fill: string; stroke: string; text: string }> = {
  ODS: { fill: '#ecfdf5', stroke: '#10b981', text: '#047857' },
  DWD: { fill: '#eff6ff', stroke: '#2563eb', text: '#1d4ed8' },
  DWS: { fill: '#fff7ed', stroke: '#f97316', text: '#c2410c' },
  ADS: { fill: '#f5f3ff', stroke: '#7c3aed', text: '#6d28d9' },
  EVAL: { fill: '#fff1f2', stroke: '#e11d48', text: '#be123c' },
}

export function colorForLayer(layer?: string) {
  return layerPalette[(layer as Layer) || 'DWD'] ?? layerPalette.DWD
}
