# -*- coding: utf-8 -*-
"""Gobierno: valida un SPEC contra el catalogo y audita cada consulta (Ley 29733).

Reglas (sprint 0):
  - allowlist: cada medida/columna/tabla debe existir en el catalogo.
  - sin identificadores: ninguna columna [id] puede usarse como dimension/filtro
    (evita re-identificacion y dumps a grano de persona).
  - tablas RESTRINGIDA (watchlist de riesgo) requieren rol explicito.
  - se exige al menos una medida (no se permiten dumps de filas crudas).
  - auditoria: cada consulta se registra en audit.log.jsonl.
"""
import os
import json
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(HERE, "catalog.json")
# Path de auditoria configurable (en despliegue apunta a un volumen persistente).
AUDIT_PATH = os.environ.get("VITRINA_AUDIT_PATH") or os.path.join(HERE, "audit.log.jsonl")


def load_catalog():
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


class Catalog:
    def __init__(self):
        cat = load_catalog()
        self.measures = {m["medida"] for m in cat["medidas"]}
        self.tables = {t["tabla"] for t in cat["tablas"]}
        self.columns = set()        # "tabla[col]"
        self.id_columns = set()     # "tabla[col]" marcadas identificador
        self.restricted = set()     # tablas que requieren rol
        for t in cat["tablas"]:
            if "RESTRINGIDA" in t.get("gobierno", []):
                self.restricted.add(t["tabla"])
            for col in t["columnas"]:
                key = "%s[%s]" % (t["tabla"], col["columna"])
                self.columns.add(key)
                if col.get("es_identificador"):
                    self.id_columns.add(key)
        self.raw = cat

    def col_key(self, ref):
        return "%s[%s]" % (ref.get("tabla"), ref.get("columna"))


_CAT = None


def catalog():
    global _CAT
    if _CAT is None:
        _CAT = Catalog()
    return _CAT


def validate_spec(spec, roles=None):
    """Devuelve (ok: bool, errores: [str], tablas_tocadas: set)."""
    roles = set(roles or [])
    cat = catalog()
    errs = []
    touched = set()

    medidas = spec.get("medidas") or []
    if not medidas:
        errs.append("Se requiere al menos una medida certificada (no se permiten dumps de filas).")
    for m in medidas:
        if m not in cat.measures:
            errs.append("Medida no existe en el catalogo: %r" % m)

    for d in (spec.get("dimensiones") or []):
        key = cat.col_key(d)
        touched.add(d.get("tabla"))
        if key not in cat.columns:
            errs.append("Columna no existe: %s" % key)
        elif key in cat.id_columns:
            errs.append("Columna identificador no permitida como dimension: %s" % key)

    OPS = {"=", "==", ">", ">=", "<", "<=", "<>", "!=", "in", "en"}
    for f in (spec.get("filtros") or []):
        key = cat.col_key(f)
        touched.add(f.get("tabla"))
        if key not in cat.columns:
            errs.append("Columna de filtro no existe: %s" % key)
        elif key in cat.id_columns:
            errs.append("No se permite filtrar por identificador: %s" % key)
        if (f.get("op") or "=").lower() not in OPS:
            errs.append("Operador de filtro no permitido: %r en %s" % (f.get("op"), key))

    # tabla de cada medida tambien cuenta como tocada
    for m in cat.raw["medidas"]:
        if m["medida"] in medidas:
            touched.add(m["tabla"])

    for t in touched:
        if t in cat.restricted and "tutoria" not in roles and "admin" not in roles:
            errs.append("Tabla restringida requiere rol (tutoria/admin): %s" % t)

    return (len(errs) == 0, errs, touched)


def audit(evento):
    """Registra un evento (dict) como linea JSON. No incluye datos crudos, solo metadatos."""
    evento = dict(evento)
    evento["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
    d = os.path.dirname(AUDIT_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    ok, errs, touched = validate_spec({
        "medidas": ["Suboferta %"],
        "dimensiones": [{"tabla": "fact_demanda_seccion", "columna": "facultad"}],
    })
    print("ok:", ok, "errs:", errs, "touched:", touched)
    ok2, errs2, _ = validate_spec({
        "medidas": ["En Watchlist"],
        "dimensiones": [{"tabla": "fact_riesgo_desercion", "columna": "id_alumno"}],
    })
    print("ok:", ok2, "errs:", errs2)
