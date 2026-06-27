// API + helpers de formato (compartidos por Chat y Tablero).

export type Filtro = { tabla: string; columna: string; op: string; valor?: any; valores?: any[] }
export type Dim = { tabla: string; columna: string }
export type Spec = {
  medidas?: string[]; dimensiones?: Dim[]; filtros?: Filtro[]
  orden?: string | null; orden_dir?: string | null; topn?: number | null; roles?: string[]
}
export type Payload = {
  ok?: boolean; intencion?: string; mensaje?: string
  titulo?: string; narrativa?: string; viz?: any
  filas?: any[]; columnas?: string[]; spec?: Spec; dax?: string; errores?: string[]
}

const post = (url: string, body: any) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    .then((r) => r.json())

export const getCatalog = () => fetch('/api/catalog').then((r) => r.json())
export const ask = (pregunta: string, historial: any[] = []): Promise<Payload> =>
  post('/api/ask', { pregunta, historial })
export const runQuery = (spec: Spec): Promise<Payload> => post('/api/query', spec)

// ---- formato ----
export function prettify(s: any): string {
  if (s === null || s === undefined || s === '') return '(sin dato)'
  let t = String(s)
  if (t === t.toUpperCase()) {
    t = t
      .replace(/^DEPARTAMENTO ACAD[EÉ]MICO DE\s+/, '').replace(/^CARRERA DE\s+/, '')
      .replace(/^FACULTAD DE\s+/, '').replace(/^ESCUELA DE\s+/, '').replace(/^PROGRAMA DE\s+/, '')
      .replace(/^MAESTR[IÍ]A EN\s+/, 'Mg. ').replace(/^DOCTORADO EN\s+/, 'Dr. ')
    t = t.toLowerCase().replace(/(^|[\s\-/(])(\p{L})/gu, (_m, a, b) => a + b.toUpperCase())
  }
  return t
}
export const isPct = (m: string) => /%/.test(m || '')
export const isSoles = (m: string) => /s\/|sol/i.test(m || '')
export function fmtVal(v: any, m: string): string {
  if (typeof v !== 'number') return v === null ? '—' : String(v)
  if (isPct(m)) return (Math.round(v * 10) / 10).toLocaleString('es-PE') + '%'
  if (isSoles(m)) return 'S/ ' + Math.round(v).toLocaleString('es-PE')
  if (Number.isInteger(v)) return v.toLocaleString('es-PE')
  return (Math.round(v * 100) / 100).toLocaleString('es-PE')
}
export function compact(v: number): string {
  const a = Math.abs(v)
  if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + 'M'
  if (a >= 1e3) return (v / 1e3).toFixed(0) + 'k'
  return '' + Math.round(v * 10) / 10
}
export const trunc = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)
export const PAL = ['#E8520E', '#2B2D33', '#F49B6A', '#7A8089', '#F7C0A0', '#C2410C']
