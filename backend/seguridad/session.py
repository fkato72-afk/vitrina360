# -*- coding: utf-8 -*-
"""Sesion firmada (JWT HS256, solo stdlib) en cookie httpOnly.

El token lleva la identidad Y el scope ya resuelto en el servidor. El cliente
nunca asserta su propio alcance: el backend lee el scope del token, no del body.
"""
import os
import json
import time
import hmac
import base64
import hashlib

try:  # en el servidor fastapi existe; offline (tests del nucleo) se degrada a stubs
    from fastapi import Request, HTTPException, Response
except ImportError:  # pragma: no cover
    Request = Response = object
    class HTTPException(Exception):
        def __init__(self, status_code=401, detail=""):
            self.status_code, self.detail = status_code, detail

import scope as scope_mod

COOKIE = "vitrina_sesion"
TTL = int(os.environ.get("VITRINA_SESSION_TTL", "43200"))  # 12 h
_SECRET = (os.environ.get("VITRINA_JWT_SECRET") or "").encode("utf-8")
# Cookie Secure salvo que se desactive explicito (dev http local).
_SECURE = os.environ.get("VITRINA_COOKIE_SECURE", "1") != "0"


def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64u_dec(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _secret():
    if not _SECRET:
        raise RuntimeError("Falta VITRINA_JWT_SECRET en el entorno (.env). No se puede firmar la sesion.")
    return _SECRET


def crear_token(payload, ttl=TTL):
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl
    h = _b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    p = _b64u(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode())
    firma = hmac.new(_secret(), ("%s.%s" % (h, p)).encode(), hashlib.sha256).digest()
    return "%s.%s.%s" % (h, p, _b64u(firma))


def leer_token(token):
    """Devuelve el payload si la firma y exp son validos; si no, None."""
    try:
        h, p, s = token.split(".")
        esperado = hmac.new(_secret(), ("%s.%s" % (h, p)).encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64u_dec(s), esperado):
            return None
        payload = json.loads(_b64u_dec(p))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


class Sesion:
    def __init__(self, payload):
        self.username = payload.get("sub")
        self.nombre = payload.get("nombre")
        self.roles = payload.get("roles", [])
        self.must_change = bool(payload.get("must_change"))
        self.scope = scope_mod.Scope.from_dict(payload.get("scope"))


def set_cookie(resp: Response, token):
    resp.set_cookie(COOKIE, token, max_age=TTL, httponly=True, samesite="lax",
                    secure=_SECURE, path="/")


def clear_cookie(resp: Response):
    resp.delete_cookie(COOKIE, path="/")


def actual(request: Request) -> Sesion:
    """Dependencia FastAPI: exige sesion valida. 401 si falta o es invalida."""
    tok = request.cookies.get(COOKIE)
    if not tok:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            tok = auth[7:]
    payload = leer_token(tok) if tok else None
    if not payload:
        raise HTTPException(status_code=401, detail="Sesion requerida")
    return Sesion(payload)
