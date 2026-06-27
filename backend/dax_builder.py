# -*- coding: utf-8 -*-
"""Construye DAX determinista a partir de un SPEC validado (no del LLM directo).

El LLM solo elige nombres del catalogo (medidas, columnas, filtros); aqui se
arma el SUMMARIZECOLUMNS/TOPN. Esto elimina alucinacion de sintaxis y garantiza
que los KPIs salen de las medidas certificadas (un solo dueno - mandamiento #1).
"""


def _lit(v):
    """Literal DAX: numero tal cual, texto entre comillas dobles."""
    if isinstance(v, bool):
        return "TRUE()" if v else "FALSE()"
    if isinstance(v, (int, float)):
        return repr(v)
    return '"%s"' % str(v).replace('"', '""')


def _col(ref):
    """ref = {'tabla':..,'columna':..} -> 'tabla'[columna]"""
    return "'%s'[%s]" % (ref["tabla"], ref["columna"])


def _predicate(f):
    col = _col(f)
    op = (f.get("op") or "=").lower()
    if op in ("in", "en"):
        vals = ", ".join(_lit(v) for v in f["valores"])
        return "%s IN {%s}" % (col, vals)
    sym = {"=": "=", "==": "=", ">": ">", ">=": ">=", "<": "<", "<=": "<=", "<>": "<>", "!=": "<>"}.get(op, "=")
    return "%s %s %s" % (col, sym, _lit(f.get("valor")))


def build_from_spec(spec, default_topn=1000):
    """spec: {medidas:[str], dimensiones:[{tabla,columna}], filtros:[{tabla,columna,op,valor|valores}],
              orden:str|None, topn:int|None}
    Devuelve un string DAX 'EVALUATE ...'."""
    medidas = spec.get("medidas") or []
    dims = spec.get("dimensiones") or []
    filtros = spec.get("filtros") or []
    topn = spec.get("topn") or default_topn

    dims_dax = [_col(d) for d in dims]
    meas_dax = ['"%s", [%s]' % (m, m) for m in medidas]
    partes = dims_dax + meas_dax
    inner = "SUMMARIZECOLUMNS(\n    %s\n)" % ",\n    ".join(partes)

    if filtros:
        preds = ", ".join(_predicate(f) for f in filtros)
        inner = "CALCULATETABLE(\n  %s,\n  %s\n)" % (inner, preds)

    # --- orden robusto: separa la direccion y resuelve si es medida o dimension ---
    orden, direction = _split_dir(spec.get("orden"))
    if spec.get("orden_dir"):
        direction = "ASC" if str(spec["orden_dir"]).lower().startswith("asc") else "DESC"
    dim_by_col = {d["columna"]: d for d in dims}

    if orden in set(medidas):
        order_expr = "[%s]" % orden
    elif orden in dim_by_col:
        order_expr = _col(dim_by_col[orden])
    elif medidas:
        order_expr, direction = "[%s]" % medidas[0], "DESC"
    else:
        order_expr = None

    # TOPN solo acota a N (ordena por la medida principal); el ORDER BY fija el display.
    if medidas:
        result = "TOPN(%d, %s, [%s], DESC)" % (topn, inner, medidas[0])
    else:
        result = inner

    dax = "EVALUATE\n%s" % result
    if order_expr:
        dax += "\nORDER BY %s %s" % (order_expr, direction)
    return dax


def _split_dir(s):
    """'Suboferta % desc' -> ('Suboferta %','DESC'); 'anio' -> ('anio','DESC')."""
    if not s:
        return None, "DESC"
    parts = s.strip().rsplit(None, 1)
    if len(parts) == 2 and parts[1].lower() in ("asc", "desc", "ascending", "descending"):
        return parts[0].strip(), ("ASC" if parts[1].lower().startswith("asc") else "DESC")
    return s.strip(), "DESC"


if __name__ == "__main__":
    demo = {
        "medidas": ["Llenado Prom %", "Suboferta %", "Secciones"],
        "dimensiones": [{"tabla": "fact_demanda_seccion", "columna": "departamento_academico"}],
        "filtros": [{"tabla": "fact_demanda_seccion", "columna": "anio", "op": "=", "valor": 2024}],
        "orden": "Suboferta %",
        "topn": 10,
    }
    print(build_from_spec(demo))
