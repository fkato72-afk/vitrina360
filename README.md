# ULima360 · Analytics (vitrina360)

Capa de **consumo** del Data Lake: dashboards interactivos propios + "habla con tu data",
ambos sobre una **capa de servicio gobernada** que reusa el modelo semántico `ULima360`
(Microsoft Fabric / OneLake). No reemplaza el lago ni toca producción: lo lee read-only.

## La idea en una línea
El LLM **no consulta tablas crudas ni escribe DAX libre**: elige medidas/columnas de un
**catálogo** (las 33 medidas certificadas del modelo) y emite un *spec*; el servidor valida
cada nombre contra el catálogo y **construye el DAX determinista**, lo ejecuta con la REST
API `executeQueries` (read-only) y devuelve datos agregados. Al LLM solo viajan metadatos +
agregados — **nunca PII** (el propio modelo es NO-PII por diseño; Ley 29733).

## Arquitectura
```
frontend/index.html  (ECharts, tema Ulima)  ── chat + explorador
        │  /api/ask (LLM)        │  /api/query (determinista)
backend/app.py (FastAPI)
        ├─ nl2dax.py      NL -> spec  (Claude, tool-forced, catálogo como contexto)
        ├─ governance.py  valida spec vs catálogo (allowlist, sin [id], roles, auditoría)
        ├─ dax_builder.py spec -> DAX (SUMMARIZECOLUMNS/TOPN)
        ├─ build_catalog.py  introspección viva del modelo (INFO.VIEW.*) -> catalog.json + catalogo_llm.md
        └─ fabric_client.py  token Power BI (reusa ../fabric/fabric_auth.py) + executeQueries
                              │
                  Modelo semántico ULima360 (DirectLake)  ─►  gold OneLake (ya construido)
```

## Gobierno (Ley 29733 · mandamiento #1)
- **Allowlist:** solo medidas/columnas del catálogo; KPIs salen de las medidas certificadas (un solo dueño).
- **Sin identificadores:** las columnas `[id]` (id_persona, id_alumno, co_alum…) no se pueden agrupar/filtrar.
- **Tablas con candado:** `fact_riesgo_desercion` (watchlist) requiere rol `tutoria`/`admin`; `fact_fin_*` solo agregados.
- **Auditoría:** cada consulta se registra en `backend/audit.log.jsonl` (metadatos, sin datos crudos).
- **Read-only:** `executeQueries` solo evalúa DAX; nada se modifica.

## Correr (Windows, Python 3.12)
```powershell
py -3.12 -m pip install -r requirements.txt
copy .env.example .env   # y completa ANTHROPIC_API_KEY
# carga el .env en el entorno (o expórtalo) y arranca:
py -3.12 backend\app.py
# abre http://127.0.0.1:8077
```
Auth a Fabric: reusa la caché de `..\fabric\fabric_auth.py`. Si el token caducó:
`py -3.12 -c "import sys;sys.path.insert(0,r'backend');import fabric_client as c;c.login()"`

Reconstruir el catálogo si cambia el modelo: `py -3.12 backend\build_catalog.py`

## Estado (sprint 0 — probado en vivo)
- [x] Ruta de datos: `executeQueries` contra ULima360 (206.997 filas matrícula, 50.235 alumnos).
- [x] Catálogo vivo: 19 tablas, 33 medidas certificadas, 5 relaciones, 6 tablas con gobierno.
- [x] Camino determinista e2e: spec → validación → DAX → datos (auditado).
- [x] API FastAPI + front (chat + explorador, ECharts).
- [x] Chat `/api/ask` validado: ranking, serie temporal, embudo+filtro, KPI, financiero agregado.
- [x] Gobierno probado: rechaza PII/[id]/tabla restringida en intención y validador; permite agregado con rol.
- [ ] Migrar el front a React + tema/login Ulima (logo.svg), drill-down y cross-filter.
- [ ] Servidor MCP sobre la misma capa (para Copilot / LLM del usuario).
- [ ] RLS por rol (impersonate en executeQueries) y enriquecer descripciones del modelo.
```
```
