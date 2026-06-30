# Deploy Fase 1 — seguridad (auth + RLS por rol) en Hostinger

Runbook del despliegue REAL en uso: **imagen horneada en CI (GHCR) + Traefik del VPS
(TLS automatico)**. (El `README.md` describe la alternativa VM+nginx+SSO, no usada aqui.)

La Fase 1 agrega login real, segmentacion de filas por rol y un volumen para la
identidad. **El dato sigue saliendo solo por HTTPS a Fabric/Claude**; no toca DB2.

## Qué cambia respecto al deploy anterior
- Nuevo volumen **`vitrina-identidad`** (`/app/datos`): `identidad.db` + `credenciales_iniciales.txt`
  + `scope_valores.json`. **Persiste entre redeploys** (un redeploy NO re-siembra ni pisa claves).
- La imagen **se auto-siembra al primer arranque** desde `VITRINA_SEED_B64` (CSV de
  autoridades reales en base64; no va al repo publico). Idempotente.
- Reconciliacion de facultad/carrera contra el modelo: **best-effort al arrancar**
  (usa el cert del SP); escribe `scope_valores.json` en el volumen.

## 1. Variables nuevas en el ENV del proyecto (hPanel → Manage → Environment)
Agregar a las que ya existen (cert, ids, Anthropic, basic-auth). El compose ya las
referencia con `${...}` (si no se listan ahi, no llegan al contenedor):

| Variable | Valor | Secreta |
|---|---|---|
| `VITRINA_JWT_SECRET` | hex de 64 (firma la sesion) | **sí** |
| `VITRINA_ADMIN_PASSWORD` | clave inicial del admin `fernando` | **sí** |
| `VITRINA_SEED_B64` | CSV de autoridades en base64 | sí (datos inst.) |

> Las 3 las entrega el dev por canal seguro (no estan en el repo). Generar:
> `VITRINA_JWT_SECRET` = `python -c "import secrets;print(secrets.token_hex(32))"`;
> `VITRINA_SEED_B64` = base64 de `backend/seguridad/autoridades_db2.csv`.

## 2. Aplicar el nuevo compose + imagen
1. **Push a `main`** → el GitHub Action reconstruye `ghcr.io/fkato72-afk/vitrina360:latest`.
2. En Hostinger, **redeploy** del proyecto con `deploy/hostinger.compose.yml` (jala la imagen nueva).
3. El contenedor arranca, siembra la identidad (1ra vez) y deja las credenciales en el volumen.

## 3. Verificar
```bash
# La cookie de sesion exige login; sin sesion, 401:
curl -s -o /dev/null -w "%{http_code}\n" https://vitrina360.fkg72.com/api/catalog   # 401

# Login del admin (usa VITRINA_ADMIN_PASSWORD); guarda la cookie y consulta:
curl -s -c /tmp/c.txt -X POST https://vitrina360.fkg72.com/api/auth/login \
  -H 'content-type: application/json' -d '{"username":"fernando","password":"<ADMIN>"}'
curl -s -b /tmp/c.txt https://vitrina360.fkg72.com/api/auth/me
```
En el navegador: entrar como `fernando` (visibilidad total) y como un decano
(p. ej. `nrodriguez`) para ver la segmentacion.

## 4. Claves temporales de los demás (decanos / directores)
Se generan en el primer arranque y quedan en el volumen:
```bash
docker exec <contenedor_vitrina360> cat /app/datos/credenciales_iniciales.txt
# distribuir por canal seguro y BORRAR el archivo
```
Cada autoridad entra con su clave temporal y **debe cambiarla** en el primer ingreso.

## 5. Notas
- **Reset de identidad** (re-sembrar): borrar el volumen `vitrina-identidad` y redeploy.
- **Agregar/quitar usuarios** (Fase 1, sin panel aun): actualizar el CSV de autoridades
  → regenerar `VITRINA_SEED_B64` → borrar el volumen → redeploy. (El panel admin es Fase 2.)
- **Cookie `Secure`**: `VITRINA_COOKIE_SECURE=1` (ya en el compose) — requiere HTTPS (Traefik lo da).
- No se toca el **DPA de produccion** ni el modelo `ULima360` (solo lectura).
