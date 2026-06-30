# -*- coding: utf-8 -*-
"""Construye el catalogo del modelo semantico ULima360 leyendo el modelo EN VIVO
(INFO.VIEW.*) via executeQueries. Produce:

  catalog.json      -> machine-readable (validador + selectores de la UI)
  catalogo_llm.md   -> menu compacto que se le da al LLM como contexto

El catalogo es la frontera de gobierno: el LLM solo conoce lo que aqui aparece
(allowlist de tablas/columnas/medidas) y nunca ve datos crudos, solo metadatos.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fabric_client as c  # noqa: E402

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- gobierno: que es sensible (Ley 29733) -------------------------------------
ID_COLUMNS = {"id_persona", "id_alumno", "co_alum", "co_pstl", "co_pers",
              "co_trab", "co_docente", "co_docente_prin"}
# Tablas que NO deben listarse a grano de fila ni siquiera por id (requieren rol):
SENSITIVE_TABLES = {"fact_riesgo_desercion", "fact_socioeconomico"}   # watchlist + nivel socioeconomico (Ley 29733)
# Dominios sensibles (financiero / identidad) -> permitidos AGREGADOS, no a fila:
SENSITIVE_PREFIX = ("fact_fin_",)
IDENTITY_TABLES = {"dim_persona"}


def _rows(dax):
    return c.execute_dax(dax)


def fetch_model():
    tables = _rows("EVALUATE INFO.VIEW.TABLES()")
    columns = _rows("EVALUATE INFO.VIEW.COLUMNS()")
    measures = _rows("EVALUATE INFO.VIEW.MEASURES()")
    rels = _rows("EVALUATE INFO.VIEW.RELATIONSHIPS()")
    return tables, columns, measures, rels


def classify_table(name):
    if name.startswith("fact_"):
        return "hecho"
    if name.startswith("dim_"):
        return "dimension"
    return "otro"


def govern_table(name):
    tags = []
    if name in SENSITIVE_TABLES:
        tags.append("RESTRINGIDA")          # requiere rol; no a grano de fila
    if name.startswith(SENSITIVE_PREFIX):
        tags.append("FINANCIERA")           # agregados ok; fila no
    if name in IDENTITY_TABLES:
        tags.append("IDENTIDAD")
    return tags


def build():
    tables, columns, measures, rels = fetch_model()

    # columnas por tabla (omitimos internas/ocultas y RowNumber)
    cols_by_table = {}
    for col in columns:
        t = col.get("Table") or col.get("Table Name")
        n = col.get("Name") or col.get("Column")
        if not t or not n or str(n).startswith("RowNumber"):
            continue
        if str(col.get("IsHidden")).lower() == "true":
            continue
        cols_by_table.setdefault(t, []).append({
            "columna": n,
            "tipo": col.get("DataType"),
            "es_identificador": n in ID_COLUMNS,
            "descripcion": col.get("Description") or "",
        })

    catalog = {"tablas": [], "medidas": [], "relaciones": []}

    for tbl in tables:
        name = tbl.get("Name")
        if not name or str(tbl.get("IsHidden")).lower() == "true":
            continue
        if str(name).startswith(("DateTableTemplate", "LocalDateTable")):
            continue
        catalog["tablas"].append({
            "tabla": name,
            "tipo": classify_table(name),
            "descripcion": tbl.get("Description") or "",
            "gobierno": govern_table(name),
            "columnas": cols_by_table.get(name, []),
        })

    for m in measures:
        if str(m.get("IsHidden")).lower() == "true":
            continue
        catalog["medidas"].append({
            "medida": m.get("Name"),
            "tabla": m.get("Table"),
            "tipo": m.get("DataType"),
            "descripcion": m.get("Description") or "",
        })

    for r in rels:
        if str(r.get("IsActive")).lower() == "false":
            continue
        catalog["relaciones"].append({
            "desde": "%s[%s]" % (r.get("FromTable"), r.get("FromColumn")),
            "hacia": "%s[%s]" % (r.get("ToTable"), r.get("ToColumn")),
        })

    with open(os.path.join(OUT_DIR, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    write_llm_menu(catalog)
    return catalog


def write_llm_menu(catalog):
    L = []
    L.append("# Catalogo ULima360 (menu para el LLM)\n")
    L.append("Reglas: responde SOLO con medidas y columnas de este catalogo. "
             "Prefiere SIEMPRE las MEDIDAS certificadas sobre recalcular. "
             "Agrupa por columnas de dimension. Nunca devuelvas columnas identificador "
             "(marcadas [id]) a grano de fila. Tablas [RESTRINGIDA]/[FINANCIERA] solo agregadas.\n")

    L.append("## Medidas certificadas (usar estas)\n")
    by_tab = {}
    for m in catalog["medidas"]:
        by_tab.setdefault(m["tabla"], []).append(m)
    for tab, ms in by_tab.items():
        L.append("### %s" % tab)
        for m in ms:
            L.append("- **%s** — %s" % (m["medida"], m["descripcion"]))
        L.append("")

    L.append("## Tablas y columnas (para filtrar/agrupar)\n")
    for t in catalog["tablas"]:
        gov = (" " + " ".join("[%s]" % g for g in t["gobierno"])) if t["gobierno"] else ""
        L.append("### %s (%s)%s" % (t["tabla"], t["tipo"], gov))
        if t["descripcion"]:
            L.append("_%s_" % t["descripcion"])
        cols = []
        for col in t["columnas"]:
            flag = " [id]" if col["es_identificador"] else ""
            cols.append("`%s`%s" % (col["columna"], flag))
        L.append(", ".join(cols))
        L.append("")

    L.append("## Relaciones (joins disponibles)\n")
    for r in catalog["relaciones"]:
        L.append("- %s -> %s" % (r["desde"], r["hacia"]))

    with open(os.path.join(OUT_DIR, "catalogo_llm.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    cat = build()
    print("tablas:", len(cat["tablas"]))
    print("medidas:", len(cat["medidas"]))
    print("relaciones:", len(cat["relaciones"]))
    sens = [t["tabla"] for t in cat["tablas"] if t["gobierno"]]
    print("tablas con gobierno:", sens)
    print("\n-> catalog.json y catalogo_llm.md escritos en", OUT_DIR)
