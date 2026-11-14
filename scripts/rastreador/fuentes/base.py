"""Piezas comunes a todas las fuentes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable


class FuenteNoConfigurada(RuntimeError):
    """La fuente necesita una clave o un ajuste que no está presente. Se omite sin error."""


@dataclass
class Contexto:
    terminos: list[str] = field(default_factory=list)
    ya_visto: Callable[[str, str], bool] = lambda fuente, id_externo: False
    avisos: list[str] = field(default_factory=list)

    def avisar(self, mensaje: str) -> None:
        self.avisos.append(mensaje)


def fecha_iso(valor) -> str | None:
    """Convierte fechas ISO, RFC 822 (RSS) o marcas Unix a AAAA-MM-DD."""
    if valor in (None, ""):
        return None
    if isinstance(valor, (int, float)):
        return datetime.fromtimestamp(valor, tz=timezone.utc).date().isoformat()
    texto = str(valor).strip()
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(texto).date().isoformat()
    except (TypeError, ValueError):
        pass
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", texto)
    return "-".join(m.groups()) if m else None
