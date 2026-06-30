// Configuración de tableros cross-filter por dominio DPA (consumo sobre ULima360).
// Cada uno: tabla (hecho), KPIs (medidas certificadas) y paneles (medida × dimensión).
export type Panel = {
  titulo: string; medida: string; dim: string
  viz: 'barra' | 'linea' | 'circular'; topn?: number; orden?: string; dir?: 'asc' | 'desc'; wide?: boolean
}
export type DashCfg = { id: string; nombre: string; tabla: string; titulo: string; sub: string; kpis: string[]; panels: Panel[] }

export const DASHBOARDS: DashCfg[] = [
  { id: 'admision', nombre: 'Admisión', tabla: 'fact_admision', titulo: 'Admisión',
    sub: 'Embudo postulante → admitido → matriculado · clic en una barra para filtrar todo',
    kpis: ['Postulantes', 'Admitidos', 'Tasa Admision %'],
    panels: [
      { titulo: 'Admitidos por facultad', medida: 'Admitidos', dim: 'facultad', viz: 'barra', topn: 15, wide: true },
      { titulo: 'Postulantes por año', medida: 'Postulantes', dim: 'anio', viz: 'linea', orden: 'anio', dir: 'asc', topn: 60 },
      { titulo: 'Postulantes por modalidad', medida: 'Postulantes', dim: 'modalidad', viz: 'barra', topn: 10 },
      { titulo: 'Admitidos por carrera postulada', medida: 'Admitidos', dim: 'carrera_postulada', viz: 'barra', topn: 15 },
    ] },
  { id: 'becas', nombre: 'Becas', tabla: 'fact_beneficio', titulo: 'Becas / Beneficios',
    sub: 'Beneficios otorgados, montos y créditos beneficiados',
    kpis: ['Beneficios Otorgados', 'Monto Beneficiado S/', 'Alumnos Beneficiados'],
    panels: [
      { titulo: 'Beneficios por facultad', medida: 'Beneficios Otorgados', dim: 'facultad', viz: 'barra', topn: 15, wide: true },
      { titulo: 'Monto beneficiado por año', medida: 'Monto Beneficiado S/', dim: 'anio', viz: 'linea', orden: 'anio', dir: 'asc', topn: 60 },
      { titulo: 'Beneficios por tipo', medida: 'Beneficios Otorgados', dim: 'tipo_beneficio', viz: 'barra', topn: 10 },
      { titulo: 'Beneficios por motivo', medida: 'Beneficios Otorgados', dim: 'motivo', viz: 'barra', topn: 12 },
      { titulo: 'Beneficios por sexo', medida: 'Beneficios Otorgados', dim: 'sexo', viz: 'circular', topn: 6 },
    ] },
  { id: 'rendimiento', nombre: 'Rendimiento', tabla: 'fact_nota_curso', titulo: 'Rendimiento académico',
    sub: 'Notas, aprobación y desaprobación por curso',
    kpis: ['Notas Registradas', 'Tasa Aprobación %', 'Nota Promedio'],
    panels: [
      { titulo: 'Tasa de aprobación por facultad', medida: 'Tasa Aprobación %', dim: 'facultad_programa', viz: 'barra', topn: 15, wide: true },
      { titulo: 'Tasa de aprobación por año', medida: 'Tasa Aprobación %', dim: 'Año', viz: 'linea', orden: 'Año', dir: 'asc', topn: 60 },
      { titulo: 'Desaprobados por departamento', medida: 'Desaprobados', dim: 'Departamento', viz: 'barra', topn: 15 },
      { titulo: 'Notas por sexo', medida: 'Notas Registradas', dim: 'genero', viz: 'circular', topn: 6 },
    ] },
  { id: 'retencion', nombre: 'Retención', tabla: 'fact_retencion', titulo: 'Retención y deserción',
    sub: 'Deserción por alumno-ciclo (transiciones observables)',
    kpis: ['Desercion %'],
    panels: [
      { titulo: 'Deserción % por facultad', medida: 'Desercion %', dim: 'facultad', viz: 'barra', topn: 15, wide: true },
      { titulo: 'Deserción % por año', medida: 'Desercion %', dim: 'anio', viz: 'linea', orden: 'anio', dir: 'asc', topn: 60 },
      { titulo: 'Deserción % por situación', medida: 'Desercion %', dim: 'situacion', viz: 'barra', topn: 10 },
    ] },
  { id: 'grados', nombre: 'Grados', tabla: 'fact_graduacion', titulo: 'Grados y títulos',
    sub: 'Diplomas otorgados (bachiller / título / posgrado)',
    kpis: ['Graduaciones', 'Bachilleres', 'Títulos'],
    panels: [
      { titulo: 'Graduaciones por facultad', medida: 'Graduaciones', dim: 'facultad_programa', viz: 'barra', topn: 15, wide: true },
      { titulo: 'Graduaciones por año', medida: 'Graduaciones', dim: 'Año', viz: 'linea', orden: 'Año', dir: 'asc', topn: 40 },
      { titulo: 'Graduaciones por tipo de diploma', medida: 'Graduaciones', dim: 'tipo_diploma', viz: 'barra', topn: 8 },
    ] },
  { id: 'captacion', nombre: 'Captación', tabla: 'fact_test_escolar', titulo: 'Captación escolar',
    sub: 'Test a escolares (PEAU): asistencia y puntaje',
    kpis: ['Escolares Evaluados', 'Pct Asistencia Test', 'Puntaje Test Promedio'],
    panels: [
      { titulo: 'Escolares por carrera de interés', medida: 'Escolares Evaluados', dim: 'carrera_interes', viz: 'barra', topn: 15, wide: true },
      { titulo: 'Escolares por año', medida: 'Escolares Evaluados', dim: 'anio', viz: 'linea', orden: 'anio', dir: 'asc', topn: 40 },
      { titulo: 'Escolares por nivel', medida: 'Escolares Evaluados', dim: 'nivel_escolar', viz: 'barra', topn: 10 },
      { titulo: 'Escolares por sexo', medida: 'Escolares Evaluados', dim: 'sexo', viz: 'circular', topn: 6 },
    ] },
  { id: 'socioeconomico', nombre: 'Socioecon.', tabla: 'fact_socioeconomico', titulo: 'Nivel socioeconómico',
    sub: 'Ficha socioeconómica (rescate; banda v1 — solo agregado, Ley 29733)',
    kpis: ['Fichas Socioeconomicas', 'Puntaje Valorizacion Prom'],
    panels: [
      { titulo: 'Fichas por nivel socioeconómico', medida: 'Fichas Socioeconomicas', dim: 'nivel_socioeconomico', viz: 'barra', topn: 6, wide: true },
      { titulo: 'Fichas por facultad', medida: 'Fichas Socioeconomicas', dim: 'facultad', viz: 'barra', topn: 15 },
      { titulo: 'Fichas por año', medida: 'Fichas Socioeconomicas', dim: 'anio', viz: 'linea', orden: 'anio', dir: 'asc', topn: 40 },
    ] },
  { id: 'demanda', nombre: 'Demanda', tabla: 'fact_demanda_seccion', titulo: 'Demanda académica',
    sub: 'Oferta y llenado de secciones',
    kpis: ['Secciones', 'Llenado Prom %', 'Suboferta %'],
    panels: [
      { titulo: 'Llenado promedio por departamento', medida: 'Llenado Prom %', dim: 'departamento_academico', viz: 'barra', topn: 15, wide: true },
      { titulo: 'Llenado promedio por año', medida: 'Llenado Prom %', dim: 'anio', viz: 'linea', orden: 'anio', dir: 'asc', topn: 50 },
      { titulo: 'Secciones por tipo de curso', medida: 'Secciones', dim: 'tipo_curso', viz: 'barra', topn: 12 },
      { titulo: 'Suboferta por tipo de dependencia', medida: 'Suboferta %', dim: 'tipo_dependencia', viz: 'barra', topn: 12 },
      { titulo: 'Secciones por turno', medida: 'Secciones', dim: 'turno', viz: 'circular', topn: 8 },
    ] },
]
