# -*- coding: utf-8 -*-
"""Scope de seguridad (RLS por inyeccion de filtros).

Toma el SPEC que pidio el usuario/LLM y, segun el scope de la SESION (no del
cliente), agrega filtros OBLIGATORIOS de facultad/carrera antes de construir el
DAX. El usuario nunca puede ensanchar su alcance: los filtros del scope se
agregan con AND y se validan contra el mapa fail-closed (scope_map).

Reglas:
  - nivel 'total'    -> sin filtro (admin/rector/vicerrector): ve todo.
  - nivel 'facultad' -> filtra por la columna de facultad de cada tabla tocada.
  - nivel 'carrera'  -> filtra por la columna de carrera de cada tabla tocada.
  - tabla 'publica'   -> se permite sin filtro (dims de tiempo/espacio).
  - tabla 'denegada'  -> se rechaza la consulta (fail-closed).
  - tabla 'scope' sin columna para el nivel pedido -> se rechaza (no se acota por
    un grano mas amplio: eso seria una fuga).
"""
import os
import json
import unicodedata

import scope_map

HERE = os.path.dirname(os.path.abspath(__file__))
# Configurable para vivir en el volumen persistente del despliegue (lo escribe
# reconciliar.py contra Fabric); por defecto junto al modulo (dev).
RECON_PATH = os.environ.get("VITRINA_SCOPE_VALORES") or os.path.join(HERE, "scope_valores.json")

# Mapa de reconciliacion {nombre_normalizado: valor_exacto_en_gold}. Lo genera
# reconciliar.py contra Fabric. Si no existe, se usa el nombre tal cual (DB2).
_RECON = None


def _normaliza(s):
    """minuscula + sin acentos + colapsa espacios: clave robusta de match."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def _recon():
    global _RECON
    if _RECON is None:
        try:
            with open(RECON_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            _RECON = {_normaliza(k): v for k, v in raw.items()}
        except Exception:
            _RECON = {}
    return _RECON


def _a_gold(valor):
    """Traduce un valor de scope (nombre DB2) al string EXACTO de la tabla gold,
    si hay reconciliacion; si no, lo deja igual."""
    return _recon().get(_normaliza(valor), valor)


class Scope:
    """Alcance efectivo de una sesion. Se construye en el servidor, jamas desde
    el cliente."""

    def __init__(self, nivel, facultades=None, carreras=None):
        assert nivel in ("total", "facultad", "carrera")
        self.nivel = nivel
        self.facultades = list(facultades or [])
        self.carreras = list(carreras or [])

    @property
    def es_total(self):
        return self.nivel == "total"

    def valores(self):
        return self.facultades if self.nivel == "facultad" else self.carreras

    def to_dict(self):
        return {"nivel": self.nivel, "facultades": self.facultades, "carreras": self.carreras}

    @staticmethod
    def from_dict(d):
        d = d or {}
        return Scope(d.get("nivel", "total"), d.get("facultades"), d.get("carreras"))


def _tablas_tocadas(spec, medida_tabla):
    """Conjunto de tablas que toca el SPEC: dimensiones + filtros + la tabla de
    cada medida (medida_tabla: dict medida->tabla del catalogo)."""
    t = set()
    for d in (spec.get("dimensiones") or []):
        if d.get("tabla"):
            t.add(d["tabla"])
    for f in (spec.get("filtros") or []):
        if f.get("tabla"):
            t.add(f["tabla"])
    for m in (spec.get("medidas") or []):
        tb = medida_tabla.get(m)
        if tb:
            t.add(tb)
    return t


def inject(spec, scope, medida_tabla):
    """Devuelve (ok, spec_o_errores, info).

    Si ok: spec_o_errores es el SPEC con los filtros de scope agregados.
    Si no: spec_o_errores es {'errores':[...]} (consulta denegada).
    info: {'inyectados':[...], 'tablas': [...]} para auditoria.
    """
    if scope.es_total:
        return True, spec, {"inyectados": [], "nivel": "total"}

    nivel = scope.nivel
    vals = scope.valores()
    if not vals:
        return False, {"errores": ["Tu usuario no tiene %s asignada(s); sin alcance no se puede consultar." % nivel]}, {}

    tocadas = _tablas_tocadas(spec, medida_tabla)
    errs = []
    inyectados = []
    vals_gold = [_a_gold(v) for v in vals]

    for tabla in sorted(tocadas):
        cls = scope_map.clasificar(tabla)
        if cls == "publica":
            continue
        if cls == "denegada":
            errs.append("Tu rol no tiene acceso a la tabla '%s'." % tabla)
            continue
        # cls == 'scope'
        col = scope_map.columna_para(tabla, nivel)
        if not col:
            errs.append(
                "Tu rol (%s) no puede acceder a '%s' a ese nivel de detalle." % (nivel, tabla))
            continue
        inyectados.append({"tabla": tabla, "columna": col, "op": "in", "valores": vals_gold})

    if errs:
        return False, {"errores": errs}, {"tablas": sorted(tocadas)}

    nuevo = dict(spec)
    nuevo["filtros"] = list(spec.get("filtros") or []) + inyectados
    return True, nuevo, {"inyectados": inyectados, "nivel": nivel, "tablas": sorted(tocadas)}
