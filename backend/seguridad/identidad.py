# -*- coding: utf-8 -*-
"""Almacen de identidad local de vitrina360 (SQLite, solo stdlib).

Es el backend de autenticacion del POC (sin DB2/MS1-MS2, porque el VPS no alcanza
la red interna). Guarda usuarios, sus roles y su alcance (facultad/carrera), con
contrasena hasheada (pbkdf2-sha256). Migrable luego a MS1/MS2 o SSO sin tocar el
resto: basta reimplementar `autenticar`.

Mapa rol -> nivel de scope (la autoridad la fija el servidor, no el cliente):
  admin / rector / vicerrector  -> total    (ve todo el data lake)
  decano                        -> facultad (sus carreras)
  director_carrera / secretario_academico -> carrera
"""
import os
import json
import sqlite3
import hashlib
import secrets

import scope as scope_mod

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("VITRINA_IDENTIDAD_DB") or os.path.join(HERE, "identidad.db")

ROL_NIVEL = {
    "admin": "total",
    "rector": "total",
    "vicerrector": "total",
    "decano": "facultad",
    "director_carrera": "carrera",
    "secretario_academico": "carrera",
}
_PRIO = {"total": 3, "facultad": 2, "carrera": 1}

_PBKDF2_ITER = 200_000


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuario (
              id        INTEGER PRIMARY KEY AUTOINCREMENT,
              username  TEXT UNIQUE NOT NULL,
              nombre    TEXT NOT NULL,
              co_pers   INTEGER,
              salt      TEXT NOT NULL,
              pwd_hash  TEXT NOT NULL,
              must_change INTEGER NOT NULL DEFAULT 1,
              activo    INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS usuario_rol (
              usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
              rol        TEXT NOT NULL,
              PRIMARY KEY (usuario_id, rol)
            );
            CREATE TABLE IF NOT EXISTS usuario_scope (
              usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
              tipo       TEXT NOT NULL,   -- 'facultad' | 'carrera'
              nombre     TEXT NOT NULL,
              PRIMARY KEY (usuario_id, tipo, nombre)
            );
            """
        )


# ---- contrasena ----
def hash_pwd(pwd, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITER)
    return salt, h.hex()


def verify_pwd(pwd, salt, expected_hex):
    _, got = hash_pwd(pwd, salt)
    return secrets.compare_digest(got, expected_hex)


# ---- altas ----
def crear_usuario(username, nombre, co_pers, password, roles, scopes, must_change=True, activo=True):
    """scopes: lista de (tipo, nombre). Devuelve el id. Si ya existe, lo reemplaza."""
    salt, ph = hash_pwd(password)
    with conn() as c:
        cur = c.execute("SELECT id FROM usuario WHERE username=?", (username,))
        row = cur.fetchone()
        if row:
            uid = row["id"]
            c.execute("UPDATE usuario SET nombre=?,co_pers=?,salt=?,pwd_hash=?,must_change=?,activo=? WHERE id=?",
                      (nombre, co_pers, salt, ph, int(must_change), int(activo), uid))
            c.execute("DELETE FROM usuario_rol WHERE usuario_id=?", (uid,))
            c.execute("DELETE FROM usuario_scope WHERE usuario_id=?", (uid,))
        else:
            cur = c.execute(
                "INSERT INTO usuario(username,nombre,co_pers,salt,pwd_hash,must_change,activo) VALUES(?,?,?,?,?,?,?)",
                (username, nombre, co_pers, salt, ph, int(must_change), int(activo)))
            uid = cur.lastrowid
        for r in roles:
            c.execute("INSERT INTO usuario_rol(usuario_id,rol) VALUES(?,?)", (uid, r))
        for tipo, nombre_v in scopes:
            c.execute("INSERT OR IGNORE INTO usuario_scope(usuario_id,tipo,nombre) VALUES(?,?,?)",
                      (uid, tipo, nombre_v))
        return uid


def cambiar_password(username, nueva):
    salt, ph = hash_pwd(nueva)
    with conn() as c:
        c.execute("UPDATE usuario SET salt=?,pwd_hash=?,must_change=0 WHERE username=?", (salt, ph, username))


# ---- lectura / scope ----
def _roles(c, uid):
    return [r["rol"] for r in c.execute("SELECT rol FROM usuario_rol WHERE usuario_id=?", (uid,))]


def _scopes(c, uid):
    rows = c.execute("SELECT tipo,nombre FROM usuario_scope WHERE usuario_id=?", (uid,))
    fac, car = [], []
    for r in rows:
        (fac if r["tipo"] == "facultad" else car).append(r["nombre"])
    return fac, car


def scope_de(roles, facultades, carreras):
    """Computa el Scope efectivo desde los roles (nivel mas amplio gana)."""
    nivel = "carrera"
    best = 0
    for r in roles:
        n = ROL_NIVEL.get(r)
        if n and _PRIO[n] > best:
            best, nivel = _PRIO[n], n
    if best == 0:
        # rol desconocido: fail-closed al grano mas estrecho y sin valores
        return scope_mod.Scope("carrera", [], [])
    if nivel == "total":
        return scope_mod.Scope("total")
    if nivel == "facultad":
        return scope_mod.Scope("facultad", facultades=facultades)
    return scope_mod.Scope("carrera", carreras=carreras)


def autenticar(username, password):
    """Devuelve dict de sesion si las credenciales son validas y el usuario esta
    activo; si no, None."""
    with conn() as c:
        row = c.execute("SELECT * FROM usuario WHERE username=? AND activo=1", (username,)).fetchone()
        if not row or not verify_pwd(password, row["salt"], row["pwd_hash"]):
            return None
        uid = row["id"]
        roles = _roles(c, uid)
        fac, car = _scopes(c, uid)
        scope = scope_de(roles, fac, car)
        return {
            "username": row["username"],
            "nombre": row["nombre"],
            "co_pers": row["co_pers"],
            "roles": roles,
            "scope": scope.to_dict(),
            "must_change": bool(row["must_change"]),
        }


def perfil(username):
    """Como autenticar pero sin validar contrasena (para /me desde el token)."""
    with conn() as c:
        row = c.execute("SELECT * FROM usuario WHERE username=? AND activo=1", (username,)).fetchone()
        if not row:
            return None
        uid = row["id"]
        roles = _roles(c, uid)
        fac, car = _scopes(c, uid)
        return {
            "username": row["username"], "nombre": row["nombre"], "co_pers": row["co_pers"],
            "roles": roles, "scope": scope_de(roles, fac, car).to_dict(),
            "must_change": bool(row["must_change"]),
        }
