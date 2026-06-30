# -*- coding: utf-8 -*-
"""Pruebas offline del nucleo de seguridad (sin Fabric ni LLM).

Verifica: hash de clave, JWT firmado, computo de scope por rol e inyeccion de
filtros fail-closed. Corre:  python test_seguridad.py
"""
import os
os.environ.setdefault("VITRINA_JWT_SECRET", "test-secret-0123456789")

import identidad
import session as sesion
import scope as scope_mod

MEDIDA_TABLA = {
    "Postulantes": "fact_admision",
    "Matriculados": "dim_alumno",
    "Deuda Abierta": "fact_fin_deuda",      # FINANCIERA -> denegada a no-total
    "Aulas Subutil %": "fact_demanda_seccion",  # sin facultad/carrera -> denegada
    "En Watchlist": "fact_riesgo_desercion",
}

fallos = []


def check(cond, msg):
    print(("  OK  " if cond else " FALLA ") + msg)
    if not cond:
        fallos.append(msg)


def main():
    # --- clave ---
    salt, h = identidad.hash_pwd("secreta123")
    check(identidad.verify_pwd("secreta123", salt, h), "verify_pwd acepta clave correcta")
    check(not identidad.verify_pwd("otra", salt, h), "verify_pwd rechaza clave incorrecta")

    # --- JWT ---
    tok = sesion.crear_token({"sub": "x", "nombre": "X", "roles": ["decano"],
                              "scope": {"nivel": "facultad", "facultades": ["FACULTAD DE INGENIERIA"]}})
    p = sesion.leer_token(tok)
    check(p and p["sub"] == "x", "JWT round-trip valido")
    check(sesion.leer_token(tok[:-3] + "xxx") is None, "JWT con firma alterada se rechaza")

    # --- scope por rol ---
    s_admin = identidad.scope_de(["admin"], [], [])
    check(s_admin.es_total, "admin -> scope total")
    s_dec = identidad.scope_de(["decano"], ["FACULTAD DE INGENIERIA"], [])
    check(s_dec.nivel == "facultad" and s_dec.facultades == ["FACULTAD DE INGENIERIA"], "decano -> scope facultad")
    s_dir = identidad.scope_de(["director_carrera"], [], ["CARRERA DE INGENIERIA DE SISTEMAS"])
    check(s_dir.nivel == "carrera", "director_carrera -> scope carrera")

    # --- inyeccion: TOTAL no filtra ---
    spec = {"medidas": ["Postulantes"], "dimensiones": [{"tabla": "fact_admision", "columna": "facultad"}], "filtros": []}
    ok, out, info = scope_mod.inject(dict(spec), s_admin, MEDIDA_TABLA)
    check(ok and not out.get("filtros"), "TOTAL: sin filtro inyectado")

    # --- inyeccion: DECANO filtra por facultad ---
    ok, out, info = scope_mod.inject(dict(spec), s_dec, MEDIDA_TABLA)
    fil = (out.get("filtros") or [])
    check(ok and any(f["columna"] == "facultad" and f["op"] == "in" for f in fil), "DECANO: inyecta facultad IN (...)")

    # --- inyeccion: DIRECTOR sobre tabla con carrera ---
    spec_car = {"medidas": ["Matriculados"], "dimensiones": [{"tabla": "dim_alumno", "columna": "carrera"}], "filtros": []}
    ok, out, info = scope_mod.inject(dict(spec_car), s_dir, MEDIDA_TABLA)
    fil = (out.get("filtros") or [])
    check(ok and any(f["columna"] == "carrera" for f in fil), "DIRECTOR: inyecta carrera IN (...)")

    # --- fail-closed: DIRECTOR sobre tabla solo-facultad se DENIEGA ---
    spec_fac = {"medidas": [], "dimensiones": [{"tabla": "fact_rendimiento_ciclo", "columna": "facultad_programa"}], "filtros": []}
    ok, out, info = scope_mod.inject(dict(spec_fac), s_dir, MEDIDA_TABLA)
    check(not ok, "FAIL-CLOSED: director sobre tabla solo-facultad denegada")

    # --- fail-closed: financiera denegada a decano ---
    spec_fin = {"medidas": ["Deuda Abierta"], "dimensiones": [], "filtros": []}
    ok, out, info = scope_mod.inject(dict(spec_fin), s_dec, MEDIDA_TABLA)
    check(not ok, "FAIL-CLOSED: financiera denegada a decano")

    # --- fail-closed: tabla sin facultad/carrera denegada a decano ---
    spec_dem = {"medidas": ["Aulas Subutil %"], "dimensiones": [], "filtros": []}
    ok, out, info = scope_mod.inject(dict(spec_dem), s_dec, MEDIDA_TABLA)
    check(not ok, "FAIL-CLOSED: tabla sin grano de facultad denegada a decano")

    # --- publica: dim_ciclo permitida a decano ---
    spec_pub = {"medidas": ["Postulantes"], "dimensiones": [{"tabla": "dim_ciclo", "columna": "anio"}], "filtros": []}
    ok, out, info = scope_mod.inject(dict(spec_pub), s_dec, MEDIDA_TABLA)
    check(ok, "PUBLICA: dim_ciclo permitida (filtra solo el fact de la medida)")

    print("\n%s" % ("TODO OK" if not fallos else "FALLOS: %d" % len(fallos)))
    return 0 if not fallos else 1


if __name__ == "__main__":
    raise SystemExit(main())
