# -*- coding: utf-8 -*-
"""NL -> SPEC con Claude. El LLM NO escribe DAX: elige medidas/columnas/filtros del
catalogo y propone el tipo de grafico. El servidor valida y construye el DAX.

Requiere ANTHROPIC_API_KEY. Modelo configurable con VITRINA_MODEL (default sonnet).
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("VITRINA_MODEL", "claude-sonnet-4-6")

with open(os.path.join(HERE, "catalogo_llm.md"), encoding="utf-8") as f:
    CATALOGO = f.read()

SYSTEM = """Eres el motor analitico de ULima360 (data lake de la Universidad de Lima).
Conviertes una pregunta en lenguaje natural en una CONSULTA estructurada (spec) usando
EXCLUSIVAMENTE el catalogo de abajo. No escribes DAX. No inventas nombres.

Reglas:
- Puede haber CONVERSACION previa. Si la nueva pregunta es un AJUSTE del resultado anterior
  (cambiar dimension, agregar/quitar un filtro o anio, cambiar el orden, el tipo de grafico o el
  top N, agregar/quitar una medida), PARTE del ultimo spec generado y cambia SOLO lo necesario,
  conservando el resto. Si es claramente una pregunta nueva, ignora el contexto previo.
- Usa SOLO medidas certificadas (las de la seccion "Medidas certificadas") por su nombre exacto.
- Las medidas y las dimensiones deben salir de la MISMA tabla de hecho (sus columnas estan
  denormalizadas en el hecho). Ej: "matricula" -> fact_matricula_ciclo o FTE en fact_fte_periodo;
  NUNCA mezcles una medida de una tabla con una columna de otra (no hay joins entre hechos).
- Para "matricula"/"alumnos matriculados" usa fact_matricula_ciclo o fact_fte_periodo (FTE Total).
  NUNCA uses fact_riesgo_desercion ni medidas de riesgo para responder sobre matricula.
- Si la columna pedida (p.ej. "facultad") no existe en la tabla del hecho, usa la mas cercana
  que SI exista alli (p.ej. en fact_demanda_seccion: departamento_academico o dependencia).
- Nunca uses columnas marcadas [id] como dimension o filtro.
- Tablas [RESTRINGIDA] o [FINANCIERA]: solo agregados; no las uses salvo que la pregunta lo pida.
- FILTROS: agrega un filtro SOLO si el usuario lo pide explicitamente (un anio, una modalidad...).
  No inventes filtros. op debe ser uno de: = > >= < <= <> in. Para "in" usa "valores":[...].
- UN SOLO filtro de tiempo: si filtras por un ciclo/periodo (id_ciclo, p.ej. 20252 para "2025-2"),
  NO agregues ademas un filtro de anio: el ciclo ya implica el anio. Para "ciclo 2025-2" usa solo
  id_ciclo=20252. Filtra por anio SOLO cuando el usuario pide un anio sin especificar ciclo.
- NOMBRES EXACTOS: copia el nombre de la columna TAL CUAL aparece en el catalogo, respetando
  mayusculas y tildes (p.ej. 'Año', 'Programa', 'Departamento'). No lo pases a minusculas ni le
  quites tildes ni cambies 'Año' por 'anio'.
- ORDEN: "orden" es el nombre EXACTO de una medida o de una columna agrupada, SIN 'asc'/'desc'.
  La direccion va en "orden_dir" ("asc" o "desc"). Para evolucion temporal ordena por el periodo
  (anio/ciclo) en "asc".
- Elige el grafico adecuado: barra (ranking/comparacion), linea (evolucion por ciclo/anio),
  kpi (un solo numero), circular (composicion <=6 partes), tabla (detalle).
- Si la pregunta es ambigua o pide algo fuera del catalogo, usa intencion "aclarar" o
  "fuera_de_alcance" y explica brevemente.
- La narrativa describe que se va a mostrar en 1-2 frases; NUNCA inventes cifras.

CATALOGO:
""" + CATALOGO

TOOL = {
    "name": "responder",
    "description": "Devuelve la consulta estructurada para ejecutar contra ULima360.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intencion": {"type": "string", "enum": ["consulta", "aclarar", "fuera_de_alcance"]},
            "titulo": {"type": "string"},
            "medidas": {"type": "array", "items": {"type": "string"}},
            "dimensiones": {
                "type": "array",
                "items": {"type": "object",
                          "properties": {"tabla": {"type": "string"}, "columna": {"type": "string"}},
                          "required": ["tabla", "columna"]},
            },
            "filtros": {
                "type": "array",
                "items": {"type": "object",
                          "properties": {
                              "tabla": {"type": "string"}, "columna": {"type": "string"},
                              "op": {"type": "string", "enum": ["=", ">", ">=", "<", "<=", "<>", "in"]},
                              "valor": {},
                              "valores": {"type": "array"},
                          },
                          "required": ["tabla", "columna", "op"]},
            },
            "orden": {"type": ["string", "null"], "description": "nombre EXACTO de una medida o columna agrupada, SIN 'asc'/'desc'"},
            "orden_dir": {"type": ["string", "null"], "enum": ["asc", "desc", None]},
            "topn": {"type": ["integer", "null"]},
            "viz": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": ["barra", "linea", "kpi", "circular", "area", "tabla"]},
                    "x": {"type": ["string", "null"]},
                    "series": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["tipo", "series"],
            },
            "narrativa": {"type": "string"},
            "mensaje": {"type": "string"},
        },
        "required": ["intencion", "titulo", "viz", "narrativa"],
    },
}


def _client():
    import anthropic
    return anthropic.Anthropic()


def pregunta_a_spec(pregunta, errores_previos=None, historial=None):
    """Devuelve el dict del spec (input del tool).

    errores_previos: lista para el reintento de reparacion.
    historial: lista de turnos previos [{pregunta, spec}] para refinamiento conversacional.
    """
    msgs = []
    for turn in (historial or [])[-6:]:
        q = (turn or {}).get("pregunta")
        if not q:
            continue
        msgs.append({"role": "user", "content": q})
        sp = turn.get("spec")
        msgs.append({"role": "assistant",
                     "content": ("Consulta generada: " + json.dumps(sp, ensure_ascii=False))
                     if sp else "(sin consulta)"})

    user = pregunta
    if errores_previos:
        user += ("\n\n[CORRIGE] La consulta anterior fue rechazada por el validador:\n- "
                 + "\n- ".join(errores_previos)
                 + "\nUsa solo nombres exactos del catalogo.")
    msgs.append({"role": "user", "content": user})

    resp = _client().messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM,
        messages=msgs,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "responder"},
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input
    raise RuntimeError("El modelo no devolvio un spec.")
