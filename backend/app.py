# -*- coding: utf-8 -*-
"""API de vitrina360 (FastAPI).

Endpoints:
  GET  /api/health
  GET  /api/catalog            -> catalogo (medidas/tablas) para los selectores de la UI
  POST /api/query   {spec}     -> camino determinista (vitrina): valida -> DAX -> datos
  POST /api/ask     {pregunta} -> camino LLM (chat): NL -> spec -> valida -> DAX -> datos
Sirve el front estatico en /.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "seguridad"))   # imports planos del paquete de seguridad

from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import fabric_client
import dax_builder
import governance
import router

import identidad
import session as sesion
import scope as scope_mod

FRONT = os.path.normpath(os.path.join(HERE, "..", "frontend"))


def _load_env():
    """Carga .env (raiz del proyecto o backend/) al entorno, sin dependencias."""
    for p in (os.path.join(HERE, "..", ".env"), os.path.join(HERE, ".env")):
        p = os.path.normpath(p)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def _ensure_catalog():
    """En despliegue el repo NO trae el catalogo (queda generico/publico-seguro):
    se genera del modelo al arrancar usando el service principal. Best-effort —
    si el SP aun no propaga, la app arranca igual (catalogo se generara luego)."""
    if os.path.exists(os.path.join(HERE, "catalog.json")):
        return
    try:
        import build_catalog
        build_catalog.build()
        print("[startup] catalogo generado desde ULima360", flush=True)
    except Exception as e:
        print("[startup] catalogo aun no generado (SP sin acceso?):", str(e)[:200], flush=True)


_ensure_catalog()

# Almacen de identidad local (POC). Auto-siembra SOLO si esta vacio (un redeploy
# NO pisa las claves ya cambiadas). Fuente: VITRINA_SEED_B64 (env) o CSV local.
identidad.init_db()
try:
    import seed as _seed
    n = _seed.sembrar_si_vacio()
    if n:
        print("[startup] identidad sembrada: %d usuarios" % n, flush=True)
except Exception as e:
    print("[startup] identidad no sembrada:", str(e)[:200], flush=True)

# Reconciliacion de valores facultad/carrera contra el modelo (best-effort): da
# los strings EXACTOS de las tablas gold para que los filtros de scope acierten.
# Necesita token Fabric (cert en el contenedor); si falla, scope usa nombres DB2.
try:
    import reconciliar as _recon
    _recon.main()
except Exception as e:
    print("[startup] reconciliacion de scope omitida:", str(e)[:200], flush=True)

# Mapa medida -> tabla (para que el scope sepa que tabla toca cada medida).
def _medida_tabla():
    try:
        return {m["medida"]: m["tabla"] for m in governance.catalog().raw["medidas"]}
    except Exception:
        return {}

MEDIDA_TABLA = _medida_tabla()

# CORS configurable (en despliegue acotar al origen real); por defecto * para dev.
# La SPA se sirve same-origin, asi que CORS solo aplica al dev cross-origin (vite).
_origins = [o.strip() for o in os.environ.get("VITRINA_CORS", "*").split(",")]
app = FastAPI(title="vitrina360", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


class Spec(BaseModel):
    medidas: list = []
    dimensiones: list = []
    filtros: list = []
    orden: str | None = None
    orden_dir: str | None = None
    topn: int | None = None
    roles: list = []


class Pregunta(BaseModel):
    pregunta: str
    roles: list = []
    historial: list = []


def _ejecutar(spec_dict, ses, pregunta=""):
    """ses: sesion.Sesion (identidad + scope resuelto en el servidor)."""
    usuario = ses.username
    roles = ses.roles
    # 1) SEGURIDAD: inyecta los filtros de scope ANTES de validar/construir DAX.
    ok, spec_dict, sc_info = scope_mod.inject(spec_dict, ses.scope, MEDIDA_TABLA)
    if not ok:
        governance.audit({"origen": "scope", "ok": False, "usuario": usuario, "roles": roles,
                          "scope": ses.scope.to_dict(), "errores": spec_dict.get("errores"),
                          "tablas": sc_info.get("tablas")})
        return False, {"ok": False, "errores": spec_dict["errores"]}
    # 2) Gobierno compartido (agnostico al plano): valida ANTES de despachar.
    ok, errs, touched = governance.validate_spec(spec_dict, roles=roles)
    if not ok:
        governance.audit({"origen": "validacion", "ok": False, "usuario": usuario,
                          "errores": errs, "spec": spec_dict})
        return False, {"ok": False, "errores": errs}
    # 3) Router: decide el plano y devuelve el ejecutor (Fase 0: siempre analitico/Fabric).
    plano, executor = router.route(spec_dict, pregunta)
    res = executor.ejecutar(spec_dict, {"roles": roles})
    if not res.ok:
        governance.audit({"origen": "ejecucion", "ok": False, "plano": plano, "usuario": usuario,
                          "error": res.error, "consulta": res.consulta})
        return False, {"ok": False, "errores": [res.error], "dax": res.consulta}
    governance.audit({"origen": "ejecucion", "ok": True, "plano": plano, "filas": len(res.filas),
                      "usuario": usuario, "roles": roles, "scope": ses.scope.to_dict(),
                      "inyectados": sc_info.get("inyectados"),
                      "tablas": list(touched), "medidas": spec_dict.get("medidas")})
    cols = list(res.filas[0].keys()) if res.filas else []
    return True, {"ok": True, "dax": res.consulta, "columnas": cols, "filas": res.filas}


class Login(BaseModel):
    username: str
    password: str


class CambioClave(BaseModel):
    actual: str
    nueva: str


@app.get("/api/health")
def health():
    return {"ok": True, "dataset": fabric_client.DATASET_ID, "token": bool(fabric_client.token())}


# ---------------- Autenticacion ----------------
@app.post("/api/auth/login")
def login(body: Login, resp: Response):
    perfil = identidad.autenticar(body.username.strip(), body.password)
    if not perfil:
        governance.audit({"origen": "login", "ok": False, "usuario": body.username.strip()})
        return JSONResponse({"ok": False, "error": "Usuario o contrasena invalidos."}, status_code=401)
    tok = sesion.crear_token({"sub": perfil["username"], "nombre": perfil["nombre"],
                              "roles": perfil["roles"], "scope": perfil["scope"],
                              "must_change": perfil["must_change"]})
    sesion.set_cookie(resp, tok)
    governance.audit({"origen": "login", "ok": True, "usuario": perfil["username"],
                      "roles": perfil["roles"], "scope": perfil["scope"]})
    return {"ok": True, "perfil": perfil}


@app.post("/api/auth/logout")
def logout(resp: Response):
    sesion.clear_cookie(resp)
    return {"ok": True}


@app.get("/api/auth/me")
def me(ses: sesion.Sesion = Depends(sesion.actual)):
    p = identidad.perfil(ses.username)
    if not p:
        return JSONResponse({"ok": False}, status_code=401)
    return {"ok": True, "perfil": p}


@app.post("/api/auth/cambiar-clave")
def cambiar_clave(body: CambioClave, resp: Response, ses: sesion.Sesion = Depends(sesion.actual)):
    if not identidad.autenticar(ses.username, body.actual):
        return JSONResponse({"ok": False, "error": "La clave actual no es correcta."}, status_code=400)
    if len(body.nueva or "") < 8:
        return JSONResponse({"ok": False, "error": "La nueva clave debe tener al menos 8 caracteres."}, status_code=400)
    identidad.cambiar_password(ses.username, body.nueva)
    p = identidad.perfil(ses.username)
    tok = sesion.crear_token({"sub": p["username"], "nombre": p["nombre"], "roles": p["roles"],
                              "scope": p["scope"], "must_change": False})
    sesion.set_cookie(resp, tok)
    governance.audit({"origen": "cambio_clave", "ok": True, "usuario": ses.username})
    return {"ok": True, "perfil": p}


# ---------------- Datos (protegidos) ----------------
@app.get("/api/catalog")
def get_catalog(ses: sesion.Sesion = Depends(sesion.actual)):
    return governance.load_catalog()


@app.post("/api/query")
def query(spec: Spec, ses: sesion.Sesion = Depends(sesion.actual)):
    ok, payload = _ejecutar(spec.model_dump(), ses)
    return JSONResponse(payload, status_code=200 if ok else 422)


@app.post("/api/ask")
def ask(p: Pregunta, ses: sesion.Sesion = Depends(sesion.actual)):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return JSONResponse({"ok": False, "errores": [
            "Falta ANTHROPIC_API_KEY. Ponla en X:\\_modernizacion\\vitrina360\\.env y reinicia el servidor."]},
            status_code=503)
    try:
        import nl2dax
        spec = nl2dax.pregunta_a_spec(p.pregunta, historial=p.historial)
    except Exception as e:
        return JSONResponse({"ok": False, "errores": ["Error del LLM: %s" % str(e)[:300]]}, status_code=502)

    if spec.get("intencion") != "consulta":
        governance.audit({"origen": "ask", "intencion": spec.get("intencion"), "pregunta": p.pregunta})
        return {"ok": True, "intencion": spec.get("intencion"),
                "mensaje": spec.get("mensaje") or spec.get("narrativa"), "spec": spec}

    ok, payload = _ejecutar(spec, ses, pregunta=p.pregunta)
    if not ok and payload.get("errores"):
        # un reintento de reparacion con los errores del validador
        try:
            spec = nl2dax.pregunta_a_spec(p.pregunta, errores_previos=payload["errores"], historial=p.historial)
            ok, payload = _ejecutar(spec, ses, pregunta=p.pregunta)
        except Exception as e:
            return JSONResponse({"ok": False, "errores": ["Error del LLM (reintento): %s" % str(e)[:300]]},
                                status_code=502)

    payload.update({"intencion": "consulta", "titulo": spec.get("titulo"),
                    "narrativa": spec.get("narrativa"), "viz": spec.get("viz"), "spec": spec})
    return JSONResponse(payload, status_code=200 if ok else 422)


# Sirve el build de React (single-origin: la misma app sirve /api y la SPA).
# Debe montarse DESPUES de las rutas /api. Si no hay build, cae al front de un archivo.
DIST = os.path.normpath(os.path.join(HERE, "..", "web", "dist"))
if os.path.isdir(DIST):
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
else:
    @app.get("/")
    def index():
        return FileResponse(os.path.join(FRONT, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8077, reload=False)
