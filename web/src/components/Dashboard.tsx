import { useEffect, useState } from 'react'
import Chart from './Chart'
import { runQuery, prettify, fmtVal, type Filtro } from '../lib'
import type { DashCfg, Panel as PanelCfg } from '../dashboards'

export default function Dashboard({ cfg }: { cfg: DashCfg }) {
  const [filtros, setFiltros] = useState<Filtro[]>([])
  useEffect(() => { setFiltros([]) }, [cfg.id])   // limpiar filtros al cambiar de dominio
  const pick = (col: string, val: any) =>
    setFiltros((f) => [...f.filter((x) => x.columna !== col), { tabla: cfg.tabla, columna: col, op: '=', valor: val }])
  const remove = (col: string) => setFiltros((f) => f.filter((x) => x.columna !== col))

  return (
    <div className="dash">
      <div className="dash-head">
        <h2>{cfg.titulo}</h2>
        <div className="muted">{cfg.sub} · haz clic en cualquier barra para filtrar todo el tablero</div>
      </div>
      <FilterBar filtros={filtros} onRemove={remove} onClear={() => setFiltros([])} />
      <div className="kpis">{cfg.kpis.map((k) => <Kpi key={k} medida={k} filtros={filtros} />)}</div>
      <div className="grid">{cfg.panels.map((p, i) => <Panel key={cfg.id + i} tabla={cfg.tabla} cfg={p} filtros={filtros} onPick={pick} />)}</div>
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

function Panel({ tabla, cfg, filtros, onPick }: { tabla: string; cfg: PanelCfg; filtros: Filtro[]; onPick: (c: string, v: any) => void }) {
  const [p, setP] = useState<any>(null)
  const [load, setLoad] = useState(true)
  const applied = filtros.filter((f) => f.columna !== cfg.dim)
  useEffect(() => {
    let on = true; setLoad(true)
    const spec = { medidas: [cfg.medida], dimensiones: [{ tabla, columna: cfg.dim }], filtros: applied, orden: cfg.orden || cfg.medida, orden_dir: cfg.dir || 'desc', topn: cfg.topn || 15 }
    runQuery(spec).then((d) => {
      if (!on) return
      if (d.ok) { d.viz = { tipo: cfg.viz, x: cfg.dim, series: [cfg.medida] }; d.titulo = cfg.titulo }
      setP(d); setLoad(false)
    })
    return () => { on = false }
  }, [JSON.stringify(applied), cfg.dim, cfg.medida])

  return (
    <div className={'panel' + (cfg.wide ? ' wide' : '')}>
      <div className="ptitle">{cfg.titulo}</div>
      {load ? <div className="ploading"><span className="spin" /></div>
        : p?.ok ? <Chart payload={p} onPick={onPick} height={cfg.viz === 'linea' || cfg.viz === 'circular' ? 280 : undefined} />
          : <div className="perr">{(p?.errores || []).join(' · ') || 'sin datos'}</div>}
    </div>
  )
}
