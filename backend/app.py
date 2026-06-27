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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import fabric_client
import dax_builder
import governance

HERE = os.path.dirname(os.path.abspath(__file__))
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

# CORS configurable (en despliegue acotar al origen real); por defecto * para dev.
_origins = [o.strip() for o in os.environ.get("VITRINA_CORS", "*").split(",")]
app = FastAPI(title="vitrina360", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])


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


def _ejecutar(spec_dict, roles):
    ok, errs, touched = governance.validate_spec(spec_dict, roles=roles)
    if not ok:
        governance.audit({"origen": "validacion", "ok": False, "errores": errs, "spec": spec_dict})
        return False, {"ok": False, "errores": errs}
    dax = dax_builder.build_from_spec(spec_dict)
    try:
        filas = fabric_client.execute_dax(dax)
    except Exception as e:
        governance.audit({"origen": "ejecucion", "ok": False, "error": str(e)[:300], "dax": dax})
        return False, {"ok": False, "errores": [str(e)[:300]], "dax": dax}
    governance.audit({"origen": "ejecucion", "ok": True, "filas": len(filas),
                      "tablas": list(touched), "medidas": spec_dict.get("medidas")})
    cols = list(filas[0].keys()) if filas else []
    return True, {"ok": True, "dax": dax, "columnas": cols, "filas": filas}


@app.get("/api/health")
def health():
    return {"ok": True, "dataset": fabric_client.DATASET_ID, "token": bool(fabric_client.token())}


@app.get("/api/catalog")
def get_catalog():
    return governance.load_catalog()


@app.post("/api/query")
def query(spec: Spec):
    ok, payload = _ejecutar(spec.model_dump(), spec.roles)
    return JSONResponse(payload, status_code=200 if ok else 422)


@app.post("/api/ask")
def ask(p: Pregunta):
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

    ok, payload = _ejecutar(spec, p.roles)
    if not ok and payload.get("errores"):
        # un reintento de reparacion con los errores del validador
        try:
            spec = nl2dax.pregunta_a_spec(p.pregunta, errores_previos=payload["errores"], historial=p.historial)
            ok, payload = _ejecutar(spec, p.roles)
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
