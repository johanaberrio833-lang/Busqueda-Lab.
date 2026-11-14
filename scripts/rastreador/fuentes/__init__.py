"""Registro de fuentes de vacantes.

Para agregar una fuente nueva:
  1. Cree un módulo en esta carpeta con una función `buscar(config: dict, ctx: Contexto) -> list[dict]`.
     Cada elemento debe tener al menos: id_externo, titulo, url. Opcionales: organizacion,
     ubicacion, modalidad, fecha_publicacion (AAAA-MM-DD), fecha_cierre, descripcion, tipo.
  2. Regístrela en REGISTRO con el mismo nombre que usará en config/fuentes.json.
"""

from . import paginas_oficiales, reliefweb, rss
from .base import Contexto, FuenteNoConfigurada

REGISTRO = {
    "reliefweb": reliefweb.buscar,
    "paginas_oficiales": paginas_oficiales.buscar,
    "rss": rss.buscar,
}

__all__ = ["REGISTRO", "Contexto", "FuenteNoConfigurada"]
