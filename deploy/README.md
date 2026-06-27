# vitrina360 — despliegue de prueba en una VM (internet + Entra ID SSO)

Topología: **internet → nginx (TLS) → oauth2-proxy (Entra ID SSO) → app (FastAPI+React)**.
En runtime la app solo hace **HTTPS saliente** a Fabric (ULima360) y a Claude — no entra a DB2 ni a la red on-prem.

## 0. Prerequisitos
- VM Linux (Ubuntu 22.04+) con **Docker** y **docker compose**, puertos **80 y 443** abiertos.
- Un **DNS A** `vitrina360.ulima.edu.pe` → IP pública de la VM.
- La VM con salida a internet (api.powerbi.com, api.fabric.microsoft.com, api.anthropic.com, login.microsoftonline.com).

## 1. Dos registros de aplicación en Entra ID
**App #1 — Service Principal (la app lee ULima360, read-only):**
1. Entra ID → App registrations → New → copia **Tenant ID** y **Client ID** → `FABRIC_*`.
2. Certificates & secrets → New client secret → copia el valor → `FABRIC_SP_CLIENT_SECRET`.
3. **Tenant admin (Fabric/Power BI admin portal):** habilitar *"Service principals can use Fabric APIs"* y *"Dataset Execute Queries REST API"* (puede acotarse a un grupo de seguridad que contenga al SP).
4. En el workspace **ULima-DataLake**: agrega el SP como **Viewer + Build** sobre `ULima360` (o **Member** del workspace).

**App #2 — OIDC para el login de usuarios (oauth2-proxy):**
1. Otro App registration → Web → Redirect URI: `https://vitrina360.ulima.edu.pe/oauth2/callback`.
2. Client secret → `OAUTH2_PROXY_CLIENT_SECRET`; Client ID → `OAUTH2_PROXY_CLIENT_ID`.
3. (Opcional) Token configuration → agrega el claim `email`. El acceso queda restringido a `@ulima.edu.pe` por `OAUTH2_PROXY_EMAIL_DOMAIN`.

## 2. Configurar y levantar (automático con `deploy.sh`)
```bash
cp .env.example .env && chmod 600 .env     # completa Entra ID, API key y host
bash deploy.sh
```
`deploy.sh` es idempotente y hace todo: valida `.env`, **genera el cookie secret** si falta,
**saca el certificado TLS** (Let's Encrypt, la 1.ª vez) y **levanta el stack** (`docker compose up -d --build`).
Reejecútalo para re-deploy. Abre **https://vitrina360.ulima.edu.pe** → login Entra ID → vitrina360.

> Cert manual (si prefieres no usar deploy.sh): `docker run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt certbot/certbot certonly --standalone -d "$VITRINA_HOST" --agree-tos -m TU_EMAIL -n`, luego `docker compose up -d --build`.

## 4. Verificar
```bash
docker compose ps                 # los 3 servicios "running"
docker compose logs -f app        # arranque de uvicorn
curl -kI https://vitrina360.ulima.edu.pe/    # 302 -> /oauth2/sign_in (SSO activo)
```

## 5. Mantenimiento
- **Catálogo del chat:** se hornea en la imagen (`backend/catalog.json` + `catalogo_llm.md`). Si cambia el modelo `ULima360`, regenéralo en tu PC (`py -3.12 backend/build_catalog.py`) y reconstruye/redeploya la imagen.
- **Auditoría:** `./data/audit.log.jsonl` (volumen persistente). Para un test serio, envíalo a un colector de logs.
- **Actualizar:** `git pull` (o copiar) → `docker compose up -d --build`.

## 6. Checklist de seguridad (es internet, aunque el dato sea agregado/NO-PII)
- [ ] `.env` con permisos 600, **fuera del repo** (ya está en `.gitignore`/`.dockerignore`).
- [ ] SSO obligatorio (oauth2-proxy delante) — el login de la app es cosmético, **no** es la barrera.
- [ ] Service principal **solo lectura** (Viewer/Build); nunca escribe en Fabric.
- [ ] TLS 1.2+ (ya en nginx.conf); HSTS opcional para prod.
- [ ] CORS: hoy `*` (single-origin, no se ejercita tras el proxy); acótalo al host para prod.
- [ ] Ley 29733: al LLM solo van metadatos + agregados (sin PII); la app no expone filas a grano de persona (validador de gobierno activo).

## Notas
- **DEV local** sigue funcionando sin SP: `py -3.12 backend/app.py` usa la caché device-code de `..\fabric\fabric_auth.py`. El SP se activa solo si `FABRIC_SP_*` están en el entorno.
- No se toca nada del **DPA de producción**: esto reusa `ULima360` (workspace nuevo) en modo lectura.
