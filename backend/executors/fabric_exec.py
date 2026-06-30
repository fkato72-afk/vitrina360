# -*- coding: utf-8 -*-
"""Ejecutor del plano ANALITICO: SPEC -> DAX -> executeQueries (Fabric/Power BI).

Es exactamente el camino que vivia inline en app.py._ejecutar (build_from_spec +
execute_dax), ahora envuelto como ejecutor. NO cambia comportamiento: mismo DAX,
mismo cliente, misma truncacion de error a 300 chars.
"""
import dax_builder
import fabric_client

from executors.base import Executor, Resultado


class FabricExecutor(Executor):
    plano = "analitico"

    def ejecutar(self, spec: dict, ctx: dict) -> Resultado:
        dax = dax_builder.build_from_spec(spec)
        try:
            filas = fabric_client.execute_dax(dax)
        except Exception as e:
            return Resultado(ok=False, filas=[], consulta=dax, error=str(e)[:300])
        return Resultado(ok=True, filas=filas, consulta=dax)
