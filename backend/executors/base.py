# -*- coding: utf-8 -*-
"""Contrato comun de los ejecutores por plano de datos.

Cada plano (analitico / operativo_fresco / operativo_puntual) implementa este
mismo protocolo, de modo que el router despacha igual a cualquiera. La validacion
de gobierno y la auditoria viven FUERA del ejecutor (en app.py), compartidas.
"""
from dataclasses import dataclass, field


@dataclass
class Resultado:
    ok: bool
    filas: list = field(default_factory=list)   # lista de dicts normalizados (mismo formato de hoy)
    consulta: str = ""                            # DAX o nombre de vista/SP, para auditoria
    error: str | None = None


class Executor:
    """Interfaz. Un ejecutor declara su `plano` e implementa `ejecutar`.

    ejecutar(spec: dict, ctx: dict) -> Resultado
      spec: el SPEC ya validado por governance.validate_spec
      ctx : contexto de la peticion (roles, usuario, etc.)
    """
    plano = "base"

    def ejecutar(self, spec: dict, ctx: dict) -> Resultado:  # pragma: no cover
        raise NotImplementedError
