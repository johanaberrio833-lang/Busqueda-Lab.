"""Carga y validación de perfiles de búsqueda (config/perfiles/*.json).

Cada archivo es un perfil anónimo. Los archivos que empiezan por "_" (como la plantilla)
se ignoran. Un perfil con "activo": false no se usa en la búsqueda.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PATRON_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")

SCORING_POR_DEFECTO = {
    "puntos_por_rol_en_titulo": 8,
    "puntos_por_rol_en_texto": 4,
    "puntos_bonus_ciudad_preferida": 2,
    "puntaje_crudo_para_100": 24,
    "afinidad_minima_para_guardar": 30,
}


class PerfilInvalido(ValueError):
    pass


def _lista_texto(valor) -> bool:
    return isinstance(valor, list) and all(isinstance(x, str) and x.strip() for x in valor)


def _bloque_ponderado(valor) -> bool:
    return (isinstance(valor, dict) and isinstance(valor.get("peso"), (int, float))
            and _lista_texto(valor.get("terminos", [])))


def validar(perfil: dict, nombre_archivo: str = "") -> list[str]:
    """Devuelve la lista de errores (vacía si el perfil es válido)."""
    e: list[str] = []
    pid = perfil.get("id")
    if not isinstance(pid, str) or not PATRON_ID.match(pid):
        e.append("'id' debe ser minúsculas, números y guiones (ej. 'contratacion-publica').")
    elif nombre_archivo and not Path(nombre_archivo).stem.startswith("_") and Path(nombre_archivo).stem != pid:
        e.append(f"'id' ({pid}) debe coincidir con el nombre del archivo ({Path(nombre_archivo).stem}.json).")
    if not isinstance(perfil.get("nombre"), str) or not perfil["nombre"].strip():
        e.append("Falta 'nombre' (texto visible en el dashboard).")
    if not _lista_texto(perfil.get("roles_objetivo")) or not perfil.get("roles_objetivo"):
        e.append("'roles_objetivo' debe ser una lista de textos con al menos un cargo.")
    for clave in ("palabras_clave_principales", "palabras_clave_secundarias"):
        if not _bloque_ponderado(perfil.get(clave)):
            e.append(f"'{clave}' debe ser {{'peso': número, 'terminos': [textos]}}.")
    if "palabras_penalizacion" in perfil and not _bloque_ponderado(perfil["palabras_penalizacion"]):
        e.append("'palabras_penalizacion' debe ser {'peso': número, 'terminos': [textos]}.")
    if not isinstance(perfil.get("palabras_exclusion", []), list):
        e.append("'palabras_exclusion' debe ser una lista.")
    um = perfil.get("ubicacion_modalidad", {})
    if not isinstance(um, dict):
        e.append("'ubicacion_modalidad' debe ser un objeto.")
    else:
        for clave in ("ciudades_preferidas", "ciudades_aceptadas", "modalidades_aceptadas"):
            if clave in um and not isinstance(um[clave], list):
                e.append(f"'ubicacion_modalidad.{clave}' debe ser una lista.")
    sc = perfil.get("scoring", {})
    if not isinstance(sc, dict):
        e.append("'scoring' debe ser un objeto.")
    elif sc.get("puntaje_crudo_para_100", 1) <= 0:
        e.append("'scoring.puntaje_crudo_para_100' debe ser mayor que 0.")
    return e


def completar(perfil: dict) -> dict:
    """Agrega valores por defecto sin modificar el original."""
    p = json.loads(json.dumps(perfil))
    p.setdefault("activo", True)
    p.setdefault("palabras_exclusion", [])
    p.setdefault("palabras_penalizacion", {"peso": 0, "terminos": []})
    p.setdefault("terminos_busqueda", [])
    p.setdefault("ubicacion_modalidad", {})
    p["scoring"] = {**SCORING_POR_DEFECTO, **p.get("scoring", {})}
    return p


def cargar_archivo(ruta: Path) -> dict:
    try:
        perfil = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        raise PerfilInvalido(f"{ruta.name}: JSON mal formado (línea {ex.lineno}): {ex.msg}") from ex
    errores = validar(perfil, ruta.name)
    if errores:
        raise PerfilInvalido(f"{ruta.name}:\n  - " + "\n  - ".join(errores))
    return completar(perfil)


def cargar_activos(carpeta: Path) -> list[dict]:
    perfiles = []
    for ruta in sorted(carpeta.glob("*.json")):
        if ruta.name.startswith("_"):
            continue
        perfil = cargar_archivo(ruta)
        if perfil["activo"]:
            perfiles.append(perfil)
    ids = [p["id"] for p in perfiles]
    if len(ids) != len(set(ids)):
        raise PerfilInvalido("Hay perfiles con el mismo 'id'.")
    return perfiles


def firma(perfiles: list[dict]) -> str:
    """Huella de los perfiles: si cambia, las ofertas ya vistas se vuelven a evaluar."""
    texto = json.dumps(perfiles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]
