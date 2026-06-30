# -*- coding: utf-8 -*-
"""Siembra el almacen de identidad desde la extraccion real de DB2.

Fuente de datos (en orden):
  1) env VITRINA_SEED_B64  -> CSV en base64 (despliegue: el repo es PUBLICO, los
     nombres/CO_PERS NO se commitean; viajan por el ENV de hPanel, como el cert).
  2) autoridades_db2.csv   -> archivo local (dev).

Crea un usuario por autoridad vigente (rector / decanos / directores de carrera,
extraidos de TRABAJADOR+PUESTO+CARGO+DEPENDENCIA) con su rol y alcance, mas el
usuario 'fernando' (DUIS) = admin / visibilidad total.

Claves: el admin (fernando) toma VITRINA_ADMIN_PASSWORD si esta (sin cambio
forzado); el resto nace con CLAVE TEMPORAL aleatoria + must_change=1, listadas en
credenciales_iniciales.txt (junto a la BD; volumen persistente en el VPS).

IDEMPOTENTE: `sembrar_si_vacio()` (lo llama app.py al arrancar) solo siembra si
la BD no tiene usuarios, asi un redeploy NO pisa las claves ya cambiadas.

Uso CLI:  python seed.py            (siembra / re-siembra)
          python seed.py --reset    (borra identidad.db y re-siembra)
          python seed.py --si-vacio (siembra solo si esta vacia)
"""
import os
import io
import csv
import sys
import base64
import unicodedata
import secrets

import identidad

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "autoridades_db2.csv")
# Credenciales junto a la BD (en el VPS = volumen persistente).
CRED_PATH = os.path.join(os.path.dirname(identidad.DB_PATH) or HERE, "credenciales_iniciales.txt")

# CO_CGO -> (rol, tipo_scope)  ; tipo_scope None = no aplica (total)
CARGO_ROL = {
    "174": ("rector", None),                 # RECTOR
    "73":  ("decano", "facultad"),           # DECANO
    "399": ("decano", "facultad"),           # DECANO A.I.
    "436": ("decano", "facultad"),           # DECANO A.I (variante)
    "458": ("director_carrera", "carrera"),  # DIRECTOR DE CARRERA
    "74":  ("director_carrera", "carrera"),  # DIRECTOR DE PROGRAMA DE EE.GG.
}


def _sin_acentos(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _username(nombre):
    """'OTERO IBANEZ, ELIZABETH RAQUEL' -> 'eotero' (inicial nombre + apellido pat)."""
    ap, _, nom = nombre.partition(",")
    ap_pat = _sin_acentos(ap.strip().split()[0]).lower()
    ini = _sin_acentos(nom.strip().split()[0])[:1].lower() if nom.strip() else ""
    return (ini + ap_pat) or ap_pat


def _temp():
    return secrets.token_urlsafe(6)


def _csv_texto():
    """Devuelve el texto CSV de autoridades, de VITRINA_SEED_B64 o del archivo.
    None si no hay ninguna fuente (despliegue sin sembrar autoridades)."""
    b64 = os.environ.get("VITRINA_SEED_B64")
    if b64:
        return base64.b64decode(b64).decode("utf-8-sig")
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, encoding="utf-8-sig") as f:
            return f.read()
    return None


def cargar_autoridades():
    txt = _csv_texto()
    if not txt:
        return []
    filas = []
    for row in csv.DictReader(io.StringIO(txt)):
        filas.append({k.strip(): (v or "").strip() for k, v in row.items()})
    return filas


def hay_usuarios():
    with identidad.conn() as c:
        return c.execute("SELECT COUNT(*) n FROM usuario").fetchone()["n"] > 0


def sembrar(admin_password=None, escribir_creds=True):
    identidad.init_db()
    admin_password = admin_password or os.environ.get("VITRINA_ADMIN_PASSWORD")
    creds = []
    usados = set()

    # --- DUIS: fernando = admin / total ---
    if admin_password:
        clave_admin, forzar_admin = admin_password, False
        nota_admin = "(VITRINA_ADMIN_PASSWORD)"
    else:
        clave_admin, forzar_admin = _temp(), True
        nota_admin = clave_admin
    identidad.crear_usuario("fernando", "KATO GORAY, Fernando Roberto", 50424, clave_admin,
                            roles=["admin"], scopes=[], must_change=forzar_admin)
    creds.append(("fernando", "KATO GORAY, Fernando Roberto", "admin", "TOTAL", nota_admin))
    usados.add("fernando")

    # --- autoridades reales (CSV / env) ---
    for r in cargar_autoridades():
        mapeo = CARGO_ROL.get(r.get("CO_CGO"))
        if not mapeo:
            continue
        rol, tipo = mapeo
        nombre = r.get("NOMBRE")
        co_pers = int(r["CO_PERS"]) if r.get("CO_PERS") else None
        dep = r.get("DEPENDENCIA")
        u = base = _username(nombre)
        i = 2
        while u in usados:
            u, i = "%s%d" % (base, i), i + 1
        usados.add(u)
        scopes = [(tipo, dep)] if tipo else []
        clave = _temp()
        identidad.crear_usuario(u, nombre, co_pers, clave, roles=[rol], scopes=scopes, must_change=True)
        creds.append((u, nombre, rol, (dep if tipo else "TOTAL"), clave))

    if escribir_creds:
        d = os.path.dirname(CRED_PATH)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(CRED_PATH, "w", encoding="utf-8") as f:
            f.write("# Credenciales iniciales vitrina360 - CLAVE TEMPORAL (cambio obligatorio 1er ingreso)\n")
            f.write("# NO commitear. Distribuir por canal seguro y borrar este archivo.\n\n")
            for u, nombre, rol, alc, clave in creds:
                f.write("%-14s %-44s %-18s %s\n" % (u, nombre[:44], rol, alc))
                f.write("%-14s %s\n\n" % ("", "clave: " + clave))

    print("Sembrados %d usuarios en %s" % (len(creds), identidad.DB_PATH))
    print("Credenciales -> %s" % CRED_PATH)
    return len(creds)


def sembrar_si_vacio():
    """Para el arranque del servidor: siembra solo si la BD no tiene usuarios."""
    identidad.init_db()
    if hay_usuarios():
        return 0
    if not _csv_texto() and not os.environ.get("VITRINA_ADMIN_PASSWORD"):
        return 0   # sin fuente: no hay nada que sembrar (best-effort)
    return sembrar()


if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(identidad.DB_PATH):
        os.remove(identidad.DB_PATH)
        print("identidad.db borrada.")
    if "--si-vacio" in sys.argv:
        n = sembrar_si_vacio()
        print("sin cambios (ya habia usuarios)" if n == 0 else "sembrado")
    else:
        sembrar()
