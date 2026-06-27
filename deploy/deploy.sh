#!/usr/bin/env bash
# Despliegue de vitrina360 en la VM (idempotente). Correr desde deploy/:  bash deploy.sh
# Hace: valida .env -> genera cookie secret si falta -> saca cert TLS (1ra vez) -> docker compose up.
set -euo pipefail
cd "$(dirname "$0")"

say() { printf "\n\033[1;33m== %s\033[0m\n" "$*"; }
die() { printf "\033[1;31mERROR: %s\033[0m\n" "$*" >&2; exit 1; }

# --- docker / compose ---
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
$DOCKER compose version >/dev/null 2>&1 || die "Falta 'docker compose'. Instala Docker Engine + compose plugin."
COMPOSE="$DOCKER compose"

# --- .env ---
if [[ ! -f .env ]]; then
  cp .env.example .env && chmod 600 .env
  die ".env creado desde la plantilla. Complétalo (Entra ID, API key, host) y reejecuta."
fi
getenv() { grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }

say "Validando .env"
missing=0
for k in ANTHROPIC_API_KEY FABRIC_TENANT_ID FABRIC_SP_CLIENT_ID FABRIC_SP_CLIENT_SECRET \
         VITRINA_HOST OAUTH2_PROXY_CLIENT_ID OAUTH2_PROXY_CLIENT_SECRET CERTBOT_EMAIL; do
  v="$(getenv "$k")"
  if [[ -z "$v" || "$v" == *"<"* || "$v" == "sk-ant-..." ]]; then
    echo "  falta o es placeholder: $k"; missing=1
  fi
done
[[ "$missing" -eq 0 ]] || die "Completa las variables anteriores en .env y reejecuta."

HOST="$(getenv VITRINA_HOST)"; EMAIL="$(getenv CERTBOT_EMAIL)"
echo "  host: $HOST"

# --- cookie secret para oauth2-proxy ---
if [[ -z "$(getenv OAUTH2_PROXY_COOKIE_SECRET)" ]]; then
  say "Generando OAUTH2_PROXY_COOKIE_SECRET"
  secret="$(openssl rand -base64 32)"
  esc="$(printf '%s' "$secret" | sed -e 's/[\/&]/\\&/g')"
  if grep -qE '^OAUTH2_PROXY_COOKIE_SECRET=' .env; then
    sed -i "s/^OAUTH2_PROXY_COOKIE_SECRET=.*/OAUTH2_PROXY_COOKIE_SECRET=$esc/" .env
  else
    echo "OAUTH2_PROXY_COOKIE_SECRET=$secret" >> .env
  fi
fi

mkdir -p data certbot-www

# --- certificado TLS (Let's Encrypt) la primera vez ---
if [[ ! -f "/etc/letsencrypt/live/$HOST/fullchain.pem" ]]; then
  say "Obteniendo certificado TLS para $HOST"
  echo "  (requiere que el DNS de $HOST apunte a esta VM y el puerto 80 libre)"
  $DOCKER run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt \
    certbot/certbot certonly --standalone -d "$HOST" --agree-tos -m "$EMAIL" -n \
    || die "Falló certbot. Revisa DNS/puerto 80 e intenta de nuevo."
else
  echo "  cert ya existe para $HOST (ok)"
fi

# --- levantar el stack ---
say "Construyendo y levantando contenedores"
$COMPOSE up -d --build

say "Estado"
$COMPOSE ps
sleep 4
code="$(curl -kso /dev/null -w '%{http_code}' --resolve "$HOST:443:127.0.0.1" "https://$HOST/" || echo 000)"
echo "  https://$HOST/ -> HTTP $code  (302 = SSO activo, redirige al login Entra ID)"

cat <<EOF

LISTO. Abre:  https://$HOST
- Renovación del cert (cron mensual sugerido):
    $DOCKER run --rm -v /etc/letsencrypt:/etc/letsencrypt -v "\$PWD/certbot-www:/var/www/certbot" \\
      certbot/certbot renew --webroot -w /var/www/certbot && $COMPOSE exec nginx nginx -s reload
- Logs:        $COMPOSE logs -f app
- Re-deploy:   git pull (o copiar) && bash deploy.sh
EOF
