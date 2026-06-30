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
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))


def _norm(s):
    """Clave de comparacion laxa para resolver el nombre que pide el LLM contra el catalogo:
    minusculas + sin tildes, y la grafia ASCII 'anio' equiparada a 'año' ('ano').
    Asi 'anio'=='Año', 'programa'=='Programa', 'departamento'=='Departamento'."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip().replace("anio", "ano")
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
        self.col_canon = {}         # (tabla, _norm(col)) -> nombre canonico exacto del catalogo
        self.meas_canon = {}        # _norm(medida) -> nombre canonico exacto
        for t in cat["tablas"]:
            if "RESTRINGIDA" in t.get("gobierno", []):
                self.restricted.add(t["tabla"])
            for col in t["columnas"]:
                key = "%s[%s]" % (t["tabla"], col["columna"])
                self.columns.add(key)
                self.col_canon[(t["tabla"], _norm(col["columna"]))] = col["columna"]
                if col.get("es_identificador"):
                    self.id_columns.add(key)
        for m in cat["medidas"]:
            self.meas_canon[_norm(m["medida"])] = m["medida"]
        self.raw = cat

    def col_key(self, ref):
        return "%s[%s]" % (ref.get("tabla"), ref.get("columna"))

    def resolve_col(self, tabla, columna):
        """Devuelve el nombre canonico de la columna en el catalogo tolerando mayusculas/tildes/
        grafia 'anio'. Si no hay match laxo, devuelve el original (que governance rechazara)."""
        if columna is None:
            return columna
        if "%s[%s]" % (tabla, columna) in self.columns:
            return columna  # ya es exacto
        return self.col_canon.get((tabla, _norm(columna)), columna)

    def resolve_meas(self, medida):
        if medida in self.measures:
            return medida
        return self.meas_canon.get(_norm(medida), medida)


_CAT = None


def catalog():
    global _CAT
    if _CAT is None:
        _CAT = Catalog()
    return _CAT


def normalize_spec_columns(spec):
    """Reescribe in-place los nombres de columna/medida del SPEC al nombre EXACTO del catalogo,
    tolerando diferencias de mayusculas/tildes/grafia (el LLM pide 'anio' y el modelo expone 'Año').
    Evita falsos 'columna no existe' y DAX 400 por nombres equivalentes. Idempotente.
    Devuelve la lista de reescrituras [(ambito, tabla, antes, despues)] para auditoria."""
    cat = catalog()
    cambios = []
    # mapa de columnas reescritas (por tabla) para propagar a orden/viz, que usan nombres "pelados"
    ren = {}
    for d in (spec.get("dimensiones") or []):
        c0 = d.get("columna"); c1 = cat.resolve_col(d.get("tabla"), c0)
        if c1 != c0:
            d["columna"] = c1; ren[c0] = c1; cambios.append(("dim", d.get("tabla"), c0, c1))
    for f in (spec.get("filtros") or []):
        c0 = f.get("columna"); c1 = cat.resolve_col(f.get("tabla"), c0)
        if c1 != c0:
            f["columna"] = c1; ren[c0] = c1; cambios.append(("filtro", f.get("tabla"), c0, c1))
    # orden: puede ser nombre de medida o de columna agrupada
    o0 = spec.get("orden")
    if o0:
        o1 = ren.get(o0) or cat.resolve_meas(o0)
        if o1 != o0:
            spec["orden"] = o1; cambios.append(("orden", None, o0, o1))
    # viz.x (columna del eje) y viz.series (medidas o columnas)
    viz = spec.get("viz") or {}
    if viz.get("x") and ren.get(viz["x"]):
        cambios.append(("viz.x", None, viz["x"], ren[viz["x"]])); viz["x"] = ren[viz["x"]]
    if isinstance(viz.get("series"), list):
        viz["series"] = [ren.get(s) or cat.resolve_meas(s) for s in viz["series"]]
    return cambios


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
