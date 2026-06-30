# -*- coding: utf-8 -*-
"""Mapa de SCOPING fila-a-fila (RLS) por tabla gold del modelo ULima360.

Para cada tabla dice por que COLUMNA se acota la visibilidad de facultad y de
carrera. Es el corazon de la segmentacion: el backend inyecta un filtro
obligatorio sobre estas columnas segun el scope de la sesion (decano -> su
facultad; director de carrera -> su carrera).

POLITICA FAIL-CLOSED:
  - SCOPE      : tabla con columna de facultad y/o carrera -> se inyecta filtro.
  - PUBLICA    : tabla sin grano de facultad y SEGURA para todos (dims de
                 tiempo/espacio). No se filtra; visible para cualquier rol.
  - (resto)    : cualquier tabla que NO este en SCOPE ni en PUBLICA queda
                 DENEGADA para usuarios acotados (no-total). Incluye financieras,
                 identidad y facts academicas sin columna de facultad/carrera
                 (fact_demanda_seccion, fact_matricula_ciclo,
                 fact_utilizacion_ambiente) -> se habilitan en Fase 1.5 cuando se
                 mapee departamento_academico -> facultad via la conformada.

Los nombres de columna salen del inventario real de catalog.json (los nombres
varian por tabla: facultad / facultad_programa / facultad_postula, etc.).
"""

# tabla -> {"facultad": <col|None>, "carrera": <col|None>}
SCOPE = {
    "fact_admision":            {"facultad": "facultad", "carrera": "carrera_postulada"},
    "fact_admision_conversion": {"facultad": "facultad", "carrera": "carrera_postulada"},
    "fact_examen_admision":     {"facultad": "facultad_postula", "carrera": "carrera_postula"},
    "fact_cohorte":             {"facultad": "facultad", "carrera": "carrera"},
    "fact_fte_periodo":         {"facultad": "facultad", "carrera": "carrera"},
    "fact_retencion":           {"facultad": "facultad", "carrera": "carrera"},
    "fact_riesgo_desercion":    {"facultad": "facultad", "carrera": "carrera"},
    "fact_beneficio":           {"facultad": "facultad", "carrera": "carrera"},
    "fact_solicitud_beneficio": {"facultad": "facultad", "carrera": "carrera"},
    "fact_socioeconomico":      {"facultad": "facultad", "carrera": "carrera"},
    "fact_matricula_cpu":       {"facultad": "facultad", "carrera": "carrera"},
    "fact_nota_curso":          {"facultad": "facultad_programa", "carrera": "carrera"},
    "fact_graduacion":          {"facultad": "facultad_programa", "carrera": "carrera"},
    "fact_rendimiento_ciclo":   {"facultad": "facultad_programa", "carrera": None},
    "fact_test_escolar":        {"facultad": None, "carrera": "carrera_interes"},
    "dim_carrera":              {"facultad": "facultad", "carrera": "carrera"},
    "dim_alumno":               {"facultad": "facultad", "carrera": "carrera"},
    "dim_especialidad":         {"facultad": "facultad", "carrera": None},
}

# Dimensiones sin grano de facultad, seguras para cualquier rol (no se filtran).
PUBLICA = {
    "dim_ciclo",
    "dim_ambiente",
}


def clasificar(tabla):
    """Devuelve 'scope' | 'publica' | 'denegada' para una tabla."""
    if tabla in SCOPE:
        return "scope"
    if tabla in PUBLICA:
        return "publica"
    return "denegada"


def columna_para(tabla, nivel):
    """Columna por la que se acota una tabla scopeable segun el nivel del scope.
    nivel: 'facultad' | 'carrera'. Devuelve None si la tabla no soporta ese grano
    (-> el llamador debe DENEGAR: fail-closed, nunca acotar por un grano mas amplio)."""
    m = SCOPE.get(tabla)
    if not m:
        return None
    return m.get(nivel)
