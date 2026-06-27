import { useEffect, useState } from 'react'
import Chart from './Chart'
import { runQuery, prettify, fmtVal, type Filtro } from '../lib'

const TABLA = 'fact_demanda_seccion'
const KPIS = ['Secciones', 'Llenado Prom %', 'Suboferta %']
const PANELS = [
  { titulo: 'Llenado promedio por departamento', medida: 'Llenado Prom %', dim: 'departamento_academico', viz: 'barra', topn: 15, wide: true },
  { titulo: 'Llenado promedio por año', medida: 'Llenado Prom %', dim: 'anio', viz: 'linea', orden: 'anio', dir: 'asc', topn: 50 },
  { titulo: 'Secciones por tipo de curso', medida: 'Secciones', dim: 'tipo_curso', viz: 'barra', topn: 12 },
  { titulo: 'Suboferta por tipo de dependencia', medida: 'Suboferta %', dim: 'tipo_dependencia', viz: 'barra', topn: 12 },
  { titulo: 'Secciones por turno', medida: 'Secciones', dim: 'turno', viz: 'circular', topn: 8 },
]

export default function Dashboard() {
  const [filtros, setFiltros] = useState<Filtro[]>([])
  const pick = (col: string, val: any) =>
    setFiltros((f) => [...f.filter((x) => x.columna !== col), { tabla: TABLA, columna: col, op: '=', valor: val }])
  const remove = (col: string) => setFiltros((f) => f.filter((x) => x.columna !== col))

  return (
    <div className="dash">
      <div className="dash-head">
        <h2>Demanda académica</h2>
        <div className="muted">Oferta y llenado de secciones · haz clic en cualquier barra para filtrar todo el tablero</div>
      </div>
      <FilterBar filtros={filtros} onRemove={remove} onClear={() => setFiltros([])} />
      <div className="kpis">{KPIS.map((k) => <Kpi key={k} medida={k} filtros={filtros} />)}</div>
      <div className="grid">{PANELS.map((p, i) => <Panel key={i} cfg={p} filtros={filtros} onPick={pick} />)}</div>
    </div>
  )
}

function FilterBar({ filtros, onRemove, onClear }: { filtros: Filtro[]; onRemove: (c: string) => void; onClear: () => void }) {
  if (!filtros.length) return <div className="filterbar empty-fb">Sin filtros activos — haz clic en una barra para acotar.</div>
  return (
    <div className="filterbar">
      <span className="fb-lbl">Filtros:</span>
      {filtros.map((f) => (
        <span key={f.columna} className="fchip">{f.columna}: <b>{prettify(f.valor)}</b><span className="x" onClick={() => onRemove(f.columna)}>✕</span></span>
      ))}
      <button className="ghost sm" onClick={onClear}>Limpiar todo</button>
    </div>
  )
}

function Kpi({ medida, filtros }: { medida: string; filtros: Filtro[] }) {
  const [v, setV] = useState<any>(null)
  const [load, setLoad] = useState(true)
  useEffect(() => {
    let on = true; setLoad(true)
    runQuery({ medidas: [medida], dimensiones: [], filtros, topn: 1 }).then((d) => {
      if (!on) return
      setV(d.ok && d.filas?.[0] ? d.filas[0][medida] : null); setLoad(false)
    })
    return () => { on = false }
  }, [medida, JSON.stringify(filtros)])
  return <div className="kpicard"><div className="kv">{load ? '…' : fmtVal(v, medida)}</div><div className="kl">{medida}</div></div>
}

function Panel({ cfg, filtros, onPick }: { cfg: any; filtros: Filtro[]; onPick: (c: string, v: any) => void }) {
  const [p, setP] = useState<any>(null)
  const [load, setLoad] = useState(true)
  const applied = filtros.filter((f) => f.columna !== cfg.dim)
  useEffect(() => {
    let on = true; setLoad(true)
    const spec = { medidas: [cfg.medida], dimensiones: [{ tabla: TABLA, columna: cfg.dim }], filtros: applied, orden: cfg.orden || cfg.medida, orden_dir: cfg.dir || 'desc', topn: cfg.topn || 15 }
    runQuery(spec).then((d) => {
      if (!on) return
      if (d.ok) { d.viz = { tipo: cfg.viz, x: cfg.dim, series: [cfg.medida] }; d.titulo = cfg.titulo }
      setP(d); setLoad(false)
    })
    return () => { on = false }
  }, [JSON.stringify(applied)])

  return (
    <div className={'panel' + (cfg.wide ? ' wide' : '')}>
      <div className="ptitle">{cfg.titulo}</div>
      {load ? <div className="ploading"><span className="spin" /></div>
        : p?.ok ? <Chart payload={p} onPick={onPick} height={cfg.viz === 'linea' || cfg.viz === 'circular' ? 280 : undefined} />
          : <div className="perr">{(p?.errores || []).join(' · ') || 'sin datos'}</div>}
    </div>
  )
}
