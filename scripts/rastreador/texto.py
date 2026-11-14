"""Utilidades de texto: normalización sin tildes, búsqueda de términos y limpieza de HTML."""

from __future__ import annotations

import html
import re
import unicodedata

_NO_ALFANUM = re.compile(r"[^a-z0-9]+")
_ETIQUETAS = re.compile(r"<[^>]+>")
_BLOQUES_OCULTOS = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.S | re.I)
_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin tildes ni signos; palabras separadas por un espacio."""
    if not texto:
        return ""
    texto = html.unescape(str(texto))
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return _NO_ALFANUM.sub(" ", texto.lower()).strip()


def contiene(texto_normalizado: str, termino: str) -> bool:
    """True si el término aparece como palabra o frase completa en el texto ya normalizado."""
    t = normalizar(termino)
    return bool(t) and f" {t} " in f" {texto_normalizado} "


def limpiar_html(texto: str | None) -> str:
    """Quita etiquetas HTML y deja texto plano en una sola línea."""
    if not texto:
        return ""
    texto = _BLOQUES_OCULTOS.sub(" ", str(texto))
    texto = _ETIQUETAS.sub(" ", texto)
    texto = html.unescape(texto)
    return _ESPACIOS.sub(" ", texto).strip()


def recortar(texto: str, maximo: int = 400) -> str:
    texto = (texto or "").strip()
    if len(texto) <= maximo:
        return texto
    corte = texto[:maximo].rsplit(" ", 1)[0]
    return corte.rstrip(".,;: ") + "…"
