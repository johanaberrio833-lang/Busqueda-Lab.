"""ReliefWeb (servicio oficial de OCHA – Naciones Unidas).

Publica vacantes de agencias de la ONU, cooperación internacional y organizaciones sociales.
API v2: https://apidoc.reliefweb.int/  — desde nov. 2025 exige un "appname" aprobado
(se solicita gratis en la documentación). Se lee de la variable de entorno RELIEFWEB_APPNAME.
"""

from __future__ import annotations

import os

from .. import red
from ..texto import limpiar_html
from .base import Contexto, FuenteNoConfigurada, fecha_iso

URL = "https://api.reliefweb.int/v2/jobs"
CAMPOS = ["title", "url", "url_alias", "date.created", "date.closing", "source.name",
          "country.name", "city.name", "body", "career_categories.name", "type.name",
          "experience.name", "theme.name"]


def _nombres(valor) -> list[str]:
    if isinstance(valor, list):
        return [v.get("name", "") for v in valor if isinstance(v, dict) and v.get("name")]
    if isinstance(valor, dict) and valor.get("name"):
        return [valor["name"]]
    return []


def buscar(config: dict, ctx: Contexto) -> list[dict]:
    appname = os.environ.get(config.get("variable_appname", "RELIEFWEB_APPNAME"), "").strip()
    if not appname:
        raise FuenteNoConfigurada("Falta el secreto RELIEFWEB_APPNAME (appname aprobado por ReliefWeb).")

    pais = config.get("pais", "Colombia")
    limite = min(int(config.get("limite_por_pagina", 100)), 1000)
    maximo = int(config.get("maximo_total", 300))
    ofertas: list[dict] = []
    offset = 0
    while offset < maximo:
        cuerpo = {
            "limit": limite,
            "offset": offset,
            "sort": ["date.created:desc"],
            "fields": {"include": CAMPOS},
            "filter": {"field": "country.name", "value": pais},
        }
        respuesta = red.json_post(f"{URL}?appname={appname}", cuerpo)
        datos = respuesta.get("data", [])
        for item in datos:
            f = item.get("fields", {})
            ciudades = _nombres(f.get("city"))
            organizaciones = _nombres(f.get("source"))
            categorias = _nombres(f.get("career_categories")) + _nombres(f.get("theme"))
            descripcion = limpiar_html(f.get("body", ""))
            if categorias:
                descripcion = f"Áreas: {', '.join(categorias)}. {descripcion}"
            ofertas.append({
                "id_externo": str(item.get("id")),
                "titulo": f.get("title", "").strip(),
                "organizacion": ", ".join(organizaciones),
                "ubicacion": ", ".join(ciudades + [pais]) if ciudades else pais,
                "url": f.get("url_alias") or f.get("url") or f"https://reliefweb.int/job/{item.get('id')}",
                "fecha_publicacion": fecha_iso((f.get("date") or {}).get("created")),
                "fecha_cierre": fecha_iso((f.get("date") or {}).get("closing")),
                "descripcion": descripcion,
                "tipo": "vacante",
            })
        if len(datos) < limite:
            break
        offset += limite
    return ofertas
