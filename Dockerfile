# ---------- build del frontend React ----------
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---------- backend + sirve el build (single-origin) ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./backend/
COPY --from=web /web/dist ./web/dist
EXPOSE 8077
# uvicorn sirve API + SPA; bind 0.0.0.0 para el contenedor.
# La auth a Fabric va por service principal (FABRIC_SP_* en el entorno).
CMD ["python", "-m", "uvicorn", "app:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8077"]
