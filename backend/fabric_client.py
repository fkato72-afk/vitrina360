# -*- coding: utf-8 -*-
"""Cliente de datos de vitrina360.

Reusa la auth existente de Fabric (fabric_auth.py, cache DPAPI) pero pide el token
con el scope de Power BI para poder llamar al endpoint REST executeQueries, que
ejecuta DAX (estrictamente read-only) contra el modelo semantico ULima360.

Nada aqui modifica recursos: executeQueries solo evalua consultas DAX.
"""
import os
import sys
import json
import urllib.request
import urllib.error

FABRIC_DIR = r"X:\_modernizacion\fabric"  # solo modo dev (cache device-code local)

PBI_SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]
# Un service principal SOLO puede usar el endpoint cualificado por workspace (grupo);
# el de "My workspace" (sin grupo) le devuelve 401 PowerBINotAuthorized. La ruta con
# grupo sirve para SP Y para usuario, asi que se prefiere siempre que haya workspace.
EXEC_URL_GROUP = "https://api.powerbi.com/v1.0/myorg/groups/{gid}/datasets/{dsid}/executeQueries"
EXEC_URL = "https://api.powerbi.com/v1.0/myorg/datasets/{dsid}/executeQueries"  # fallback dev (usuario)


def _dataset_id():
    # 1) env var (despliegue);  2) fabric_ids.json local (dev)
    env = os.environ.get("VITRINA_DATASET_ID")
    if env:
        return env
    try:
        with open(os.path.join(FABRIC_DIR, "fabric_ids.json"), encoding="utf-8") as f:
            return json.load(f).get("semantic_model_id")
    except Exception:
        return None


DATASET_ID = _dataset_id()


def _workspace_id():
    # 1) env var (despliegue: el contenedor no trae fabric_ids.json);  2) fabric_ids.json local (dev)
    env = os.environ.get("VITRINA_WORKSPACE_ID")
    if env:
        return env
    try:
        with open(os.path.join(FABRIC_DIR, "fabric_ids.json"), encoding="utf-8") as f:
            return json.load(f).get("workspace_id")
    except Exception:
        return None


WORKSPACE_ID = _workspace_id()


def token():
    """Token Power BI.
    - Servidor: service principal (client credentials) via env FABRIC_SP_CLIENT_ID/SECRET + FABRIC_TENANT_ID.
    - Dev: cache device-code local (fabric_auth.py, DPAPI).
    """
    cid = os.environ.get("FABRIC_SP_CLIENT_ID")
    sec = os.environ.get("FABRIC_SP_CLIENT_SECRET")
    tid = os.environ.get("FABRIC_TENANT_ID")
    if cid and sec and tid:
        import msal
        app = msal.ConfidentialClientApplication(
            cid, authority="https://login.microsoftonline.com/" + tid, client_credential=sec)
        r = app.acquire_token_for_client(scopes=PBI_SCOPES)
        return r.get("access_token")
    try:
        if FABRIC_DIR not in sys.path:
            sys.path.insert(0, FABRIC_DIR)
        from fabric_auth import get_token as _gt  # noqa: E402
        return _gt(PBI_SCOPES)
    except Exception:
        return None


def login():
    """Device-flow local (solo dev) para poblar la cache DPAPI."""
    if FABRIC_DIR not in sys.path:
        sys.path.insert(0, FABRIC_DIR)
    from fabric_auth import _app
    app = _app()
    flow = app.initiate_device_flow(scopes=PBI_SCOPES)
    if "user_code" not in flow:
        raise RuntimeError("No se pudo iniciar device flow: " + json.dumps(flow))
    print("URL:   ", flow["verification_uri"], flush=True)
    print("CODIGO:", flow["user_code"], flush=True)
    r = app.acquire_token_by_device_flow(flow)
    print("LOGIN OK" if "access_token" in r else ("FALLO: " + r.get("error_description", "?")[:200]),
          flush=True)


def execute_dax(dax, dataset_id=None, workspace_id=None, impersonate=None, timeout=90):
    """Ejecuta una consulta DAX y devuelve filas como lista de dicts.

    impersonate: UPN para correr con identidad efectiva (RLS). None = identidad del servicio.
    """
    dataset_id = dataset_id or DATASET_ID
    gid = workspace_id or WORKSPACE_ID
    tok = token()
    if not tok:
        raise RuntimeError("Sin token Power BI. Corre una vez:  python -c \"import fabric_client as c; c.login()\"")
    body = {"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}}
    if impersonate:
        body["impersonatedUserName"] = impersonate
    # con workspace -> sirve para SP y usuario; sin el -> solo "My workspace" (dev/usuario)
    url = EXEC_URL_GROUP.format(gid=gid, dsid=dataset_id) if gid else EXEC_URL.format(dsid=dataset_id)
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError("executeQueries HTTP %s: %s" % (e.code, detail[:600]))
    tbl = payload["results"][0]["tables"][0]
    rows = tbl.get("rows", [])
    # executeQueries devuelve claves "[Tabla[col]]" (columna agrupada) o "[alias]" (medida).
    # Normaliza al nombre limpio de columna/medida para la UI.
    norm = []
    for row in rows:
        norm.append({_clean_key(k): v for k, v in row.items()})
    return norm


def _clean_key(k):
    k = k.strip()
    if k.startswith("[") and k.endswith("]"):
        k = k[1:-1]
    if "[" in k:                 # quedaba "Tabla[Columna" -> toma la columna
        k = k.split("[")[-1]
    return k.rstrip("]")


if __name__ == "__main__":
    print("DATASET_ID:", DATASET_ID)
    print("token:", "OK" if token() else "None (corre login())")
