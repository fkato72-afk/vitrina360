# -*- coding: utf-8 -*-
"""Reconcilia los nombres de facultad/carrera de DB2 con los valores EXACTOS de
las tablas gold (Fabric/ULima360) y escribe scope_valores.json.

scope.py usa ese archivo para traducir el alcance del usuario (nombre tomado de
la dependencia en DB2) al string literal con que la columna gold filtra en DAX,
tolerando diferencias de acento/mayusculas (match por forma normalizada).

Correr UNA vez (y tras cambios de nomenclatura) donde haya token de Power BI:
    python -c "import fabric_client as c; c.login()"   # si hace falta (dev)
    python reconciliar.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
import fabric_client

HERE = os.path.dirname(os.path.abspath(__file__))
# Misma ruta que lee scope.py (configurable para el volumen del despliegue).
OUT = os.environ.get("VITRINA_SCOPE_VALORES") or os.path.join(HERE, "scope_valores.json")


def _distintos(dax):
    try:
        filas = fabric_client.execute_dax(dax)
    except Exception as e:
        print("  ! fallo DAX:", str(e)[:160])
        return []
    out = []
    for r in filas:
        for v in r.values():
            if v not in (None, ""):
                out.append(str(v))
    return out


def main():
    valores = set()
    # La conformada dim_carrera tiene facultad y carrera canonicas.
    valores |= set(_distintos("EVALUATE VALUES(dim_carrera[facultad])"))
    valores |= set(_distintos("EVALUATE VALUES(dim_carrera[carrera])"))
    valores |= set(_distintos("EVALUATE VALUES(dim_especialidad[facultad])"))
    valores = {v for v in valores if v.strip()}

    mapa = {v: v for v in sorted(valores)}   # scope.py normaliza la clave al leer
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)
    print("Escritos %d valores gold -> %s" % (len(mapa), OUT))


if __name__ == "__main__":
    main()
