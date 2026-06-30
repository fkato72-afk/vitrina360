# -*- coding: utf-8 -*-
"""Router de intencion: decide a que PLANO de datos va una consulta.

DETERMINISTA: el LLM puede sugerir un plano (spec["plano_sugerido"]), pero la
autoridad es este router. El default siempre cae al plano mas gobernado.

FASE 0: solo esta registrado el plano analitico (Fabric). Los planos
operativo_fresco (A, dataset espejo) y operativo_puntual (B, vistas/SP curados)
se registran en sus fases sin tocar este contrato:

    from executors.lakehot_exec import LakeHotExecutor      # Fase 2 (A)
    from executors.operativo_exec import OperativoExecutor  # Fase 1 (B)
    REGISTRO[LakeHotExecutor.plano]  = LakeHotExecutor()
    REGISTRO[OperativoExecutor.plano] = OperativoExecutor()
"""
from executors.fabric_exec import FabricExecutor

REGISTRO = {
    FabricExecutor.plano: FabricExecutor(),
}

# Palabras que marcan necesidad de dato fresco (plano A). Se activa cuando A este
# registrado; hoy cae a analitico porque "operativo_fresco" no esta en REGISTRO.
_MARCAS_FRESCO = ("hoy", "ahora", "en vivo", "al momento", "esta hora", "en este momento")


def clasificar(spec: dict, pregunta: str = "") -> str:
    # 1) Senal fuerte: el SPEC trae una consulta operativa nombrada -> B
    if spec.get("consulta_operativa") and "operativo_puntual" in REGISTRO:
        return "operativo_puntual"
    # 2) Senal de tiempo real -> A
    if any(k in (pregunta or "").lower() for k in _MARCAS_FRESCO) and "operativo_fresco" in REGISTRO:
        return "operativo_fresco"
    # 3) Hint del LLM, si es un plano valido y registrado
    sugerido = spec.get("plano_sugerido")
    if sugerido in REGISTRO:
        return sugerido
    # 4) Default seguro: analitico gobernado
    return "analitico"


def route(spec: dict, pregunta: str = ""):
    """Devuelve (plano: str, executor: Executor)."""
    plano = clasificar(spec, pregunta)
    return plano, REGISTRO[plano]
