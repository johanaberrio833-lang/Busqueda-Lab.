"""Feeds RSS o Atom de portales oficiales (o alertas de Google limitadas a dominios oficiales).

Admite RSS 2.0 y Atom. Los enlaces de Google Alertas se desenvuelven a la URL real,
y luego el filtro de dominios oficiales decide si la oferta se conserva.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse

from .. import red
from ..texto import limpiar_html
from .base import Contexto, fecha_iso

ATOM = "{http://www.w3.org/2005/Atom}"


def _desenvolver(url: str) -> str:
    p = urlparse(url)
    if p.hostname and "google." in p.hostname and p.path.startswith("/url"):
        destino = parse_qs(p.query).get("url") or parse_qs(p.query).get("q")
        if destino:
            return destino[0]
    return url


def _txt(nodo, etiqueta: str) -> str:
    hijo = nodo.find(etiqueta)
    return (hijo.text or "").strip() if hijo is not None and hijo.text else ""


def _leer(xml_texto: str) -> list[dict]:
    raiz = ET.fromstring(xml_texto.encode("utf-8"))
    entradas = []
    for item in raiz.iter("item"):  # RSS 2.0
        entradas.append({
            "titulo": _txt(item, "title"), "url": _txt(item, "link"),
            "descripcion": _txt(item, "description"), "fecha": _txt(item, "pubDate"),
            "guid": _txt(item, "guid"),
        })
    for entry in raiz.iter(f"{ATOM}entry"):  # Atom
        enlace = entry.find(f"{ATOM}link")
        entradas.append({
            "titulo": _txt(entry, f"{ATOM}title"),
            "url": enlace.get("href", "") if enlace is not None else "",
            "descripcion": _txt(entry, f"{ATOM}content") or _txt(entry, f"{ATOM}summary"),
            "fecha": _txt(entry, f"{ATOM}published") or _txt(entry, f"{ATOM}updated"),
            "guid": _txt(entry, f"{ATOM}id"),
        })
    return entradas


def buscar(config: dict, ctx: Contexto) -> list[dict]:
    ofertas: list[dict] = []
    for feed in config.get("feeds", []):
        if not feed.get("activa", True):
            continue
        try:
            entradas = _leer(red.texto(feed["url"]))
        except (red.ErrorRed, ET.ParseError) as e:
            ctx.avisar(f"Feed {feed.get('nombre', feed['url'])}: {e}")
            continue
        for e in entradas:
            url = _desenvolver(e["url"])
            if not url or not e["titulo"]:
                continue
            ofertas.append({
                "id_externo": hashlib.sha1((e["guid"] or url).encode("utf-8")).hexdigest()[:16],
                "titulo": limpiar_html(e["titulo"]),
                "organizacion": feed.get("organizacion", ""),
                "ubicacion": feed.get("ubicacion", "Colombia"),
                "url": url,
                "fecha_publicacion": fecha_iso(e["fecha"]),
                "descripcion": limpiar_html(e["descripcion"]),
                "tipo": feed.get("tipo", "convocatoria"),
                "fuente_detalle": feed.get("nombre", ""),
            })
    return ofertas
