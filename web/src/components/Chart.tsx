import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import { PAL, prettify, fmtVal, compact, trunc, isPct, isSoles } from '../lib'

type Props = { payload: any; onPick?: (col: string, val: any) => void; height?: number }

function buildOption(payload: any) {
  const filas: any[] = payload.filas || []
  const viz = payload.viz || { tipo: 'barra', series: [] }
  const cols: string[] = payload.columnas || (filas[0] ? Object.keys(filas[0]) : [])
  const series: string[] = viz.series?.length ? viz.series : cols.filter((c) => typeof filas[0]?.[c] === 'number')
  const x: string = viz.x || cols.find((c) => !series.includes(c)) || cols[0]
  const rawCats = filas.map((r) => r[x])
  const base = (o: any) => ({ color: PAL, textStyle: { fontFamily: 'Inter,sans-serif' }, animationDuration: 500, ...o })

  if (viz.tipo === 'circular') {
    return {
      h: 340, rawCats, dimCol: x,
      option: base({
        tooltip: { trigger: 'item', formatter: (p: any) => `${prettify(p.name)}<br/><b>${fmtVal(p.value, series[0])}</b> (${p.percent}%)` },
        legend: { type: 'scroll', bottom: 0, textStyle: { color: '#697079' } },
        series: [{
          type: 'pie', radius: ['42%', '68%'], center: ['50%', '45%'], itemStyle: { borderColor: '#fff', borderWidth: 2 },
          label: { formatter: (p: any) => prettify(p.name), color: '#4b5159' },
          data: filas.map((r, i) => ({ name: r[x], value: r[series[0]], itemStyle: { color: PAL[i % PAL.length] } })),
        }],
      }),
    }
  }

  const isLine = viz.tipo === 'linea' || viz.tipo === 'area'
  const cats = filas.map((r) => prettify(r[x]))
  const maxLen = Math.max(0, ...cats.map((c) => c.length))
  const horiz = !isLine && (filas.length > 7 || maxLen > 14)

  const kinds = series.map((m) => (isPct(m) ? 'pct' : isSoles(m) ? 'soles' : 'count'))
  const primary = kinds[0]
  const mixed = series.length > 1 && new Set(kinds).size > 1
  const axOf = (i: number) => (mixed && kinds[i] !== primary ? 1 : 0)

  const s = series.map((m, i) => {
    const o: any = {
      name: m, type: isLine ? 'line' : 'bar', smooth: true,
      areaStyle: viz.tipo === 'area' ? { opacity: 0.12 } : undefined, symbolSize: 6,
      itemStyle: { color: PAL[i % PAL.length], borderRadius: isLine ? 0 : horiz ? [0, 4, 4, 0] : [4, 4, 0, 0] },
      lineStyle: isLine ? { width: 2.5 } : undefined, barMaxWidth: 26,
      label: !isLine && series.length === 1
        ? { show: true, position: horiz ? 'right' : 'top', color: '#4b5159', fontSize: 11, formatter: (p: any) => fmtVal(p.value, m) }
        : { show: false },
      data: filas.map((r) => r[m]),
    }
    if (horiz) o.xAxisIndex = axOf(i); else o.yAxisIndex = axOf(i)
    return o
  })

  const valAxis = (kind: string, side: string, sec: boolean) => ({
    type: 'value', position: side,
    axisLabel: { color: '#9aa0a8', formatter: kind === 'pct' ? (v: number) => v + '%' : compact },
    splitLine: sec ? { show: false } : { lineStyle: { color: '#eef0f2' } }, axisLine: { show: false }, axisTick: { show: false },
  })
  let vAxes: any[]
  if (mixed) { const k2 = kinds.find((k) => k !== primary)!; vAxes = [valAxis(primary, horiz ? 'bottom' : 'left', false), valAxis(k2, horiz ? 'top' : 'right', true)] }
  else vAxes = [valAxis(primary, horiz ? 'bottom' : 'left', false)]

  const catAxis: any = {
    type: 'category', data: cats, axisTick: { show: false }, axisLine: { lineStyle: { color: '#e9eaed' } },
    axisLabel: { color: '#5b626b', formatter: (v: string) => trunc(v, horiz ? 26 : 12), interval: 0, rotate: !horiz && maxLen > 6 ? 35 : 0, fontSize: 11 },
  }
  const h = horiz ? Math.max(300, filas.length * 30 + 60) : 340
  return {
    h, rawCats, dimCol: x,
    option: base({
      grid: { left: 6, right: horiz ? 44 : mixed ? 30 : 18, top: series.length > 1 ? 32 : 12, bottom: 6, containLabel: true },
      legend: series.length > 1 ? { top: 0, textStyle: { color: '#697079' }, icon: 'roundRect' } : undefined,
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (ps: any[]) => { let html = `<b>${ps[0].axisValueLabel}</b>`; ps.forEach((p) => (html += `<br/>${p.marker} ${p.seriesName}: <b>${fmtVal(p.value, p.seriesName)}</b>`)); return html },
      },
      xAxis: horiz ? vAxes : catAxis,
      yAxis: horiz ? { inverse: true, ...catAxis } : vAxes,
      series: s,
    }),
  }
}

export default function Chart({ payload, onPick, height }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const inst = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const ch = inst.current || echarts.init(ref.current)
    inst.current = ch
    const { option, h, rawCats, dimCol } = buildOption(payload)
    ref.current.style.height = (height || h) + 'px'
    ch.setOption(option, true)
    ch.resize()
    ch.off('click')
    if (onPick && dimCol) ch.on('click', (p: any) => { const v = rawCats[p.dataIndex]; if (v !== undefined) onPick(dimCol, v) })
  }, [payload, onPick, height])

  useEffect(() => {
    const ch = inst.current
    if (!ch || !ref.current) return
    const ro = new ResizeObserver(() => ch.resize())
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  useEffect(() => () => { inst.current?.dispose(); inst.current = null }, [])

  return <div ref={ref} style={{ width: '100%', height: (height || 340) + 'px', cursor: onPick ? 'pointer' : 'default' }} />
}
