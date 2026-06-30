import { useEffect, useRef, useState } from 'react'
import Chart from './Chart'
import { ask, prettify, fmtVal, type Payload } from '../lib'

const STARTERS = [
  'suboferta por facultad', 'evolución de la matrícula por año',
  'tasa de admisión por modalidad en 2024', 'aulas subutilizadas', 'deuda abierta por año',
]
const REFINES = ['como línea', 'como tabla', 'top 5', 'por facultad', 'por carrera', 'solo 2024']

type Msg =
  | { k: 'user'; text: string }
  | { k: 'assistant'; p: Payload }
  | { k: 'note'; title: string; html: string; err?: boolean }
  | { k: 'thinking' }

export default function Chat() {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const hist = useRef<any[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])

  async function send(text: string) {
    text = text.trim()
    if (!text || busy) return
    setBusy(true)
    setInput('')
    setMsgs((m) => [...m, { k: 'user', text }, { k: 'thinking' }])
    let res: Msg
    try {
      const d = await ask(text, hist.current.slice(-6))
      if (d.intencion && d.intencion !== 'consulta') {
        res = { k: 'note', title: d.intencion === 'aclarar' ? 'Necesito precisar' : 'Fuera de alcance', html: (d.mensaje || '').replace(/\n/g, '<br/>') }
        hist.current.push({ pregunta: text, spec: null })
      } else if (d.ok) {
        res = { k: 'assistant', p: d }
        hist.current.push({ pregunta: text, spec: d.spec })
      } else {
        res = { k: 'note', title: 'No se pudo resolver', html: (d.errores || []).join(' · '), err: true }
        hist.current.push({ pregunta: text, spec: null })
      }
    } catch (e: any) {
      res = { k: 'note', title: 'Error', html: String(e), err: true }
    }
    setMsgs((m) => [...m.slice(0, -1), res])
    setBusy(false)
  }
  function reset() { setMsgs([]); hist.current = []; setInput('') }

  return (
    <div className="chat">
      <div className="thread">
        <div className="inner">
          {msgs.length === 0 && (
            <div className="empty">
              <div className="big">¿Qué quieres saber?</div>
              <p>Pregúntale a tu data en lenguaje natural. Cada respuesta trae su gráfico, y puedes <b>repreguntar</b> para refinarla sin empezar de nuevo.</p>
              <div className="chips">{STARTERS.map((s) => <span key={s} className="chip" onClick={() => send(s)}>{s}</span>)}</div>
            </div>
          )}
          {msgs.map((m, i) => <Bubble key={i} m={m} onRefine={send} />)}
          <div ref={end} />
        </div>
      </div>
      <div className="composer">
        <div className="cwrap">
          <div className="composer-top">
            <button className="ghost sm" onClick={reset} disabled={busy}>↺ Nueva consulta</button>
          </div>
          <div className="ask">
            <input
              value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') send(input) }}
              placeholder="Pregúntale a tu data…  luego repregunta: «ahora por facultad», «como línea»…"
            />
            <button onClick={() => send(input)} disabled={busy}>{busy ? '…' : 'Preguntar'}</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function Bubble({ m, onRefine }: { m: Msg; onRefine: (t: string) => void }) {
  if (m.k === 'user') return <div className="umsg">{m.text}</div>
  if (m.k === 'thinking') return <div className="amsg"><div className="think"><span className="spin" /> Consultando el modelo…</div></div>
  if (m.k === 'note') return (
    <div className="amsg"><h2 className={m.err ? 'err' : ''}>{m.title}</h2><div className={'narr ' + (m.err ? 'err' : '')} dangerouslySetInnerHTML={{ __html: m.html }} /></div>
  )
  return <Assistant p={m.p} onRefine={onRefine} />
}

function Assistant({ p, onRefine }: { p: Payload; onRefine: (t: string) => void }) {
  const filas = p.filas || []
  const viz: any = p.viz || { tipo: 'tabla', series: [] }
  const cols = p.columnas || (filas[0] ? Object.keys(filas[0]) : [])
  const series: string[] = viz.series?.length ? viz.series : cols.filter((c) => typeof filas[0]?.[c] === 'number')
  const isKpi = viz.tipo === 'kpi' || (filas.length === 1 && series.length === 1 && !viz.x)
  const isTable = viz.tipo === 'tabla'
  const isEmpty = filas.length === 0
  return (
    <div className="amsg">
      <h2>{p.titulo || 'Resultado'}</h2>
      {p.narrativa && <div className="narr">{p.narrativa}</div>}
      {isEmpty ? (
        <div className="nodata">
          <div className="nd-title">Sin datos para este corte</div>
          <p>La consulta se ejecutó correctamente, pero no devolvió ninguna fila. Suele deberse a que el período aún no tiene datos cargados en el lago, o a que algún filtro (ciclo, facultad, carrera…) no coincide con los valores existentes.</p>
          <p className="nd-hint">Prueba con otro período o quita un filtro. Puedes ver el corte exacto en «Ver consulta» más abajo.</p>
        </div>
      ) : isKpi ? (
        <div className="kpi"><span className="num">{fmtVal(filas[0]?.[series[0]], series[0])}</span><span className="lbl">{series[0]}</span></div>
      ) : isTable ? (
        <DataTable cols={cols} filas={filas} series={series} open />
      ) : (
        <Chart payload={p} />
      )}
      {!isEmpty && !isTable && filas.length > 0 && <DataTable cols={cols} filas={filas} series={series} />}
      <details><summary>Ver consulta (spec + DAX)</summary><pre>{'SPEC\n' + JSON.stringify(p.spec, null, 2) + '\n\nDAX\n' + (p.dax || '')}</pre></details>
      <div className="refine"><span className="rlbl">Refinar:</span>{REFINES.map((r) => <span key={r} className="rchip" onClick={() => onRefine(r)}>{r}</span>)}</div>
    </div>
  )
}

function DataTable({ cols, filas, series, open }: { cols: string[]; filas: any[]; series: string[]; open?: boolean }) {
  if (!filas.length) return null
  const num = new Set(series)
  const table = (
    <table>
      <thead><tr>{cols.map((c) => <th key={c} className={num.has(c) ? 'num' : ''}>{prettify(c)}</th>)}</tr></thead>
      <tbody>{filas.slice(0, 60).map((r, i) => <tr key={i}>{cols.map((c) => <td key={c} className={num.has(c) ? 'num' : ''}>{num.has(c) ? fmtVal(r[c], c) : prettify(r[c])}</td>)}</tr>)}</tbody>
    </table>
  )
  if (open) return table
  return <details><summary>Ver datos ({filas.length} {filas.length === 1 ? 'fila' : 'filas'})</summary>{table}</details>
}
